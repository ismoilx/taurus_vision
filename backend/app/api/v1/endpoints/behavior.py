"""
Taurus Vision — Behavior Analysis API (Sprint 11-12)

Jonivorlar xatti-harakatini real-time tahlil qilish uchun HTTP endpointlar.
Barcha biznes mantiq BehaviorService da joylashgan.

ENDPOINTLAR:
    GET  /behavior/{animal_id}          — Bitta jonivor tahlili
    POST /behavior/{animal_id}/analyze  — Darhol tahlil (manager+)
    GET  /behavior/herd/summary         — Butun podadan umumiy ko'rinish
    GET  /behavior/{animal_id}/timeline — Soatlik vaqt chizig'i
    GET  /behavior/{animal_id}/anomalies — Aniqlangan anomaliyalar

AUTENTIFIKATSIYA:
    O'qish:        VIEWER+
    Darhol tahlil: MANAGER+
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager
from app.services.behavior_service import BehaviorService
from app.schemas.behavior import (
    AnomalyEntry,
    BehaviorAnalysis,
    BehaviorTimelineEntry,
    HerdBehaviorSummary,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behavior", tags=["Behavior Analysis"])


# =============================================================================
# ENDPOINTS
# =============================================================================


@router.get(
    "/herd/summary",
    response_model=HerdBehaviorSummary,
    summary="Butun podaning xatti-harakat xulosasi",
    description=(
        "Barcha aktiv jonivorlar uchun xatti-harakat tahlili o'tkazadi va "
        "umumiy xulosa yaratadi. Diqqat talab qiladigan jonivorlarni ro'yxatga oladi. "
        "Katta podalarda sekinroq ishlashi mumkin — limit parametridan foydalaning."
    ),
)
async def get_herd_behavior_summary(
    hours: int = Query(
        default=24,
        ge=1,
        le=72,
        description="Tahlil davri (soat). Katta qiymatlar sekinroq ishlaydi.",
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Diqqat talab qiladiganlar maksimal soni",
    ),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HerdBehaviorSummary:
    """
    Butun podaning xatti-harakat xulosasi.

    Barcha ACTIVE jonivorlarni tahlil qilib holat taqsimoti,
    o'rtacha ko'rsatkichlar va eng muammolilarni qaytaradi.
    """
    service = BehaviorService(db)
    return await service.get_herd_summary(period_hours=hours, attention_limit=limit)


@router.get(
    "/{animal_id}",
    response_model=BehaviorAnalysis,
    summary="Jonivor xatti-harakat tahlili",
    description=(
        "So'nggi N soat uchun jonivor xatti-harakatini tahlil qiladi. "
        "Faollik, oziqlanish, harakat va ijtimoiy xulq ko'rsatkichlarini hisoblaydi."
    ),
)
async def get_animal_behavior(
    animal_id: int,
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
        description="Tahlil davri (soat). Min: 1, Max: 168 (7 kun)",
    ),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> BehaviorAnalysis:
    """
    Jonivor xatti-harakat tahlilini qaytaradi.

    Args:
        animal_id: Tahlil qilinadigan jonivor ID
        hours:     Tahlil davri (1–168 soat)

    Raises:
        404: Jonivor topilmasa
    """
    service = BehaviorService(db)
    try:
        return await service.analyze_animal(animal_id, period_hours=hours)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.post(
    "/{animal_id}/analyze",
    response_model=BehaviorAnalysis,
    status_code=http_status.HTTP_200_OK,
    summary="Darhol xatti-harakat tahlilini ishga tushirish",
    description=(
        "Jonivor uchun xatti-harakat tahlilini sinxron bajaradi va natijani qaytaradi. "
        "Celery task ni kutmasdan real-time natija kerak bo'lganda ishlatiladi. "
        "MANAGER va undan yuqori rol talab etiladi."
    ),
)
async def trigger_behavior_analysis(
    animal_id: int,
    hours: int = Query(
        default=24,
        ge=1,
        le=168,
        description="Tahlil davri (soat)",
    ),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> BehaviorAnalysis:
    """
    Darhol xatti-harakat tahlili (MANAGER+ roli talab etiladi).

    GET /{animal_id} bilan bir xil natija qaytaradi,
    lekin foydalanuvchi harakati log qilinadi.
    """
    logger.info(
        "Manual behavior analysis triggered",
        extra={
            "extra_data": {
                "animal_id": animal_id,
                "hours": hours,
                "requested_by": current_user.username,
            }
        },
    )
    service = BehaviorService(db)
    try:
        return await service.analyze_animal(animal_id, period_hours=hours)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{animal_id}/timeline",
    response_model=list[BehaviorTimelineEntry],
    summary="Jonivor xatti-harakat vaqt chizig'i",
    description=(
        "So'nggi N soatlik xatti-harakat ma'lumotini soatlik "
        "kesimda qaytaradi. Grafik va trend ko'rsatish uchun mo'ljallangan."
    ),
)
async def get_behavior_timeline(
    animal_id: int,
    hours: int = Query(
        default=24,
        ge=6,
        le=168,
        description="Tahlil davri (soat)",
    ),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> list[BehaviorTimelineEntry]:
    """
    Soatlik detection va xatti-harakat ma'lumotlari.

    Frontend uchun chart data:
        X: Vaqt (soat)
        Y: Detection soni, Oziqlanish tashrifi, Harakat
    """
    service = BehaviorService(db)
    try:
        return await service.get_animal_timeline(animal_id, period_hours=hours)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


@router.get(
    "/{animal_id}/anomalies",
    response_model=list[AnomalyEntry],
    summary="Jonivor anomaliyalari",
    description=(
        "So'nggi N kunlik xatti-harakat anomaliyalarini qaytaradi. "
        "Har kuni bir necha anomaliya aniqlanishi mumkin."
    ),
)
async def get_animal_anomalies(
    animal_id: int,
    days: int = Query(
        default=7,
        ge=1,
        le=30,
        description="Necha kun orqaga qarash",
    ),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> list[AnomalyEntry]:
    """
    Jonivor anomaliyalari ro'yxati (xronologik tartibda, eng yangisi birinchi).

    Args:
        animal_id: Jonivor ID
        days:      Necha kun orqaga qarash (1–30)

    Raises:
        404: Jonivor topilmasa
    """
    service = BehaviorService(db)
    try:
        return await service.get_animal_anomalies(animal_id, days=days)
    except ValueError as exc:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc