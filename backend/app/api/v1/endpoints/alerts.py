"""
Alerts API Endpoints.

ENDPOINTS:
    GET    /alerts              — Ochiq alertlar ro'yxati
    GET    /alerts/stats        — Alert statistikasi (dashboard)
    GET    /alerts/{alert_id}   — Bitta alert
    POST   /alerts              — Qo'lda alert yaratish
    PATCH  /alerts/{alert_id}/seen      — Ko'rilgan deb belgilash
    PATCH  /alerts/{alert_id}/resolve   — Hal etilgan deb belgilash
    PATCH  /alerts/{alert_id}/dismiss   — Bekor qilish
    POST   /alerts/check-missing        — Ko'rinmayotganlarni tekshirish
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import EntityNotFoundError
from app.models.alert import Alert, AlertStatus, AlertSeverity
from app.models.animal import Animal
from app.schemas.alert import (
    AlertResponse,
    AlertListResponse,
    AlertStatsResponse,
    AlertCreateManual,
    AlertResolveRequest,
    AlertDismissRequest,
)
from app.services.alert_service import AlertService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ------------------------------------------------------------------ #
# LIST                                                                 #
# ------------------------------------------------------------------ #

@router.get(
    "/",
    response_model=AlertListResponse,
    summary="Alertlar ro'yxati",
)
async def list_alerts(
    animal_id: Optional[int]  = Query(None, description="Jonivor ID filter"),
    severity:  Optional[str]  = Query(None, description="low|medium|high|critical"),
    status:    Optional[str]  = Query("open", description="open|seen|resolved|dismissed|all"),
    limit:     int            = Query(50, ge=1, le=200),
    offset:    int            = Query(0,  ge=0),
    db:        AsyncSession   = Depends(get_db),
) -> AlertListResponse:
    """
    Filterlangan alertlar ro'yxati.
    Default: faqat ochiq (open + seen) alertlar.
    """
    service = AlertService(db)

    if status == "all":
        # Barcha statuslar
        alerts, total = await service.get_open_alerts(
            animal_id=animal_id,
            severity= severity,
            limit=    limit,
            offset=   offset,
        )
        # Barcha status uchun alohida query
        conditions = []
        if animal_id:
            conditions.append(Alert.animal_id == animal_id)
        if severity:
            conditions.append(Alert.severity == severity)

        count_stmt = select(func.count(Alert.id))
        if conditions:
            count_stmt = count_stmt.where(and_(*conditions))
        total = await db.scalar(count_stmt) or 0

        stmt = select(Alert)
        if conditions:
            stmt = stmt.where(and_(*conditions))
        stmt = (
            stmt
            .order_by(Alert.triggered_at.desc())
            .limit(limit)
            .offset(offset)
        )
        result = await db.execute(stmt)
        alerts = list(result.scalars().all())
    else:
        alerts, total = await service.get_open_alerts(
            animal_id=animal_id,
            severity= severity,
            limit=    limit,
            offset=   offset,
        )

    # tag_id larni olish
    items = []
    for alert in alerts:
        tag_id = None
        if alert.animal_id:
            animal_stmt = select(Animal.tag_id).where(
                Animal.id == alert.animal_id
            )
            animal_result = await db.execute(animal_stmt)
            row = animal_result.fetchone()
            tag_id = row[0] if row else None

        items.append(
            AlertResponse.from_orm_with_tag(alert, tag_id)
        )

    return AlertListResponse(
        total=  total,
        limit=  limit,
        offset= offset,
        items=  items,
    )


# ------------------------------------------------------------------ #
# STATS                                                                #
# ------------------------------------------------------------------ #

@router.get(
    "/stats",
    response_model=AlertStatsResponse,
    summary="Alert statistikasi",
    description="Dashboard widget uchun alert statistikasi.",
)
async def get_alert_stats(
    db: AsyncSession = Depends(get_db),
) -> AlertStatsResponse:
    """Ochiq alertlar statistikasi."""
    service = AlertService(db)
    stats = await service.get_alert_stats()
    return AlertStatsResponse(**stats)


# ------------------------------------------------------------------ #
# SINGLE ALERT                                                         #
# ------------------------------------------------------------------ #

@router.get(
    "/{alert_id}",
    response_model=AlertResponse,
    summary="Bitta alert",
    responses={404: {"description": "Alert topilmadi"}},
)
async def get_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """ID bo'yicha bitta alertni qaytarish."""
    stmt = select(Alert).where(Alert.id == alert_id)
    result = await db.execute(stmt)
    alert = result.scalar_one_or_none()

    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} topilmadi",
        )

    tag_id = None
    if alert.animal_id:
        animal_stmt = select(Animal.tag_id).where(
            Animal.id == alert.animal_id
        )
        animal_result = await db.execute(animal_stmt)
        row = animal_result.fetchone()
        tag_id = row[0] if row else None

    return AlertResponse.from_orm_with_tag(alert, tag_id)


