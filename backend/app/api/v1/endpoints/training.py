"""
Taurus Vision — Training API Endpoints (Sprint 15-16)

Custom YOLO training pipeline boshqaruvi uchun REST API.

ENDPOINTLAR:
    GET    /training/dataset-stats         — Yig'ilgan kadrlar statistikasi
    GET    /training/runs                  — Barcha runlar ro'yxati
    GET    /training/runs/{run_id}         — Bitta run holati
    POST   /training/runs                  — Yangi training boshlash
    POST   /training/runs/{run_id}/deploy  — Modelni ishlatishga olish
    DELETE /training/runs/{run_id}         — Runni o'chirish (failed/pending)

RUXSAT:
    GET    endpointlar: barcha autentifikatsiyalangan foydalanuvchilar
    POST   /runs:       faqat ADMIN
    POST   /deploy:     faqat ADMIN
    DELETE /runs/{id}:  faqat ADMIN
"""

import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentAdmin
from app.models.training_run import TrainingStatus, TrainingRun
from app.repositories.training_repository import TrainingRepository
from app.schemas.training import (
    DatasetStatsResponse,
    TrainingDeployRequest,
    TrainingDeployResponse,
    TrainingListResponse,
    TrainingRunResponse,
    TrainingStartRequest,
    TrainingStartResponse,
)
from app.services.ai.frame_collector import get_frame_collector
from app.services.ai.dataset_builder import DatasetBuilder, MIN_IMAGES_REQUIRED
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/training", tags=["Training"])


# =============================================================================
# HELPER: TrainingRun → Response
# =============================================================================

def _to_response(run: TrainingRun) -> TrainingRunResponse:
    """ORM ob'ektini Pydantic response schemaga aylantirish."""
    return TrainingRunResponse(
        id               = run.id,
        run_name         = run.run_name,
        status           = run.status,
        base_model_name  = run.base_model_name,
        epochs           = run.epochs,
        batch_size       = run.batch_size,
        img_size         = run.img_size,
        freeze_layers    = run.freeze_layers,
        dataset_info     = run.dataset_info,
        started_at       = run.started_at,
        completed_at     = run.completed_at,
        metrics          = run.metrics,
        error_message    = run.error_message,
        model_path       = run.model_path,
        is_deployed      = run.is_deployed,
        deployed_at      = run.deployed_at,
        notes            = run.notes,
        created_at       = run.created_at,
        updated_at       = run.updated_at,
        duration_seconds = run.duration_seconds,
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/dataset-stats",
    response_model=DatasetStatsResponse,
    summary="Yig'ilgan kadrlar statistikasi",
)
async def get_dataset_stats(
    _: CurrentUser,
) -> DatasetStatsResponse:
    """Training dataset statistikasini qaytarish."""
    collector = get_frame_collector()

    if collector is None:
        return DatasetStatsResponse(
            total_frames    = 0,
            min_required    = MIN_IMAGES_REQUIRED,
            is_ready        = False,
            cameras         = {},
            frames_dir      = settings.TRAINING_FRAMES_DIR,
            collector_stats = None,
        )

    stats  = collector.get_stats()
    total  = collector.count_collected_frames()
    cameras = {
        cam: count
        for cam, count in stats.get("cameras", {}).items()
    }

    return DatasetStatsResponse(
        total_frames    = total,
        min_required    = MIN_IMAGES_REQUIRED,
        is_ready        = total >= MIN_IMAGES_REQUIRED,
        cameras         = cameras,
        frames_dir      = str(stats.get("save_dir", settings.TRAINING_FRAMES_DIR)),
        collector_stats = stats,
    )


@router.get(
    "/runs",
    response_model=TrainingListResponse,
    summary="Barcha training runlar",
)
async def list_training_runs(
    limit:  int          = 50,
    offset: int          = 0,
    db:     AsyncSession = Depends(get_db),
    _: CurrentUser = None,
) -> TrainingListResponse:
    """Training run tarixi."""
    repo = TrainingRepository(db)
    runs = await repo.list_all(limit=limit, offset=offset)
    return TrainingListResponse(
        total = len(runs),
        items = [_to_response(r) for r in runs],
    )


