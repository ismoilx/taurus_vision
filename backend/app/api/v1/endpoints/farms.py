"""
Taurus Vision — Farms API Endpoint

ROUTES:
    GET    /farms              — Fermalar ro'yxati (barcha foydalanuvchilar)
    POST   /farms              — Yangi ferma yaratish (ADMIN)
    GET    /farms/{id}         — Ferma tafsiloti
    PUT    /farms/{id}         — Ferma yangilash (ADMIN)
    POST   /farms/{id}/switch  — Joriy fermani almashtirish (har kim)
    POST   /farms/{id}/deactivate — Arxivlash (ADMIN)
    DELETE /farms/{id}         — O'chirish (ADMIN, jonivorsiz fermalar)
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentAdmin
from app.services.farm_service import FarmService
from app.schemas.farm import (
    FarmCreate,
    FarmUpdate,
    FarmResponse,
    FarmListResponse,
    FarmSwitchResponse,
)

router = APIRouter(prefix="/farms", tags=["Farms"])


# =============================================================================
# LIST
# =============================================================================

@router.get("", response_model=FarmListResponse)
async def list_farms(
    skip:        int  = Query(0,     ge=0),
    limit:       int  = Query(50,    ge=1, le=200),
    active_only: bool = Query(False, description="Faqat aktiv fermalar"),
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """Barcha fermalar ro'yxati va jonivor statistikasi."""
    service = FarmService(db)
    return await service.list_farms(skip=skip, limit=limit, active_only=active_only)


# =============================================================================
# CREATE
# =============================================================================

@router.post("", response_model=FarmResponse, status_code=201)
async def create_farm(
    data: FarmCreate,
    current_user: CurrentAdmin = None,
    db: AsyncSession = Depends(get_db),
):
    """Yangi ferma yaratish — faqat ADMIN."""
    service = FarmService(db)
    return await service.create_farm(data)


# =============================================================================
# GET ONE
# =============================================================================

@router.get("/{farm_id}", response_model=FarmResponse)
async def get_farm(
    farm_id: int,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """Ferma tafsiloti."""
    service = FarmService(db)
    return await service.get_farm(farm_id)


# =============================================================================
# UPDATE
# =============================================================================

@router.put("/{farm_id}", response_model=FarmResponse)
async def update_farm(
    farm_id: int,
    data: FarmUpdate,
    current_user: CurrentAdmin = None,
    db: AsyncSession = Depends(get_db),
):
    """Ferma ma'lumotlarini yangilash — faqat ADMIN."""
    service = FarmService(db)
    return await service.update_farm(farm_id, data)


# =============================================================================
# SWITCH
# =============================================================================

@router.post("/{farm_id}/switch", response_model=FarmSwitchResponse)
async def switch_farm(
    farm_id: int,
    current_user: CurrentUser = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Joriy fermani almashtirish.

    Foydalanuvchi bu endpoint orqali qaysi fermada ishlashini tanlaydi.
    Tanlangan ferma frontend da saqlanib, barcha so'rovlarda ishlatiladi.
    """
    service = FarmService(db)
    return await service.switch_farm(current_user.id, farm_id)


# =============================================================================
# DEACTIVATE
# =============================================================================

@router.post("/{farm_id}/deactivate", response_model=FarmResponse)
async def deactivate_farm(
    farm_id: int,
    current_user: CurrentAdmin = None,
    db: AsyncSession = Depends(get_db),
):
    """Fermani arxivlash (o'chirilmaydi, faqat yashiriladi) — faqat ADMIN."""
    service = FarmService(db)
    return await service.deactivate_farm(farm_id)


# =============================================================================
# DELETE
# =============================================================================

@router.delete("/{farm_id}", status_code=204)
async def delete_farm(
    farm_id: int,
    current_user: CurrentAdmin = None,
    db: AsyncSession = Depends(get_db),
):
    """Fermani to'liq o'chirish — faqat ADMIN, faqat jonivorsiz fermalar."""
    service = FarmService(db)
    await service.delete_farm(farm_id)