"""
Taurus Vision — Go'sht Ishlab Chiqarish Endpointlari

ENDPOINTS:
    POST   /meat/                          — Yangi so'yish yozuvi qo'shish
    GET    /meat/                          — Barcha yozuvlar (filter bilan)
    GET    /meat/{record_id}               — Bitta yozuv
    PUT    /meat/{record_id}               — Yozuvni tahrirlash
    DELETE /meat/{record_id}               — Yozuvni o'chirish
    GET    /meat/farm/summary              — Ferma bo'yicha xulosa
    GET    /meat/farm/records              — Jadval uchun yozuvlar (enriched)
    GET    /meat/farm/daily                — Kunlik trend
    GET    /meat/animal/{id}               — Jonivorning so'yish tarixi
    GET    /meat/animal/{id}/summary       — Jonivorning go'sht xulosasi
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user, require_manager
from app.services.meat_service import MeatService
from app.models.meat_production import SlaughterPurpose, MeatQualityGrade
from app.schemas.meat_production import (
    SlaughterRecordCreate,
    SlaughterRecordUpdate,
    SlaughterRecordResponse,
    SlaughterRecordListResponse,
    AnimalMeatSummary,
    FarmMeatSummary,
)

router = APIRouter(prefix="/meat", tags=["Go'sht ishlab chiqarish"])


# ── YARATISH ──────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=SlaughterRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi so'yish yozuvi qo'shish",
)
async def create_slaughter_record(
    data: SlaughterRecordCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    """
    Yangi so'yish yozuvi qo'shish.

    - **animal_id**: Jonivor ID si (majburiy)
    - **slaughter_date**: So'yish sanasi (majburiy)
    - **meat_kg**: Sof go'sht miqdori kg (majburiy)
    - **live_weight_kg**: Tirik vazn kg (ixtiyoriy)
    - **price_per_kg**: 1 kg narxi so'mda (ixtiyoriy)
    """
    svc = MeatService(db)
    record = await svc.add_record(data)
    await db.commit()
    await db.refresh(record)
    return await svc.get_record_by_id(record.id)


# ── BARCHA YOZUVLAR ───────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=SlaughterRecordListResponse,
    summary="Barcha so'yish yozuvlari",
)
async def get_all_slaughter_records(
    page: int = Query(1, ge=1, description="Sahifa raqami"),
    page_size: int = Query(20, ge=1, le=100, description="Sahifadagi yozuvlar soni"),
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Tugash sanasi (YYYY-MM-DD)"),
    purpose: Optional[SlaughterPurpose] = Query(None, description="So'yish maqsadi"),
    quality_grade: Optional[MeatQualityGrade] = Query(None, description="Sifat darajasi"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MeatService(db)
    return await svc.get_all_records(
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
        purpose=purpose,
        quality_grade=quality_grade,
    )


# ── FERMA XULOSASI ────────────────────────────────────────────────────────────

@router.get(
    "/farm/summary",
    response_model=FarmMeatSummary,
    summary="Ferma bo'yicha go'sht xulosasi",
)
async def get_farm_meat_summary(
    days: int = Query(30, ge=7, le=365, description="Trend uchun kunlar soni"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    """
    Ferma bo'yicha to'liq go'sht statistikasi:
    - Bugungi, bu oylik, o'tgan oylik ko'rsatkichlar
    - Kunlik trend grafik ma'lumotlari
    - Maqsad va sifat bo'yicha taqsimot
    - Top jonivorlar reytingi
    """
    svc = MeatService(db)
    return await svc.get_farm_summary(days_trend=days)


@router.get(
    "/farm/records",
    summary="Jadval uchun yozuvlar (jonivor ma'lumotlari bilan)",
)
async def get_farm_meat_records(
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi"),
    date_to: Optional[date] = Query(None, description="Tugash sanasi"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> list[dict]:
    """
    Ferma bo'yicha barcha so'yish yozuvlari + jonivor ma'lumotlari.
    Frontend jadval uchun optimallashtirilgan.
    """
    svc = MeatService(db)
    return await svc.get_farm_records_enriched(date_from=date_from, date_to=date_to)


@router.get(
    "/farm/daily",
    summary="Kunlik go'sht trend",
)
async def get_daily_meat_trend(
    days: int = Query(30, ge=7, le=90, description="Necha kunlik trend"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> list[dict]:
    """Kunlik go'sht ishlab chiqarish trendi (grafik uchun)."""
    from datetime import timedelta
    repo = __import__(
        "app.repositories.meat_production_repository",
        fromlist=["MeatProductionRepository"]
    ).MeatProductionRepository(db)
    today = date.today()
    return await repo.get_daily_totals(
        date_from=today - timedelta(days=days - 1),
        date_to=today,
    )


# ── JONIVOR TARIXI ────────────────────────────────────────────────────────────

@router.get(
    "/animal/{animal_id}",
    response_model=SlaughterRecordListResponse,
    summary="Jonivorning so'yish tarixi",
)
async def get_animal_slaughter_records(
    animal_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MeatService(db)
    return await svc.get_animal_records(
        animal_id,
        page=page,
        page_size=page_size,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/animal/{animal_id}/summary",
    response_model=AnimalMeatSummary,
    summary="Jonivorning go'sht xulosasi",
)
async def get_animal_meat_summary(
    animal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MeatService(db)
    return await svc.get_animal_summary(animal_id)


# ── BITTA YOZUV ───────────────────────────────────────────────────────────────

@router.get(
    "/{record_id}",
    response_model=SlaughterRecordResponse,
    summary="Bitta so'yish yozuvi",
)
async def get_slaughter_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MeatService(db)
    return await svc.get_record_by_id(record_id)


# ── TAHRIRLASH / O'CHIRISH ────────────────────────────────────────────────────

@router.put(
    "/{record_id}",
    response_model=SlaughterRecordResponse,
    summary="Yozuvni tahrirlash",
)
async def update_slaughter_record(
    record_id: int,
    data: SlaughterRecordUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MeatService(db)
    await svc.update_record(record_id, data)
    await db.commit()
    return await svc.get_record_by_id(record_id)


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Yozuvni o'chirish",
)
async def delete_slaughter_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MeatService(db)
    await svc.delete_record(record_id)
    await db.commit()