@router.get(
    "/runs/{run_id}",
    response_model=TrainingRunResponse,
    summary="Bitta training run holati",
)
async def get_training_run(
    run_id: int,
    db:     AsyncSession = Depends(get_db),
    _: CurrentUser = None,
) -> TrainingRunResponse:
    """Run holati va natijalarini qaytarish."""
    repo = TrainingRepository(db)
    run  = await repo.get(run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training run #{run_id} topilmadi.",
        )
    return _to_response(run)


@router.post(
    "/runs",
    response_model=TrainingStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Yangi training boshlash",
)
async def start_training(
    body:  TrainingStartRequest,
    db:    AsyncSession = Depends(get_db),
    _: CurrentAdmin = None,
) -> TrainingStartResponse:
    """
    Training run ni yaratib Celery task ga topshirish.
    Faqat ADMIN roli uchun.
    """
    from workers.tasks.training_tasks import run_training_task

    # Dataset statistikasini tekshirish
    collector    = get_frame_collector()
    total_frames = collector.count_collected_frames() if collector else 0

    if total_frames < MIN_IMAGES_REQUIRED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Yetarli kadr yo'q: {total_frames} ta mavjud, "
                f"kamida {MIN_IMAGES_REQUIRED} ta kerak. "
                f"Detection pipeline ishlayotganda kadrlar yig'iladi."
            ),
        )

    # Run nomini avtomatik yaratish
    run_name = (body.run_name or "").strip() or (
        f"Run-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M')}"
    )

    # DB ga yozish
    repo = TrainingRepository(db)
    run  = await repo.create(
        run_name        = run_name,
        base_model_name = settings.YOLO_MODEL,
        epochs          = body.epochs,
        batch_size      = body.batch_size,
        img_size        = body.img_size,
        freeze_layers   = body.freeze_layers,
        notes           = body.notes or "",
    )
    await db.commit()

    # Celery task ga topshirish
    task = run_training_task.apply_async(
        kwargs={
            "run_id":      run.id,
            "auto_deploy": body.auto_deploy,
        },
        queue="training",
    )

    logger.info(
        f"[training] Run started: id={run.id}, name={run_name}, "
        f"task_id={task.id}"
    )

    return TrainingStartResponse(
        run_id   = run.id,
        run_name = run_name,
        task_id  = task.id,
        message  = (
            f"Training #{run.id} background da ishga tushirildi. "
            f"Dataset: {total_frames} kadr. "
            f"GET /api/v1/training/runs/{run.id} orqali holatni kuzating."
        ),
    )


@router.post(
    "/runs/{run_id}/deploy",
    response_model=TrainingDeployResponse,
    summary="Modelni ishlatishga olish (deploy)",
)
async def deploy_model(
    run_id: int,
    body:   TrainingDeployRequest,
    db:     AsyncSession = Depends(get_db),
    _: CurrentAdmin = None,
) -> TrainingDeployResponse:
    """
    Training run modelini production ga deploy qilish.
    Faqat ADMIN. Completed yoki Deployed run bo'lishi kerak.
    """
    repo = TrainingRepository(db)
    run  = await repo.get(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training run #{run_id} topilmadi.",
        )

    if run.status not in (TrainingStatus.COMPLETED, TrainingStatus.DEPLOYED):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"Faqat 'completed' yoki 'deployed' statusdagi run deploy qilinadi. "
                f"Hozirgi status: {run.status}"
            ),
        )

    if not run.model_path:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Model fayli yo'li saqlanmagan.",
        )

    # mAP50 tekshiruvi (force=False bo'lsa)
    if not body.force and run.map50 is not None:
        from app.services.ai.training_pipeline import TrainingPipeline
        deployed     = await repo.get_deployed()
        current_map50 = 0.0
        if deployed and deployed.map50 is not None:
            current_map50 = deployed.map50

        pipeline = TrainingPipeline(
            base_model_path = settings.TRAINING_BASE_MODEL_PATH,
            output_dir      = settings.TRAINING_MODELS_DIR,
        )
        if not pipeline.should_deploy(
            new_metrics   = _fake_metrics_from_run(run),
            current_map50 = current_map50,
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Yangi model mAP50 ({run.map50:.4f}) hozirgi modeldan "
                    f"yetarlicha yaxshi emas (hozirgi: {current_map50:.4f}). "
                    f"Majburan deploy uchun force=true yuboring."
                ),
            )

    # Modelni deploy joyiga nusxalash
    import shutil
    from pathlib import Path

    deploy_path = settings.TRAINING_DEPLOY_MODEL_PATH
    Path(deploy_path).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(run.model_path, deploy_path)

    # DB ni yangilash
    await repo.deploy(run_id)
    await db.commit()

    # YoloService ni yangi model bilan qayta yuklash
    try:
        await _reload_yolo_service(deploy_path)
        logger.info(f"[training] YOLO service reloaded: {deploy_path}")
    except Exception as exc:
        logger.error(f"[training] YOLO reload failed: {exc}", exc_info=True)
        # Deploy DB da muvaffaqiyatli — keyingi restart da yangi model yuklanadi

    logger.info(
        f"[training] Deployed: run_id={run_id} | "
        f"model={deploy_path} | mAP50={run.map50}"
    )

    return TrainingDeployResponse(
        run_id     = run_id,
        model_path = deploy_path,
        map50      = run.map50,
        message    = (
            f"Model muvaffaqiyatli deploy qilindi. "
            f"mAP50: {f'{run.map50:.4f}' if run.map50 else 'N/A'}. "
            f"Yangi kadrlar shu model bilan aniqlanadi."
        ),
    )


