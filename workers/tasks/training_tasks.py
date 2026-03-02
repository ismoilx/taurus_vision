"""
Taurus Vision — Training Celery Task (Sprint 15-16)

YOLO fine-tuning ni background da to'liq boshqaradigan Celery task.

LIFECYCLE:
    PENDING → BUILDING (dataset) → TRAINING (fine-tune) → EVALUATING →
    COMPLETED [→ DEPLOYED (auto_deploy=True bo'lsa)]
              → FAILED (xato bo'lsa)

PATTERN:
    DatabaseTask base class → thread-safe async DB session.
    Har bir holat o'zgarishi darhol DB ga yoziladi → frontend real-vaqt kuzatishi.

QUEUE: training (alohida worker concurrency=1 bo'lishi kerak —
       CPU intensive training parallel bo'lmasligi lozim)

USAGE:
    task = run_training_task.apply_async(
        kwargs={"run_id": 42, "auto_deploy": False},
        queue="training",
    )

CELERY BEAT (manual trigger yo'q — faqat API orqali):
    Training task beat schedule da emas, faqat API so'rovida ishga tushadi.
"""

import logging
from datetime import datetime, timezone
from pathlib import Path

from workers.celery_app import celery_app
from workers.tasks.adi_tasks import DatabaseTask   # Thread-safe async base

logger = logging.getLogger(__name__)


# =============================================================================
# ASOSIY TRAINING TASK
# =============================================================================

@celery_app.task(
    name           = "training.run",
    queue          = "training",
    bind           = True,
    base           = DatabaseTask,
    max_retries    = 0,          # Training qayta urinilmaydi — deterministik
    soft_time_limit = 10800,     # 3 soat soft limit (CPU da yirik model)
    time_limit      = 11400,     # 3 soat 10 daqiqa hard limit
    acks_late       = True,
)
def run_training_task(
    self,
    run_id:      int,
    auto_deploy: bool = False,
) -> dict:
    """
    To'liq YOLO fine-tuning jarayoni.

    Bosqichlar:
        1. TrainingRun statusini BUILDING ga o'zgartirish
        2. Dataset yaratish (DatasetBuilder)
        3. Statusni TRAINING ga o'zgartirish
        4. Fine-tuning (TrainingPipeline)
        5. Statusni EVALUATING ga o'zgartirish
        6. Natijalarni saqlash
        7. auto_deploy=True va yetarli mAP50 bo'lsa → DEPLOY
        8. Statusni COMPLETED (yoki DEPLOYED) ga o'zgartirish

    Args:
        run_id:      TrainingRun DB yozuvi ID si
        auto_deploy: True → mAP50 yetarli bo'lsa avtomatik deploy

    Returns:
        {
            "run_id":       int,
            "status":       str,
            "map50":        float,
            "map50_95":     float,
            "precision":    float,
            "recall":       float,
            "n_train":      int,
            "n_val":        int,
            "duration_sec": float,
            "deployed":     bool,
            "model_path":   str,
        }
    """
    logger.info(
        f"[task:training] Starting | run_id={run_id} | auto_deploy={auto_deploy}"
    )

    return self.run_async(
        _run_training_async(
            task        = self,
            run_id      = run_id,
            auto_deploy = auto_deploy,
        )
    )


# =============================================================================
# ASYNC IMPLEMENTATSIYA
# =============================================================================

