"""
ADI API Endpoints.

Animal Development Index uchun REST API.

ENDPOINTS:
    GET  /adi/farm-summary              — Ferma umumiy ADI holati
    GET  /adi/animal/{animal_id}        — Bitta jonivor ADI (bugungi)
    GET  /adi/animal/{animal_id}/trend  — Jonivor ADI trend tarixi
    POST /adi/calculate                 — Qo'lda hisoblashni ishga tushirish
    POST /adi/calculate/{animal_id}     — Bitta jonivor uchun hisoblash
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.models.adi_log import ADILog
from app.models.animal import Animal, AnimalStatus
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

router = APIRouter(prefix="/adi", tags=["ADI"])


# ------------------------------------------------------------------ #
# FARM SUMMARY                                                         #
# ------------------------------------------------------------------ #

@router.get(
    "/farm-summary",
    response_model=ADIFarmSummary,
    summary="Ferma umumiy ADI holati",
    description=(
        "Bugungi yoki berilgan sana uchun butun ferma bo'yicha "
        "ADI xulosasini qaytaradi. Dashboard asosiy widget uchun."
    ),
)
async def get_farm_summary(
    date: Optional[str] = Query(
        None,
        description="YYYY-MM-DD format. None = bugun",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> ADIFarmSummary:
    """Ferma darajasidagi ADI xulosasi."""

    service = ADIService(db)
    date_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    raw = await service.get_farm_summary(target_date=date_str)

    if raw.get("total_animals", 0) == 0:
        return ADIFarmSummary(
            date=date_str,
            total_animals=0,
            healthy_count=0,
            average_count=0,
            warning_count=0,
            critical_count=0,
            healthy_pct=0.0,
            average_pct=0.0,
            warning_pct=0.0,
            critical_pct=0.0,
            farm_adi_score=0.0,
            needs_attention=[],
        )

    # needs_attention uchun tag_id larni olish
    attention_items: list[ADIFarmSummaryItem] = []
    for item in raw.get("needs_attention", []):
        stmt = select(Animal).where(Animal.id == item["animal_id"])
        result = await db.execute(stmt)
        animal = result.scalar_one_or_none()
        if animal:
            # Trend hisoblash: bugungi vs kechagi
            trend = await _compute_trend(db, animal.id, date_str)
            attention_items.append(
                ADIFarmSummaryItem(
                    animal_id=   animal.id,
                    tag_id=      animal.tag_id,
                    species=     animal.species.value,
                    adi_score=   item["adi_score"],
                    category=    item["category"],
                    trend=       trend,
                    last_updated=date_str,
                )
            )

    # Severity bo'yicha sort: critical birinchi
    attention_items.sort(
        key=lambda x: (
            0 if x.category == "critical" else 1
        )
    )

    return ADIFarmSummary(
        date=           date_str,
        total_animals=  raw["total_animals"],
        healthy_count=  raw["healthy_count"],
        average_count=  raw["average_count"],
        warning_count=  raw["warning_count"],
        critical_count= raw["critical_count"],
        healthy_pct=    raw["healthy_pct"],
        average_pct=    raw["average_pct"],
        warning_pct=    raw["warning_pct"],
        critical_pct=   raw["critical_pct"],
        farm_adi_score= raw["farm_adi_score"],
        needs_attention=attention_items,
    )


# ------------------------------------------------------------------ #
# ANIMAL ADI                                                           #
# ------------------------------------------------------------------ #

@router.get(
    "/animal/{animal_id}",
    response_model=ADILogResponse,
    summary="Jonivor bugungi ADI",
    responses={
        404: {"description": "Jonivor topilmadi"},
        204: {"description": "Bugun uchun ADI hali hisoblanmagan"},
    },
)
async def get_animal_adi(
    animal_id: int,
    date: Optional[str] = Query(
        None,
        description="YYYY-MM-DD. None = bugun",
        regex=r"^\d{4}-\d{2}-\d{2}$",
    ),
    db: AsyncSession = Depends(get_db),
) -> ADILogResponse:
    """
    Bitta jonivorning ADI natijasini qaytaradi.

    Agar berilgan sana uchun ADI hali hisoblanmagan bo'lsa,
    hozir hisoblab qaytaradi.
    """
    date_str = date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Jonivor mavjudligini tekshirish
    stmt = select(Animal).where(Animal.id == animal_id)
    result = await db.execute(stmt)
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor {animal_id} topilmadi",
        )

    # Mavjud ADI yozuvini qidirish
    log_stmt = select(ADILog).where(
        and_(
            ADILog.animal_id == animal_id,
            ADILog.calculation_date == date_str,
        )
    )
    log_result = await db.execute(log_stmt)
    log = log_result.scalar_one_or_none()

    if log:
        return ADILogResponse.from_orm_flat(log)

    # Mavjud bo'lmasa — hisoblash
    try:
        service = ADIService(db)
        adi_result = await service.calculate_for_animal(
            animal_id=animal_id,
            target_date=date_str,
        )

        # Alert tekshirish
        await _trigger_alerts_if_needed(
            db, animal_id, adi_result.adi_score,
            adi_result.category, date_str,
            adi_result.components.get("feeding"),
        )

        # Yangi saqlangan yozuvni olish
        new_log_result = await db.execute(log_stmt)
        new_log = new_log_result.scalar_one_or_none()

        if not new_log:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="ADI hisoblandi, lekin saqlanmadi",
            )

        return ADILogResponse.from_orm_flat(new_log)

    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor {animal_id} topilmadi",
        )
    except Exception as e:
        logger.error(
            f"ADI calculation failed for animal {animal_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ADI hisoblashda xato yuz berdi",
        )


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
    days: int = Query(
        30,
        ge=7,
        le=365,
        description="Necha kunlik tarix (7—365)",
    ),
    db: AsyncSession = Depends(get_db),
) -> ADITrendResponse:
    """
    Jonivorning ADI trend tarixini qaytaradi.
    Grafik chizish uchun ishlatiladi.
    """
    # Jonivor tekshirish
    stmt = select(Animal).where(Animal.id == animal_id)
    result = await db.execute(stmt)
    animal = result.scalar_one_or_none()
    if not animal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor {animal_id} topilmadi",
        )

    service = ADIService(db)
    logs = await service.get_animal_trend(
        animal_id=animal_id,
        days=days,
    )

    if not logs:
        return ADITrendResponse(
            animal_id=   animal_id,
            animal_tag=  animal.tag_id,
            period_days= days,
            trend=       [],
            avg_score=   0.0,
            min_score=   0.0,
            max_score=   0.0,
            current=     None,
        )

    # Trend nuqtalarini shakllantirish (eski → yangi)
    trend_points = [
        ADITrendPoint(
            date=     log.calculation_date,
            score=    log.adi_score,
            category= log.category,
        )
        for log in reversed(logs)   # DB yangi→eski, biz eski→yangi
    ]

    scores = [p.score for p in trend_points]

    return ADITrendResponse(
        animal_id=   animal_id,
        animal_tag=  animal.tag_id,
        period_days= days,
        trend=       trend_points,
        avg_score=   round(sum(scores) / len(scores), 2),
        min_score=   round(min(scores), 2),
        max_score=   round(max(scores), 2),
        current=     ADILogResponse.from_orm_flat(logs[0]),
    )


# ------------------------------------------------------------------ #
# CALCULATE (manual trigger)                                           #
# ------------------------------------------------------------------ #

@router.post(
    "/calculate",
    response_model=ADIBatchCalculationResponse,
    summary="ADI hisoblashni ishga tushirish",
    description=(
        "Barcha aktiv jonivorlar yoki bitta jonivor uchun "
        "ADI hisoblashni qo'lda ishga tushiradi. "
        "Asosan testing va debug uchun. "
        "Production da bu Celery task orqali bajariladi."
    ),
)
async def trigger_calculation(
    request: ADICalculationRequest,
    db: AsyncSession = Depends(get_db),
) -> ADIBatchCalculationResponse:
    """Qo'lda ADI hisoblash."""
    import time
    start_time = time.monotonic()

    service = ADIService(db)
    results: list[ADICalculationResult] = []

    if request.animal_id:
        # Bitta jonivor
        try:
            adi = await service.calculate_for_animal(
                animal_id=        request.animal_id,
                target_date=      request.target_date,
                force_recalculate=request.force_recalculate,
            )
            results.append(ADICalculationResult(
                success=          True,
                animal_id=        request.animal_id,
                calculation_date= adi.calculation_date,
                adi_score=        adi.adi_score,
                category=         adi.category,
                data_quality=     adi.data_quality,
            ))
        except EntityNotFoundError:
            results.append(ADICalculationResult(
                success=          False,
                animal_id=        request.animal_id,
                calculation_date= request.target_date or "",
                error=            "Jonivor topilmadi",
            ))
        except Exception as e:
            results.append(ADICalculationResult(
                success=          False,
                animal_id=        request.animal_id,
                calculation_date= request.target_date or "",
                error=            str(e),
            ))
    else:
        # Barcha aktiv jonivorlar
        animal_stmt = select(Animal.id).where(
            Animal.status == AnimalStatus.ACTIVE
        )
        animal_result = await db.execute(animal_stmt)
        animal_ids = [row[0] for row in animal_result.fetchall()]

        for animal_id in animal_ids:
            try:
                adi = await service.calculate_for_animal(
                    animal_id=        animal_id,
                    target_date=      request.target_date,
                    force_recalculate=request.force_recalculate,
                )
                results.append(ADICalculationResult(
                    success=          True,
                    animal_id=        animal_id,
                    calculation_date= adi.calculation_date,
                    adi_score=        adi.adi_score,
                    category=         adi.category,
                    data_quality=     adi.data_quality,
                ))
            except Exception as e:
                results.append(ADICalculationResult(
                    success=  False,
                    animal_id=animal_id,
                    calculation_date=request.target_date or "",
                    error=    str(e),
                ))

    duration_ms = (time.monotonic() - start_time) * 1000

    return ADIBatchCalculationResponse(
        total=       len(results),
        success=     sum(1 for r in results if r.success),
        failed=      sum(1 for r in results if not r.success and not r.skipped),
        skipped=     sum(1 for r in results if r.skipped),
        results=     results,
        duration_ms= round(duration_ms, 2),
    )