@router.delete(
    "/runs/{run_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Training runni o'chirish",
)
async def delete_training_run(
    run_id: int,
    db:     AsyncSession = Depends(get_db),
    _: CurrentAdmin = None,
) -> None:
    """
    Pending, failed yoki completed runni o'chirish.
    Deployed va aktiv training run o'chirib bo'lmaydi.
    """
    repo = TrainingRepository(db)
    run  = await repo.get(run_id)

    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training run #{run_id} topilmadi.",
        )

    if run.status in (TrainingStatus.DEPLOYED, TrainingStatus.TRAINING):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"'{run.status}' statusdagi run o'chirib bo'lmaydi. "
                f"Faqat 'pending', 'failed', 'completed' statuslar o'chiriladi."
            ),
        )

    _cleanup_run_files(run)
    await db.delete(run)
    await db.commit()
    logger.info(f"[training] Run deleted: id={run_id}")


# =============================================================================
# PRIVATE HELPERS
# =============================================================================

def _cleanup_run_files(run: TrainingRun) -> None:
    """Run ga tegishli disk fayllarini o'chirish."""
    import shutil
    from pathlib import Path

    if run.dataset_info:
        dataset_dir = run.dataset_info.get("dataset_dir")
        if dataset_dir and Path(dataset_dir).exists():
            shutil.rmtree(dataset_dir, ignore_errors=True)
            logger.debug(f"[training] Dataset cleaned: {dataset_dir}")

    if run.model_path:
        p = Path(run.model_path)
        if p.exists():
            p.unlink(missing_ok=True)
            logger.debug(f"[training] Model file cleaned: {run.model_path}")


async def _reload_yolo_service(new_model_path: str) -> None:
    """YoloService ni yangi model bilan qayta yuklash."""
    from pathlib import Path
    from app.services.ai.yolo_service import (
        shutdown_yolo_service,
        initialize_yolo_service,
    )

    settings.YOLO_MODEL       = Path(new_model_path).name
    settings.AI_TARGET_CLASSES = [0, 1]   # Custom model: cow=0, sheep=1

    await shutdown_yolo_service()
    await initialize_yolo_service()


def _fake_metrics_from_run(run: TrainingRun):
    """should_deploy() uchun TrainingMetrics-ga o'xshash ob'ekt yaratish."""
    from app.services.ai.training_pipeline import TrainingMetrics
    m = run.metrics or {}
    return TrainingMetrics(
        map50        = float(m.get("map50",       0.0)),
        map50_95     = float(m.get("map50_95",    0.0)),
        precision    = float(m.get("precision",   0.0)),
        recall       = float(m.get("recall",      0.0)),
        box_loss     = float(m.get("box_loss",    0.0)),
        cls_loss     = float(m.get("cls_loss",    0.0)),
        epochs_done  = int(m.get("epochs_done",   0)),
        best_epoch   = int(m.get("best_epoch",    0)),
        duration_sec = float(m.get("duration_sec", 0.0)),
    )