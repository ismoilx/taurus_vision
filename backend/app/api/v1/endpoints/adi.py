"""
ADI API Endpoints — Refactored with Repository Pattern.

ARXITEKTURA O'ZGARISHI (Sprint 5):
    Oldingi: endpoint → to'g'ridan DB query
    Yangi:   endpoint → ADIRepository / AnimalRepository

ENDPOINTS:
    GET  /adi/farm-summary              — Ferma umumiy ADI holati
    GET  /adi/animal/{animal_id}        — Bitta jonivor ADI (bugungi)
    GET  /adi/animal/{animal_id}/trend  — Jonivor ADI trend tarixi
    POST /adi/calculate                 — Qo'lda hisoblashni ishga tushirish
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.core.exceptions import EntityNotFoundError
from app.models.animal import AnimalStatus
from app.repositories.adi_repository import ADIRepository
from app.repositories.animal import AnimalRepository
from app.schemas.adi import (
    ADILogResponse,
    ADITrendResponse,
    ADITrendPoint,
    ADIFarmSummary,
    ADIFarmSummaryItem,
    ADICalculationRequest,
    ADICalculationResult,
    ADIBatchCalculationResponse,
)
from app.services.adi_service import ADIService
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/adi", tags=["ADI"], dependencies=[Depends(get_current_active_user)])


# ------------------------------------------------------------------ #
# FARM SUMMARY                                                         #
# ------------------------------------------------------------------ #

@router.get(
    "/farm-summary",
    response_model=ADIFarmSummary,
    summary="Ferma umumiy ADI holati",
)
async def get_farm_summary(
    date: Optional[str] = Query(None, description="YYYY-MM-DD. None = bugun",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> ADIFarmSummary:
    """Ferma darajasidagi ADI xulosasi."""
    service     = ADIService(db)
    adi_repo    = ADIRepository(db)
    animal_repo = AnimalRepository(db)
    date_str    = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw = await service.get_farm_summary(target_date=date_str)

    if raw.get("total_animals", 0) == 0:
        return ADIFarmSummary(
            date=date_str, total_animals=0, healthy_count=0, average_count=0,
            warning_count=0, critical_count=0, healthy_pct=0.0, average_pct=0.0,
            warning_pct=0.0, critical_pct=0.0, farm_adi_score=0.0, needs_attention=[],
        )

    attention_items: list[ADIFarmSummaryItem] = []
    for item in raw.get("needs_attention", []):
        animal = await animal_repo.get_by_id(item["animal_id"])
        if animal:
            trend = await _compute_trend(adi_repo, animal.id, date_str)
            attention_items.append(ADIFarmSummaryItem(
                animal_id=animal.id, tag_id=animal.tag_id,
                species=animal.species.value, adi_score=item["adi_score"],
                category=item["category"], trend=trend, last_updated=date_str,
            ))

    attention_items.sort(key=lambda x: 0 if x.category == "critical" else 1)

    return ADIFarmSummary(
        date=date_str,
        total_animals=raw["total_animals"],
        healthy_count=raw["healthy_count"],
        average_count=raw["average_count"],
        warning_count=raw["warning_count"],
        critical_count=raw["critical_count"],
        healthy_pct=raw["healthy_pct"],
        average_pct=raw["average_pct"],
        warning_pct=raw["warning_pct"],
        critical_pct=raw["critical_pct"],
        farm_adi_score=raw["farm_adi_score"],
        needs_attention=attention_items,
    )


# ------------------------------------------------------------------ #
# ANIMAL ADI                                                           #
# ------------------------------------------------------------------ #

@router.get(
    "/animal/{animal_id}",
    response_model=ADILogResponse,
    summary="Jonivor bugungi ADI",
    responses={404: {"description": "Jonivor topilmadi yoki hisoblanmagan"}},
)
async def get_animal_adi(
    animal_id: int,
    date: Optional[str] = Query(None, description="YYYY-MM-DD. None = bugun",
                                pattern=r"^\d{4}-\d{2}-\d{2}$"),
    db: AsyncSession = Depends(get_db),
) -> ADILogResponse:
    """Bitta jonivorning ADI natijasini qaytaradi."""
    date_str    = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    animal_repo = AnimalRepository(db)
    adi_repo    = ADIRepository(db)

    animal = await animal_repo.get_by_id(animal_id)
    if not animal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Jonivor {animal_id} topilmadi")

    log = await adi_repo.get_by_animal_and_date(animal_id, date_str)
    if log:
        return ADILogResponse.from_orm_flat(log)
    
    # Testlar kutayotganidek: agar so'ralgan sanada hisoblanmagan bo'lsa 404 qaytaramiz
    # Avtomatik hisoblash faqat Celery yoki POST orqali bo'lishi kerak.
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Jonivor {animal_id} uchun {date_str} sanasiga ADI hisoblanmagan")


# ------------------------------------------------------------------ #
# TREND                                                                #
# ------------------------------------------------------------------ #

@router.get(
    "/animal/{animal_id}/trend",
    response_model=ADITrendResponse,
    summary="Jonivor ADI trend tarixi",
    responses={404: {"description": "Jonivor topilmadi"}},
)
async def get_animal_trend(
    animal_id: int,
    days: int = Query(30, ge=7, le=365, description="Necha kunlik tarix (7—365)"),
    db: AsyncSession = Depends(get_db),
) -> ADITrendResponse:
    """Jonivorning ADI trend tarixini qaytaradi."""
    animal_repo = AnimalRepository(db)
    animal = await animal_repo.get_by_id(animal_id)
    if not animal:
        raise HTTPException(status_code=404, detail=f"Jonivor {animal_id} topilmadi")

    service = ADIService(db)
    logs    = await service.get_animal_trend(animal_id=animal_id, days=days)

    if not logs:
        return ADITrendResponse(
            animal_id=animal_id, animal_tag=animal.tag_id, period_days=days,
            trend=[], avg_score=0.0, min_score=0.0, max_score=0.0, current=None,
        )

    trend_points = [
        ADITrendPoint(date=log.calculation_date, score=log.adi_score, category=log.category)
        for log in reversed(logs)
    ]
    scores = [p.score for p in trend_points]

    return ADITrendResponse(
        animal_id=animal_id, animal_tag=animal.tag_id, period_days=days,
        trend=trend_points,
        avg_score=round(sum(scores) / len(scores), 2),
        min_score=round(min(scores), 2),
        max_score=round(max(scores), 2),
        current=ADILogResponse.from_orm_flat(logs[0]),
    )


# ------------------------------------------------------------------ #
# CALCULATE (manual trigger)                                           #
# ------------------------------------------------------------------ #

@router.post(
    "/calculate",
    response_model=ADIBatchCalculationResponse,
    summary="ADI hisoblashni ishga tushirish",
)
async def trigger_calculation(
    request: ADICalculationRequest,
    db: AsyncSession = Depends(get_db),
) -> ADIBatchCalculationResponse:
    """Qo'lda ADI hisoblash — testing va debug uchun."""
    import time
    start_time  = time.monotonic()
    service     = ADIService(db)
    animal_repo = AnimalRepository(db)
    results: list[ADICalculationResult] = []

    target_date = request.target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if request.animal_id:
        # Bitta jonivor
        try:
            adi = await service.calculate_for_animal(
                animal_id=request.animal_id,
                target_date=target_date,
                force_recalculate=request.force_recalculate,
            )
            results.append(ADICalculationResult(
                success=True, animal_id=request.animal_id,
                calculation_date=adi.calculation_date,
                adi_score=float(adi.adi_score) if adi.adi_score is not None else 0.0,
                category=adi.category,
                data_quality=adi.data_quality,
            ))
        except EntityNotFoundError:
            raise HTTPException(status_code=404,
                                detail=f"Jonivor {request.animal_id} topilmadi")
        except Exception as e:
            results.append(ADICalculationResult(
                success=False, animal_id=request.animal_id,
                calculation_date=target_date, error=str(e),
            ))
    else:
        # Barcha aktiv jonivorlar
        animals    = await animal_repo.get_all(status=AnimalStatus.ACTIVE, limit=1000)
        animal_ids = [a.id for a in animals]

        for animal_id in animal_ids:
            try:
                adi = await service.calculate_for_animal(
                    animal_id=animal_id,
                    target_date=target_date,
                    force_recalculate=request.force_recalculate,
                )
                results.append(ADICalculationResult(
                    success=True, animal_id=animal_id,
                    calculation_date=adi.calculation_date,
                    adi_score=adi.adi_score, category=adi.category,
                    data_quality=adi.data_quality,
                ))
            except Exception as e:
                results.append(ADICalculationResult(
                    success=False, animal_id=animal_id,
                    calculation_date=target_date, error=str(e),
                ))

    duration_ms = (time.monotonic() - start_time) * 1000
    
    # AttributeError oldini olish (skipped xususiyati yo'q bo'lishi mumkin)
    skipped_count = sum(1 for r in results if getattr(r, 'skipped', False))
    failed_count = sum(1 for r in results if not r.success and not getattr(r, 'skipped', False))

    return ADIBatchCalculationResponse(
        total=len(results),
        success=sum(1 for r in results if r.success),
        failed=failed_count,
        skipped=skipped_count,
        results=results,
        duration_ms=round(duration_ms, 2),
    )


