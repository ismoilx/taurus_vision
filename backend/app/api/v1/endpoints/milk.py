"""
Taurus Vision — Sut Ishlab Chiqarish Endpointlari

ENDPOINTS:
    POST   /milk/                          — Yangi yozuv qo'shish
    GET    /milk/animal/{id}               — Jonivorning sut tarixi
    GET    /milk/animal/{id}/summary       — Jonivorning sut xulosasi
    GET    /milk/farm/summary              — Ferma bo'yicha xulosa
    GET    /milk/farm/daily                — Kunlik trend (30 kun)
    PUT    /milk/{record_id}               — Yozuvni tahrirlash
    DELETE /milk/{record_id}               — Yozuvni o'chirish
    GET    /milk/categories                — Kategoriyalar (species bo'yicha)
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user, require_manager
from app.services.milk_service import MilkService
from app.schemas.milk_production import (
    MilkProductionCreate,
    MilkProductionUpdate,
    MilkProductionResponse,
    MilkProductionListResponse,
    AnimalMilkSummary,
    FarmMilkSummary,
)

router = APIRouter(prefix="/milk", tags=["Sut ishlab chiqarish"])


# ── YARATISH ──────────────────────────────────────────────────────────────────

@router.post(
    "/",
    response_model=MilkProductionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi sut yozuvi qo'shish",
)
async def create_milk_record(
    data: MilkProductionCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MilkService(db)
    record = await svc.add_record(data)
    await db.commit()
    await db.refresh(record)
    return record


# ── JONIVOR TARIXI ────────────────────────────────────────────────────────────

@router.get(
    "/animal/{animal_id}",
    response_model=MilkProductionListResponse,
    summary="Jonivorning sut tarixi",
)
async def get_animal_milk_records(
    animal_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(30, ge=1, le=100),
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi (YYYY-MM-DD)"),
    date_to: Optional[date] = Query(None, description="Tugash sanasi (YYYY-MM-DD)"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MilkService(db)
    return await svc.get_animal_records(
        animal_id, page=page, page_size=page_size,
        date_from=date_from, date_to=date_to,
    )


@router.get(
    "/animal/{animal_id}/summary",
    response_model=AnimalMilkSummary,
    summary="Jonivorning sut xulosasi",
)
async def get_animal_milk_summary(
    animal_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MilkService(db)
    return await svc.get_animal_summary(animal_id)


# ── FERMA XULOSASI ────────────────────────────────────────────────────────────

@router.get(
    "/farm/animals",
    summary="Jonivorlar bo'yicha oylik sut statistikasi",
)
async def get_farm_animal_milk_stats(
    date_from: Optional[date] = Query(None, description="Boshlanish sanasi"),
    date_to: Optional[date] = Query(None, description="Tugash sanasi"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
) -> list[dict]:
    """
    Har bir jonivor uchun davr ichidagi sut statistikasi.

    Javob: [{ animal_id, tag_id, name, species,
              month_kg, today_kg, avg_daily_kg,
              avg_fat_percent, days_recorded, last_record_date }]
    """
    svc = MilkService(db)
    return await svc.get_farm_animal_stats(date_from=date_from, date_to=date_to)



@router.get(
    "/farm/summary",
    response_model=FarmMilkSummary,
    summary="Ferma bo'yicha sut xulosasi",
)
async def get_farm_milk_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MilkService(db)
    return await svc.get_farm_summary()


@router.get(
    "/farm/daily",
    summary="Kunlik sut trend (30 kun)",
)
async def get_daily_milk_trend(
    days: int = Query(30, ge=7, le=90),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    from datetime import timedelta
    from app.repositories.milk_production_repository import MilkProductionRepository
    repo = MilkProductionRepository(db)
    today = date.today()
    return await repo.get_daily_totals(
        date_from=today - timedelta(days=days - 1),
        date_to=today,
    )


# ── TAHRIRLASH / O'CHIRISH ────────────────────────────────────────────────────

@router.put(
    "/{record_id}",
    response_model=MilkProductionResponse,
    summary="Yozuvni tahrirlash",
)
async def update_milk_record(
    record_id: int,
    data: MilkProductionUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MilkService(db)
    record = await svc.update_record(record_id, data)
    await db.commit()
    await db.refresh(record)
    return record


@router.delete(
    "/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Yozuvni o'chirish",
)
async def delete_milk_record(
    record_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MilkService(db)
    await svc.delete_record(record_id)
    await db.commit()