# ------------------------------------------------------------------ #
# PRIVATE HELPERS                                                      #
# ------------------------------------------------------------------ #

async def _compute_trend(
    db: AsyncSession,
    animal_id: int,
    today: str,
) -> str:
    """
    Bugungi va kechagi ADI taqqoslab trend aniqlash.

    Returns:
        "up" | "down" | "stable" | "unknown"
    """
    from datetime import timedelta
    today_dt = datetime.strptime(today, "%Y-%m-%d")
    yesterday = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    stmt = (
        select(ADILog.calculation_date, ADILog.adi_score)
        .where(
            and_(
                ADILog.animal_id == animal_id,
                ADILog.calculation_date.in_([today, yesterday]),
            )
        )
        .order_by(ADILog.calculation_date.desc())
    )
    result = await db.execute(stmt)
    rows = result.fetchall()

    scores = {row[0]: row[1] for row in rows}
    today_score     = scores.get(today)
    yesterday_score = scores.get(yesterday)

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
    animal_id: int,
    adi_score: float,
    category: str,
    date_str: str,
    feeding_component: Optional[Any] = None,
) -> None:
    """
    ADI hisoblangandan keyin alert servisini chaqirish.
    """
    from datetime import timedelta

    alert_service = AlertService(db)

    # Kechagi scoreini olish
    today_dt  = datetime.strptime(date_str, "%Y-%m-%d")
    yesterday = (today_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    stmt = select(ADILog.adi_score).where(
        and_(
            ADILog.animal_id == animal_id,
            ADILog.calculation_date == yesterday,
        )
    )
    result = await db.execute(stmt)
    row = result.fetchone()
    prev_score = float(row[0]) if row else None

    feeding_score = (
        feeding_component.score
        if feeding_component and hasattr(feeding_component, "score")
        else None
    )

    await alert_service.process_adi_result(
        animal_id=     animal_id,
        adi_score=     adi_score,
        category=      category,
        prev_score=    prev_score,
        feeding_score= feeding_score,
    )
