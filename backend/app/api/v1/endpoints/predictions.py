"""
Health Prediction API Endpoints — Sprint 13-14.

ENDPOINTS:
    GET  /predictions/farm-summary              — Ferma xavf xulosasi
    GET  /predictions/at-risk                   — Xavf ostidagi jonivorlar
    GET  /predictions/animal/{id}               — Bitta jonivor bashorati
    GET  /predictions/animal/{id}/history       — Jonivor bashorat tarixi
    POST /predictions/animal/{id}/predict       — Qo'lda bashorat (manager)
    POST /predictions/run-farm                  — Ferma-wide bashorat (admin)
    POST /predictions/train                     — Modelni qayta o'rgatish (admin)
    GET  /predictions/model-status              — Model holati

AVTORIZATSIYA:
    GET  endpoints: barcha autentifikatsiyalangan foydalanuvchilar
    POST endpoints: MANAGER yoki ADMIN roli
    train, run-farm: faqat ADMIN
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import (
    CurrentUser,
    CurrentManager,
    CurrentAdmin,
    get_current_active_user,
)
from app.core.exceptions import EntityNotFoundError, DatabaseError
from app.repositories.prediction_repository import PredictionRepository
from app.repositories.animal import AnimalRepository
from app.services.prediction_service import PredictionService, get_prediction_service
from app.schemas.prediction import (
    HealthPredictionResponse,
    PredictionFarmSummary,
    AnimalRiskSummary,
    PredictionHistory,
    PredictionHistoryPoint,
    TrainModelsRequest,
    TrainModelsResponse,
    ModelStatusResponse,
    EnsembleWeights,
    FeatureImportance,
    FarmPredictionRunResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/predictions",
    tags=["Health Predictions"],
    dependencies=[Depends(get_current_active_user)],
)


# ─── Farm Summary ──────────────────────────────────────────────────────────────

@router.get(
    "/farm-summary",
    response_model=PredictionFarmSummary,
    summary="Ferma xavf xulosasi",
    description="Bugungi sana uchun barcha jonivorlarning sog'liq xavf statistikasi.",
)
async def get_farm_summary(
    date: Optional[str] = Query(
        None,
        description="YYYY-MM-DD (None = bugun)",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> PredictionFarmSummary:
    """Ferma darajasidagi bashorat xulosasi."""
    target_date  = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repo         = PredictionRepository(db)
    animal_repo  = AnimalRepository(db)

    # DB summary
    summary = await repo.get_farm_summary(target_date)

    # At-risk jonivorlar ro'yxati (medium+)
    at_risk_preds = await repo.get_at_risk_animals(target_date, min_risk_level="medium")
    at_risk_list: list[AnimalRiskSummary] = []

    for pred in at_risk_preds[:20]:  # Maksimum 20 ta
        animal = await animal_repo.get_by_id(pred.animal_id)
        if not animal:
            continue
        at_risk_list.append(AnimalRiskSummary(
            animal_id       = pred.animal_id,
            tag_id          = animal.tag_id,
            name            = getattr(animal, "name", None),
            species         = str(animal.species).lower().replace("animalspecies.", ""),
            risk_level      = pred.risk_level,
            risk_score      = pred.risk_score,
            confidence      = pred.confidence,
            trend_direction = pred.trend_direction,
            top_risk_factor = (pred.risk_factors or [None])[0],
        ))

    return PredictionFarmSummary(
        date            = summary["date"],
        total_predicted = summary["total_predicted"],
        avg_risk_score  = summary["avg_risk_score"],
        max_risk_score  = summary["max_risk_score"],
        low_count       = summary["low_count"],
        medium_count    = summary["medium_count"],
        high_count      = summary["high_count"],
        critical_count  = summary["critical_count"],
        at_risk_animals = at_risk_list,
    )


# ─── At-Risk Animals ──────────────────────────────────────────────────────────

@router.get(
    "/at-risk",
    response_model=list[AnimalRiskSummary],
    summary="Xavf ostidagi jonivorlar",
)
async def get_at_risk_animals(
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    min_risk: str = Query(
        "medium",
        description="Minimal xavf darajasi: low | medium | high | critical",
        pattern=r"^(low|medium|high|critical)$",
    ),
    db: AsyncSession = Depends(get_db),
) -> list[AnimalRiskSummary]:
    """Muayyan kunda xavf darajasi belgilangan chegara ustidagi jonivorlar."""
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repo        = PredictionRepository(db)
    animal_repo = AnimalRepository(db)

    preds = await repo.get_at_risk_animals(target_date, min_risk_level=min_risk)
    result: list[AnimalRiskSummary] = []

    for pred in preds:
        animal = await animal_repo.get_by_id(pred.animal_id)
        if not animal:
            continue
        result.append(AnimalRiskSummary(
            animal_id       = pred.animal_id,
            tag_id          = animal.tag_id,
            name            = getattr(animal, "name", None),
            species         = str(animal.species).lower().replace("animalspecies.", ""),
            risk_level      = pred.risk_level,
            risk_score      = pred.risk_score,
            confidence      = pred.confidence,
            trend_direction = pred.trend_direction,
            top_risk_factor = (pred.risk_factors or [None])[0],
        ))

    return result


# ─── Single Animal Prediction ─────────────────────────────────────────────────

@router.get(
    "/animal/{animal_id}",
    response_model=HealthPredictionResponse,
    summary="Bitta jonivor bashorati",
)
async def get_animal_prediction(
    animal_id: int = Path(..., ge=1, description="Jonivor ID"),
    date: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> HealthPredictionResponse:
    """
    Jonivorning muayyan kundagi bashoratini qaytaradi.

    Agar DB da bashorat topilmasa → avtomatik hisoblaydi va saqlaydi.
    """
    target_date = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    repo        = PredictionRepository(db)

    # DB da mavjudmi?
    pred = await repo.get_by_animal_and_date(animal_id, target_date)

    if pred is None:
        # Yo'q → hisoblash
        service = get_prediction_service(db)
        try:
            pred = await service.predict_for_animal(
                animal_id=animal_id,
                save=True,
                target_date=target_date,
            )
            await db.commit()
        except EntityNotFoundError as exc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(exc),
            )

    return HealthPredictionResponse.from_orm_obj(pred)


# ─── Prediction History ───────────────────────────────────────────────────────

@router.get(
    "/animal/{animal_id}/history",
    response_model=PredictionHistory,
    summary="Jonivor bashorat tarixi",
)
async def get_animal_prediction_history(
    animal_id: int = Path(..., ge=1),
    days: int = Query(30, ge=7, le=90, description="Necha kunlik tarix"),
    db: AsyncSession = Depends(get_db),
) -> PredictionHistory:
    """Jonivorning oxirgi N kunlik risk trend tarixi."""
    repo    = PredictionRepository(db)
    history = await repo.get_history_for_animal(animal_id, days=days)

    points = [
        PredictionHistoryPoint(
            date           = h.prediction_date,
            risk_score     = h.risk_score,
            risk_level     = h.risk_level,
            adi_projection = h.predicted_adi_7day,
        )
        for h in reversed(history)  # eski → yangi
    ]

    return PredictionHistory(
        animal_id = animal_id,
        days      = days,
        history   = points,
    )


# ─── Manual Predict (single animal) ──────────────────────────────────────────

@router.post(
    "/animal/{animal_id}/predict",
    response_model=HealthPredictionResponse,
    summary="Qo'lda bashorat hisoblash",
    status_code=status.HTTP_200_OK,
)
async def predict_animal_manual(
    animal_id: int = Path(..., ge=1),
    db: AsyncSession = Depends(get_db),
    _: CurrentManager = None,
) -> HealthPredictionResponse:
    """
    Jonivor uchun bashoratni qo'lda hisoblaydi (va DB ni yangilaydi).

    MANAGER yoki ADMIN roli talab etiladi.
    """
    service = get_prediction_service(db)
    try:
        pred = await service.predict_for_animal(
            animal_id=animal_id,
            save=True,
        )
        await db.commit()
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Animal ID {animal_id} topilmadi",
        )
    except Exception as exc:
        await db.rollback()
        logger.error(f"[predictions] Manual predict failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bashorat hisoblashda xato yuz berdi",
        )

    return HealthPredictionResponse.from_orm_obj(pred)


# ─── Farm-wide Run ────────────────────────────────────────────────────────────

@router.post(
    "/run-farm",
    response_model=FarmPredictionRunResponse,
    summary="Barcha jonivorlar uchun bashorat",
    status_code=status.HTTP_202_ACCEPTED,
)
async def run_farm_predictions(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: CurrentAdmin = None,
) -> FarmPredictionRunResponse:
    """
    Barcha aktiv jonivorlar uchun bashoratni hisoblaydi.

    Faqat ADMIN. Background task — natija darhol qaytarilmaydi.
    """
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    service = get_prediction_service(db)

    # Immediate run (asinxron bo'lsa ham await qilamiz — Celery yo'q)
    try:
        result = await service.predict_all_active(target_date=today)
        await db.commit()
        return FarmPredictionRunResponse(**result)
    except Exception as exc:
        await db.rollback()
        logger.error(f"[predictions] Farm run failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ferma bashoratini hisoblashda xato",
        )


# ─── Train Models ─────────────────────────────────────────────────────────────

@router.post(
    "/train",
    response_model=TrainModelsResponse,
    summary="ML modellarni qayta o'rgatish",
    status_code=status.HTTP_200_OK,
)
async def train_prediction_models(
    body: TrainModelsRequest,
    db: AsyncSession = Depends(get_db),
    _: CurrentAdmin = None,
) -> TrainModelsResponse:
    """
    RandomForest va IsolationForest modellarini qayta o'rgatadi.

    Faqat ADMIN. ~5-30 soniya davom etadi.
    """
    service = get_prediction_service(db)

    try:
        result = await service.train_models(days_back=body.days_back)
    except Exception as exc:
        logger.error(f"[predictions] Training failed: {exc}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Model o'rgatishda xato: {exc}",
        )

    top_features = [
        FeatureImportance(feature=f["feature"], importance=f["importance"])
        for f in result.get("top_features", [])
    ]

    return TrainModelsResponse(
        rf_trained   = result.get("rf_trained", False),
        iso_trained  = result.get("iso_trained", False),
        n_samples    = result.get("n_samples", 0),
        n_positive   = result.get("n_positive", 0),
        rf_accuracy  = result.get("rf_accuracy", 0.0),
        top_features = top_features,
        duration_sec = result.get("duration_sec", 0.0),
        trained_at   = result.get("trained_at"),
        message      = result.get("message"),
    )


# ─── Model Status ─────────────────────────────────────────────────────────────

@router.get(
    "/model-status",
    response_model=ModelStatusResponse,
    summary="ML model holati",
)
async def get_model_status(
    db: AsyncSession = Depends(get_db),
) -> ModelStatusResponse:
    """Prediction model versiyasi, o'rgatilgan/o'rgatilmagan va ensemble og'irliklari."""
    service = get_prediction_service(db)
    stats   = service.get_model_stats()

    status_msg = "✅ RF + ISO tayyor" if stats["rf_trained"] else (
        "⚠️ Faqat Rule-based + ISO (RF o'rgatilmagan)"
    )

    return ModelStatusResponse(
        rf_trained          = stats["rf_trained"],
        iso_trained         = stats["iso_trained"],
        trained_at          = stats["trained_at"],
        n_training_samples  = stats["n_training_samples"],
        model_version       = stats["model_version"],
        ensemble_weights    = EnsembleWeights(**stats["ensemble_weights"]),
        top_features        = [
            FeatureImportance(**f) for f in stats["top_features"]
        ],
        status_message      = status_msg,
    )