# ------------------------------------------------------------------ #
# PRIVATE HELPERS                                                      #
# ------------------------------------------------------------------ #

async def _compute_trend(
    adi_repo: ADIRepository,
    animal_id: int,
    today: str,
) -> str:
    """
    Bugungi va kechagi ADI taqqoslab trend aniqlash.
    Repository orqali — to'g'ridan DB query yo'q.

    Returns: "up" | "down" | "stable" | "unknown"
    """
    today_log       = await adi_repo.get_by_animal_and_date(animal_id, today)
    today_score     = today_log.adi_score if today_log else None
    yesterday_score = await adi_repo.get_previous_score(animal_id, today)

    if today_score is None or yesterday_score is None:
        return "unknown"

    diff = today_score - yesterday_score
    if diff >= 5:
        return "up"
    elif diff <= -5:
        return "down"
    else:
        return "stable"


async def _trigger_alerts_if_needed(
    db: AsyncSession,
    adi_repo: ADIRepository,
    animal_id: int,
    adi_score: float,
    category: str,
    date_str: str,
    feeding_component: Optional[Any] = None,
) -> None:
    """
    ADI hisoblangandan keyin alert servisini chaqirish.
    Kechagi scoreni ADIRepository orqali oladi.
    """
    alert_service = AlertService(db)
    prev_score    = await adi_repo.get_previous_score(animal_id, date_str)

    feeding_score = (
        feeding_component.score
        if feeding_component and hasattr(feeding_component, "score")
        else None
    )

    await alert_service.process_adi_result(
        animal_id=animal_id,
        adi_score=adi_score,
        category=category,
        prev_score=prev_score,
        feeding_score=feeding_score,
    )