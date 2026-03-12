"""
Taurus Vision — Health Record API Endpoints

/api/v1/health/* prefix ostida jonivor sog'liq yozuvlari uchun
barcha REST endpointlari.

ARXITEKTURA QOIDASI:
    Endpoint → Service → Repository → DB
    Service har so'rov uchun alohida yaratiladi (request-scoped).
    Hech qanday global service instance yo'q.

AUTH:
    Barcha endpointlar JWT authentication talab qiladi.
    O'zgartirish/o'chirish faqat MANAGER va ADMIN uchun.

ENDPOINTLAR:
    POST   /health/animals/{id}/records   — Yangi yozuv
    GET    /health/animals/{id}/records   — Jonivor yozuvlari
    GET    /health/animals/{id}/summary   — Sog'liq xulosasi
    GET    /health/records/{id}           — Yozuv detail
    PATCH  /health/records/{id}           — Yozuvni yangilash
    POST   /health/records/{id}/resolve   — Hal etilgan belgilash
    DELETE /health/records/{id}           — O'chirish (MANAGER)
    GET    /health/unresolved             — Hal etilmagan yozuvlar
    GET    /health/critical               — Kritik yozuvlar
    GET    /health/upcoming-checkups      — Yaqin tekshiruvlar
    GET    /health/statistics             — Statistika
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Path, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.api.v1.deps import CurrentUser, CurrentManager
from app.services.health_record_service import HealthRecordService
from app.models.health_record import HealthRecordType, HealthRecordSeverity
from app.schemas.health_record import (
    HealthRecordCreate,
    HealthRecordUpdate,
    HealthRecordResponse,
    HealthRecordListResponse,
    HealthStatistics,
    HealthSummary,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health Records"])


# =============================================================================
# CREATE
# =============================================================================

@router.post(
    "/animals/{animal_id}/records",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Sog'liq yozuvi yaratish",
    description=(
        "Jonivor uchun yangi sog'liq yozuvi qo'shish. "
        "Tekshiruv, davolash, emlash va boshqa tibbiy hodisalar. "
        "MANAGER yoki ADMIN talab qilinadi."
    ),
)
async def create_health_record(
    animal_id: int = Path(..., gt=0, description="Jonivor ID"),
    record: HealthRecordCreate = ...,
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordResponse:
    """
    Jonivor uchun yangi sog'liq yozuvi yaratish.

    Args:
        animal_id:    Jonivor ID (URL dan)
        record:       Yangi yozuv ma'lumotlari
        current_user: MANAGER yoki ADMIN (JWT tekshiruvi)
        db:           DB session

    Returns:
        Yaratilgan HealthRecordResponse

    Raises:
        404: Jonivor topilmadi
        400: Validatsiya xatosi (manfiy narx, o'tgan sana va h.k.)
        403: Ruxsat yo'q
    """
    logger.info(
        "Health record create request",
        extra={"animal_id": animal_id, "requested_by": current_user.id},
    )

    service = HealthRecordService(db)
    try:
        created = await service.create_health_record(
            db=db,
            animal_id=animal_id,
            record_type=HealthRecordType(record.record_type),
            severity=HealthRecordSeverity(record.severity),
            diagnosis=record.diagnosis,
            symptoms=record.symptoms,
            treatment=record.treatment,
            medication=record.medication,
            dosage=record.dosage,
            veterinarian=record.veterinarian,
            clinic_name=record.clinic_name,
            cost=record.cost,
            notes=record.notes,
            recorded_at=record.recorded_at,
            next_checkup_date=record.next_checkup_date,
        )
    except ValueError as exc:
        msg = str(exc)
        # Animal not found → 404, boshqa validatsiya xatolari → 400
        if "not found" in msg.lower():
            raise HTTPException(status_code=404, detail=msg)
        raise BusinessRuleViolationError(message=msg)

    return HealthRecordResponse.model_validate(created)


# =============================================================================
# READ — Yozuv detail
# =============================================================================

@router.get(
    "/records/{record_id}",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Sog'liq yozuvi detail",
    description="ID bo'yicha bitta sog'liq yozuvini olish.",
)
async def get_health_record(
    record_id: int = Path(..., gt=0, description="Yozuv ID"),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordResponse:
    """
    ID bo'yicha sog'liq yozuvini olish.

    Args:
        record_id:    Yozuv ID
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session

    Returns:
        HealthRecordResponse

    Raises:
        404: Yozuv topilmadi
    """
    service = HealthRecordService(db)
    record = await service.get_record_by_id(db, record_id)

    if not record:
        raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)

    return HealthRecordResponse.model_validate(record)


# =============================================================================
# READ — Jonivor yozuvlari ro'yxati
# =============================================================================

@router.get(
    "/animals/{animal_id}/records",
    response_model=HealthRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="Jonivor sog'liq yozuvlari",
    description="Bir jonivorning barcha sog'liq yozuvlari (sahifalab).",
)
async def get_animal_health_records(
    animal_id: int = Path(..., gt=0, description="Jonivor ID"),
    skip: int = Query(0, ge=0, description="O'tkazib yuborilgan yozuvlar soni"),
    limit: int = Query(20, ge=1, le=100, description="Sahifa hajmi"),
    record_type: Optional[str] = Query(None, description="Tur bo'yicha filter (vaccination, checkup, ...)"),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordListResponse:
    """
    Jonivorning sog'liq yozuvlari ro'yxatini olish.

    Args:
        animal_id:    Jonivor ID
        skip:         Sahifalash offseti
        limit:        Sahifa hajmi (max 100)
        record_type:  Ixtiyoriy filter (vaccination, checkup, ...)
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session

    Returns:
        HealthRecordListResponse (yozuvlar + jami soni)

    Raises:
        404: Jonivor topilmadi
    """
    service = HealthRecordService(db)
    try:
        if record_type:
            try:
                rt = HealthRecordType(record_type)
            except ValueError:
                raise HTTPException(status_code=422, detail=f"Noto'g'ri record_type: {record_type}")
            records, total = await service.get_records_by_type(db, animal_id, rt)
            # Pagination qo'lda
            records = records[skip: skip + limit]
        else:
            records, total = await service.get_animal_records(db, animal_id, skip, limit)
    except HTTPException:
        raise
    except ValueError:
        raise EntityNotFoundError(entity="Animal", identifier=animal_id)

    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total,
        skip=skip,
        limit=limit,
    )


# =============================================================================
# READ — Sog'liq xulosasi
# =============================================================================

@router.get(
    "/animals/{animal_id}/summary",
    response_model=HealthSummary,
    status_code=status.HTTP_200_OK,
    summary="Jonivor sog'liq xulosasi",
    description=(
        "Jonivor uchun to'liq sog'liq tahlili: skor, ochiq muammolar, "
        "yaqin tekshiruvlar va statistika."
    ),
)
async def get_health_summary(
    animal_id: int = Path(..., gt=0, description="Jonivor ID"),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthSummary:
    """
    Jonivor uchun keng qamrovli sog'liq xulosasi.

    Args:
        animal_id:    Jonivor ID
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session

    Returns:
        HealthSummary

    Raises:
        404: Jonivor topilmadi
    """
    service = HealthRecordService(db)
    try:
        summary = await service.get_health_summary(db, animal_id)
    except ValueError:
        raise EntityNotFoundError(entity="Animal", identifier=animal_id)

    return HealthSummary(**summary)


# =============================================================================
# UPDATE
# =============================================================================

@router.patch(
    "/records/{record_id}",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Sog'liq yozuvini yangilash",
    description="Yozuvning bir yoki bir necha maydonini yangilash. MANAGER talab.",
)
async def update_health_record(
    record_id: int = Path(..., gt=0, description="Yozuv ID"),
    update: HealthRecordUpdate = ...,
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordResponse:
    """
    Sog'liq yozuvini qisman yangilash.

    Args:
        record_id:    Yangilanadigan yozuv ID
        update:       Yangi ma'lumotlar (faqat yuborilgan maydonlar yangilanadi)
        current_user: MANAGER yoki ADMIN
        db:           DB session

    Returns:
        Yangilangan HealthRecordResponse

    Raises:
        404: Yozuv topilmadi
        400: Validatsiya xatosi
    """
    service = HealthRecordService(db)
    try:
        update_data = update.model_dump(exclude_unset=True)
        if "record_type" in update_data:
            update_data["record_type"] = HealthRecordType(update_data["record_type"])
        if "severity" in update_data:
            update_data["severity"] = HealthRecordSeverity(update_data["severity"])

        updated = await service.update_health_record(db, record_id, **update_data)
    except ValueError as exc:
        raise BusinessRuleViolationError(message=str(exc))

    if not updated:
        raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)

    return HealthRecordResponse.model_validate(updated)


# =============================================================================
# RESOLVE
# =============================================================================

@router.post(
    "/records/{record_id}/resolve",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_200_OK,
    summary="Yozuvni hal etilgan deb belgilash",
    description="Sog'liq muammosini hal etilgan deb belgilash. MANAGER talab.",
)
async def resolve_health_record(
    record_id: int = Path(..., gt=0, description="Yozuv ID"),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordResponse:
    """
    Sog'liq yozuvini hal etilgan deb belgilash.

    Args:
        record_id:    Hal etiladigan yozuv ID
        current_user: MANAGER yoki ADMIN
        db:           DB session

    Returns:
        Yangilangan HealthRecordResponse

    Raises:
        404: Yozuv topilmadi
    """
    service = HealthRecordService(db)
    resolved = await service.resolve_health_record(db, record_id)

    if not resolved:
        raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)

    logger.info(
        "Health record resolved",
        extra={"record_id": record_id, "resolved_by": current_user.id},
    )

    return HealthRecordResponse.model_validate(resolved)


# =============================================================================
# DELETE
# =============================================================================

@router.delete(
    "/records/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Sog'liq yozuvini o'chirish",
    description="Yozuvni butunlay o'chirish. MANAGER talab. Qaytarib bo'lmaydi.",
)
async def delete_health_record(
    record_id: int = Path(..., gt=0, description="Yozuv ID"),
    current_user: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Sog'liq yozuvini o'chirish.

    Args:
        record_id:    O'chiriladigan yozuv ID
        current_user: MANAGER yoki ADMIN
        db:           DB session

    Raises:
        404: Yozuv topilmadi
    """
    service = HealthRecordService(db)
    deleted = await service.delete_health_record(db, record_id)

    if not deleted:
        raise EntityNotFoundError(entity="HealthRecord", identifier=record_id)

    logger.info(
        "Health record deleted",
        extra={"record_id": record_id, "deleted_by": current_user.id},
    )


# =============================================================================
# FILTER ENDPOINTS
# =============================================================================

@router.get(
    "/unresolved",
    response_model=HealthRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="Hal etilmagan yozuvlar",
    description="Barcha hal etilmagan sog'liq muammolari ro'yxati.",
)
async def get_unresolved_records(
    animal_id: Optional[int] = Query(None, gt=0, description="Jonivor filtri"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordListResponse:
    """
    Hal etilmagan sog'liq yozuvlarini olish.

    Args:
        animal_id:    Ixtiyoriy jonivor filtri
        skip:         Sahifalash offseti
        limit:        Sahifa hajmi
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session
    """
    service = HealthRecordService(db)
    records, total = await service.get_unresolved_records(db, animal_id, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/critical",
    response_model=HealthRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="Kritik yozuvlar",
    description="Darhol e'tibor talab qiluvchi hal etilmagan kritik muammolar.",
)
async def get_critical_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordListResponse:
    """
    Kritik hal etilmagan sog'liq yozuvlarini olish.

    Args:
        skip:         Sahifalash offseti
        limit:        Sahifa hajmi
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session
    """
    service = HealthRecordService(db)
    records, total = await service.get_critical_records(db, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/upcoming-checkups",
    response_model=HealthRecordListResponse,
    status_code=status.HTTP_200_OK,
    summary="Yaqin tekshiruvlar",
    description="Rejalashtirilgan va yaqinda bo'ladigan veterinar tekshiruvlar.",
)
async def get_upcoming_checkups(
    days_ahead: int = Query(7, ge=1, le=90, description="Necha kun oldini ko'rish"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthRecordListResponse:
    """
    Yaqin tekshiruv jadvalini olish.

    Args:
        days_ahead:   Ko'riladigan kun oralig'i (1-90)
        skip:         Sahifalash offseti
        limit:        Sahifa hajmi
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session
    """
    service = HealthRecordService(db)
    records, total = await service.get_upcoming_checkups(db, days_ahead, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get(
    "/statistics",
    response_model=HealthStatistics,
    status_code=status.HTTP_200_OK,
    summary="Sog'liq statistikasi",
    description="Ferma bo'yicha yoki bitta jonivor bo'yicha sog'liq statistikasi.",
)
async def get_health_statistics(
    animal_id: Optional[int] = Query(None, gt=0, description="Jonivor filtri (bo'sh = barcha)"),
    current_user: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
) -> HealthStatistics:
    """
    Sog'liq statistikasini olish.

    Args:
        animal_id:    Ixtiyoriy jonivor filtri
        current_user: Autentifikatsiya qilingan foydalanuvchi
        db:           DB session
    """
    service = HealthRecordService(db)
    stats = await service.get_health_statistics(db, animal_id)
    return HealthStatistics(**stats)