async def _run_training_async(
    task:        "run_training_task",
    run_id:      int,
    auto_deploy: bool,
) -> dict:
    """
    Training lifecycle async implementatsiyasi.

    Har bir bosqichda DB yangilanadi — frontend real-vaqt kuzatishi mumkin.
    Har qanday xatoda FAILED statusiga o'tib, xatoni DB ga yozadi.
    """
    from app.core.database import AsyncSessionLocal
    from app.config import settings
    from app.models.training_run import TrainingStatus
    from app.repositories.training_repository import TrainingRepository
    from app.services.ai.dataset_builder import DatasetBuilder, DatasetBuildError
    from app.services.ai.training_pipeline import TrainingPipeline, TrainingPipelineError

    import time
    start_time = time.monotonic()

    # ─── DB session va repo ───────────────────────────────────────────────────
    async with AsyncSessionLocal() as db:
        repo = TrainingRepository(db)

        # Run mavjudligini tekshirish
        run = await repo.get(run_id)
        if not run:
            logger.error(f"[task:training] Run #{run_id} topilmadi — task bekor qilindi")
            return {"run_id": run_id, "status": "not_found", "error": "Run not found"}

        # ─── BOSQICH 1: BUILDING (dataset yaratish) ───────────────────────────
        try:
            await repo.set_status(run_id, TrainingStatus.BUILDING)
            await db.commit()
            logger.info(f"[task:training] Status: BUILDING | run_id={run_id}")

            builder = DatasetBuilder(
                frames_dir   = settings.TRAINING_FRAMES_DIR,
                datasets_dir = settings.TRAINING_DATASETS_DIR,
            )
            dataset_info = builder.build(run_id=run_id)

            await repo.set_dataset_info(run_id, dataset_info.to_dict())
            await db.commit()

            logger.info(
                f"[task:training] Dataset ready | "
                f"train={dataset_info.n_train} | val={dataset_info.n_val}"
            )

        except DatasetBuildError as exc:
            error_msg = str(exc)
            logger.error(f"[task:training] Dataset build failed: {error_msg}")
            await repo.set_status(run_id, TrainingStatus.FAILED, error=error_msg)
            await db.commit()
            return {
                "run_id": run_id,
                "status": "failed",
                "error":  error_msg,
            }
        except Exception as exc:
            error_msg = f"Kutilmagan xato (dataset): {exc}"
            logger.error(f"[task:training] {error_msg}", exc_info=True)
            await repo.set_status(run_id, TrainingStatus.FAILED, error=error_msg)
            await db.commit()
            return {"run_id": run_id, "status": "failed", "error": error_msg}

        # ─── BOSQICH 2: TRAINING (fine-tuning) ───────────────────────────────
        try:
            # run ob'ektini yangi session dan olish (flush dan keyin)
            run = await repo.get(run_id)

            await repo.set_status(run_id, TrainingStatus.TRAINING)
            await db.commit()
            logger.info(f"[task:training] Status: TRAINING | run_id={run_id}")

            pipeline = TrainingPipeline(
                base_model_path = settings.TRAINING_BASE_MODEL_PATH,
                output_dir      = settings.TRAINING_MODELS_DIR,
            )
            metrics = pipeline.train(
                yaml_path  = dataset_info.yaml_path,
                run_id     = run_id,
                epochs     = run.epochs,
                batch_size = run.batch_size,
                img_size   = run.img_size,
                freeze     = run.freeze_layers,
            )

            logger.info(
                f"[task:training] Training complete | "
                f"mAP50={metrics.map50:.4f} | "
                f"precision={metrics.precision:.4f} | "
                f"recall={metrics.recall:.4f} | "
                f"epochs={metrics.epochs_done} | "
                f"duration={metrics.duration_sec:.0f}s"
            )

        except TrainingPipelineError as exc:
            error_msg = str(exc)
            logger.error(f"[task:training] Training failed: {error_msg}")
            await repo.set_status(run_id, TrainingStatus.FAILED, error=error_msg)
            await db.commit()
            return {
                "run_id": run_id,
                "status": "failed",
                "error":  error_msg,
            }
        except Exception as exc:
            error_msg = f"Kutilmagan xato (training): {exc}"
            logger.error(f"[task:training] {error_msg}", exc_info=True)
            await repo.set_status(run_id, TrainingStatus.FAILED, error=error_msg)
            await db.commit()
            return {"run_id": run_id, "status": "failed", "error": error_msg}

        # ─── BOSQICH 3: EVALUATING (natijalarni saqlash) ─────────────────────
        try:
            await repo.set_status(run_id, TrainingStatus.EVALUATING)
            await db.commit()

            # Model faylini aniqlash
            model_path = pipeline.get_model_path(run_id)
            if not model_path:
                raise TrainingPipelineError(
                    f"best.pt fayli topilmadi. Training to'g'ri yakunlanmagan."
                )

            # Natijalarni DB ga yozish
            await repo.set_metrics(
                run_id     = run_id,
                metrics    = {
                    "map50":       round(metrics.map50,     4),
                    "map50_95":    round(metrics.map50_95,  4),
                    "precision":   round(metrics.precision, 4),
                    "recall":      round(metrics.recall,    4),
                    "box_loss":    round(metrics.box_loss,  4),
                    "cls_loss":    round(metrics.cls_loss,  4),
                    "epochs_done": metrics.epochs_done,
                    "best_epoch":  metrics.best_epoch,
                    "duration_sec": metrics.duration_sec,
                },
                model_path = model_path,
            )
            await db.commit()
            logger.info(f"[task:training] Metrics saved | model={model_path}")

        except Exception as exc:
            error_msg = f"Kutilmagan xato (evaluation): {exc}"
            logger.error(f"[task:training] {error_msg}", exc_info=True)
            await repo.set_status(run_id, TrainingStatus.FAILED, error=error_msg)
            await db.commit()
            return {"run_id": run_id, "status": "failed", "error": error_msg}

        # ─── BOSQICH 4: AUTO-DEPLOY (ixtiyoriy) ──────────────────────────────
        deployed = False
        if auto_deploy:
            try:
                # Hozirgi deployed model mAP50 sini olish
                current_run  = await repo.get_deployed()
                current_map50 = 0.0
                if current_run and current_run.map50 is not None:
                    current_map50 = current_run.map50

                if pipeline.should_deploy(metrics, current_map50):
                    deploy_path = settings.TRAINING_DEPLOY_MODEL_PATH
                    pipeline.deploy(
                        run_id            = run_id,
                        deploy_model_path = deploy_path,
                    )
                    await repo.deploy(run_id)
                    await db.commit()
                    deployed = True

                    # YoloService ni yangilash
                    try:
                        from app.services.ai.yolo_service import (
                            shutdown_yolo_service,
                            initialize_yolo_service,
                        )
                        from pathlib import Path
                        settings.YOLO_MODEL = Path(deploy_path).name
                        await shutdown_yolo_service()
                        await initialize_yolo_service()
                        logger.info(
                            f"[task:training] YOLO service reloaded: {deploy_path}"
                        )
                    except Exception as reload_exc:
                        # Reload xatosi — deploy muvaffaqiyatli, ammo service restart kerak
                        logger.warning(
                            f"[task:training] YOLO reload warning (restart required): "
                            f"{reload_exc}"
                        )

                    logger.info(
                        f"[task:training] Auto-deployed | "
                        f"mAP50={metrics.map50:.4f} > {current_map50:.4f}"
                    )
                else:
                    logger.info(
                        f"[task:training] Auto-deploy skipped: "
                        f"mAP50={metrics.map50:.4f} ≤ {current_map50:.4f} + threshold"
                    )
            except Exception as exc:
                # Deploy xatosi — COMPLETED sifatida saqlashda davom etamiz
                logger.error(f"[task:training] Auto-deploy error: {exc}", exc_info=True)

        # ─── BOSQICH 5: COMPLETED ─────────────────────────────────────────────
        if not deployed:
            await repo.set_status(run_id, TrainingStatus.COMPLETED)
            await db.commit()

        # Yig'ilgan framlarni tozalash (disk tejash) — ixtiyoriy
        try:
            pipeline.cleanup_run(run_id)
        except Exception as cleanup_exc:
            logger.debug(f"[task:training] Cleanup warning: {cleanup_exc}")

        total_duration = time.monotonic() - start_time

        final_status = "deployed" if deployed else "completed"
        logger.info(
            f"[task:training] DONE | run_id={run_id} | "
            f"status={final_status} | "
            f"mAP50={metrics.map50:.4f} | "
            f"total_duration={total_duration:.0f}s"
        )

        return {
            "run_id":       run_id,
            "status":       final_status,
            "map50":        round(metrics.map50,     4),
            "map50_95":     round(metrics.map50_95,  4),
            "precision":    round(metrics.precision, 4),
            "recall":       round(metrics.recall,    4),
            "n_train":      dataset_info.n_train,
            "n_val":        dataset_info.n_val,
            "duration_sec": round(total_duration,    1),
            "deployed":     deployed,
            "model_path":   model_path,
        }