# ------------------------------------------------------------------ #
# CREATE (manual)                                                      #
# ------------------------------------------------------------------ #

@router.post(
    "/",
    response_model=AlertResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Qo'lda alert yaratish",
)
async def create_alert(
    data: AlertCreateManual,
    db:   AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Fermer tomonidan qo'lda alert yaratish.
    Avtomatik tizim kuzatmagan muammolar uchun.
    """
    # Jonivor tekshirish
    if data.animal_id:
        stmt = select(Animal).where(Animal.id == data.animal_id)
        result = await db.execute(stmt)
        animal = result.scalar_one_or_none()
        if not animal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Jonivor {data.animal_id} topilmadi",
            )

    service = AlertService(db)
    alert = await service.create_manual_alert(data)

    tag_id = None
    if alert.animal_id:
        stmt = select(Animal.tag_id).where(Animal.id == alert.animal_id)
        result = await db.execute(stmt)
        row = result.fetchone()
        tag_id = row[0] if row else None

    return AlertResponse.from_orm_with_tag(alert, tag_id)


# ------------------------------------------------------------------ #
# LIFECYCLE                                                            #
# ------------------------------------------------------------------ #

@router.patch(
    "/{alert_id}/seen",
    response_model=AlertResponse,
    summary="Alertni ko'rilgan deb belgilash",
    responses={404: {"description": "Alert topilmadi"}},
)
async def mark_alert_seen(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
) -> AlertResponse:
    """Alertni ko'rilgan (seen) holatiga o'tkazish."""
    service = AlertService(db)
    try:
        alert = await service.mark_seen(alert_id)
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} topilmadi",
        )

    tag_id = None
    if alert.animal_id:
        stmt = select(Animal.tag_id).where(Animal.id == alert.animal_id)
        result = await db.execute(stmt)
        row = result.fetchone()
        tag_id = row[0] if row else None

    return AlertResponse.from_orm_with_tag(alert, tag_id)


@router.patch(
    "/{alert_id}/resolve",
    response_model=AlertResponse,
    summary="Alertni hal etilgan deb belgilash",
    responses={
        404: {"description": "Alert topilmadi"},
        400: {"description": "Alert allaqachon yopilgan"},
    },
)
async def resolve_alert(
    alert_id: int,
    data:     AlertResolveRequest,
    db:       AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Alertni hal etilgan (resolved) holatiga o'tkazish.
    Qanday harakat qilinganini yozib qoldirish mumkin.
    """
    service = AlertService(db)
    try:
        alert = await service.resolve_alert(
            alert_id=    alert_id,
            resolved_by= data.resolved_by,
            note=        data.resolution_note,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} topilmadi",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    tag_id = None
    if alert.animal_id:
        stmt = select(Animal.tag_id).where(Animal.id == alert.animal_id)
        result = await db.execute(stmt)
        row = result.fetchone()
        tag_id = row[0] if row else None

    return AlertResponse.from_orm_with_tag(alert, tag_id)


@router.patch(
    "/{alert_id}/dismiss",
    response_model=AlertResponse,
    summary="Alertni bekor qilish",
    responses={
        404: {"description": "Alert topilmadi"},
        400: {"description": "Alert allaqachon yopilgan"},
    },
)
async def dismiss_alert(
    alert_id: int,
    data:     AlertDismissRequest,
    db:       AsyncSession = Depends(get_db),
) -> AlertResponse:
    """
    Alertni noto'g'ri alarm (false alarm) sifatida bekor qilish.
    """
    service = AlertService(db)
    try:
        alert = await service.dismiss_alert(
            alert_id=     alert_id,
            dismissed_by= data.dismissed_by,
            reason=       data.reason,
        )
    except EntityNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} topilmadi",
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    tag_id = None
    if alert.animal_id:
        stmt = select(Animal.tag_id).where(Animal.id == alert.animal_id)
        result = await db.execute(stmt)
        row = result.fetchone()
        tag_id = row[0] if row else None

    return AlertResponse.from_orm_with_tag(alert, tag_id)


# ------------------------------------------------------------------ #
# SYSTEM ACTIONS                                                       #
# ------------------------------------------------------------------ #

@router.post(
    "/check-missing",
    summary="Ko'rinmayotgan jonivorlarni tekshirish",
    description=(
        "Barcha aktiv jonivorlarning so'nggi ko'rinish vaqtini tekshirib, "
        "24/48 soatdan ko'p ko'rinmayotganlar uchun alert yaratadi. "
        "Odatda Celery tomonidan har soatda chaqiriladi."
    ),
)
async def check_missing_animals(
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ko'rinmayotgan jonivorlar tekshiruvi."""
    service = AlertService(db)
    alerts = await service.check_missing_animals()

    return {
        "checked": True,
        "alerts_created": len(alerts),
        "alert_ids": [a.id for a in alerts],
    }