# =============================================================================
# TOZALASH TASK (Beat schedule orqali Yakshanba da ishlaydi)
# =============================================================================

@celery_app.task(
    name           = "training.cleanup_old_runs",
    queue          = "maintenance",
    bind           = True,
    base           = DatabaseTask,
    max_retries    = 2,
    default_retry_delay = 300,
    soft_time_limit = 120,
    time_limit      = 180,
)
def cleanup_old_training_runs(self, keep_days: int = 30) -> dict:
    """
    Eski (completed/failed) training run yozuvlarini va ularga tegishli
    fayl tizimi resurslarini tozalaydi.

    Har hafta Yakshanba 04:30 UTC da beat tomonidan chaqiriladi.
    Deployed run lar hech qachon o'chirilmaydi.

    Args:
        keep_days: Necha kunlik runlarni saqlash (default: 30)

    Returns:
        {"deleted_db": int, "errors": int}
    """
    logger.info(f"[task:training.cleanup] Starting | keep_days={keep_days}")

    return self.run_async(_cleanup_old_runs_async(keep_days=keep_days))


async def _cleanup_old_runs_async(keep_days: int) -> dict:
    """Eski training run larni tozalash async implementatsiyasi."""
    from datetime import timedelta
    from app.core.database import AsyncSessionLocal
    from app.models.training_run import TrainingRun, TrainingStatus
    from app.repositories.training_repository import TrainingRepository
    from sqlalchemy import select

    cutoff     = datetime.now(timezone.utc) - timedelta(days=keep_days)
    deleted_db = 0
    errors     = 0

    async with AsyncSessionLocal() as db:
        # Eski, deployed bo'lmagan, yakunlangan runlar
        result = await db.execute(
            select(TrainingRun).where(
                TrainingRun.is_deployed == False,            # noqa: E712
                TrainingRun.status.in_([
                    TrainingStatus.COMPLETED,
                    TrainingStatus.FAILED,
                ]),
                TrainingRun.created_at < cutoff,
            )
        )
        old_runs = result.scalars().all()

        for run in old_runs:
            try:
                # Dataset va model fayllarini o'chirish
                import shutil
                from pathlib import Path

                if run.dataset_info:
                    dataset_dir = run.dataset_info.get("dataset_dir")
                    if dataset_dir and Path(dataset_dir).exists():
                        shutil.rmtree(dataset_dir, ignore_errors=True)

                if run.model_path:
                    model_path = Path(run.model_path)
                    if model_path.exists():
                        model_path.unlink(missing_ok=True)

                await db.delete(run)
                deleted_db += 1

            except Exception as exc:
                logger.warning(
                    f"[task:training.cleanup] Run #{run.id} tozalashda xato: {exc}"
                )
                errors += 1

        await db.commit()

    logger.info(
        f"[task:training.cleanup] Done | deleted={deleted_db} | errors={errors}"
    )
    return {"deleted_db": deleted_db, "errors": errors, "keep_days": keep_days}