"""
Taurus Vision — Dori-Darmon Ombori Endpointlari

ENDPOINTS:
    GET    /medicine/                         — Barcha dorlar ro'yxati
    POST   /medicine/                         — Yangi dori qo'shish
    GET    /medicine/summary                  — Ombor umumiy holati
    GET    /medicine/low-stock                — Kam qolganlar
    GET    /medicine/expiring                 — Muddati tugayotganlar
    GET    /medicine/{id}                     — Bitta dori
    PUT    /medicine/{id}                     — Tahrirlash
    POST   /medicine/{id}/restock             — Ombor to'ldirish
    DELETE /medicine/{id}                     — Arxivlash
    POST   /medicine/usage/                   — Jonivorga dori berish
    GET    /medicine/usage/animal/{animal_id} — Jonivorning dori tarixi
    GET    /medicine/categories               — Kategoriyalar ro'yxati
"""

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user, require_manager
from app.services.medicine_service import MedicineService
from app.schemas.medicine import (
    MedicineInventoryCreate,
    MedicineInventoryUpdate,
    MedicineInventoryResponse,
    MedicineListResponse,
    MedicineUsageCreate,
    MedicineUsageResponse,
    MedicineUsageListResponse,
    MedicineRestockRequest,
    MedicineInventorySummary,
)
from app.models.medicine import MedicineType

router = APIRouter(prefix="/medicine", tags=["Dori-darmon ombori"])


# ── KATEGORIYALAR ─────────────────────────────────────────────────────────────

@router.get("/categories", summary="Dori turlari ro'yxati")
async def get_medicine_categories():
    return {
        "types": [
            {"value": t.value, "label": _type_label(t)} for t in MedicineType
        ],
    }


def _type_label(t: MedicineType) -> str:
    labels = {
        MedicineType.VACCINE: "Vaksina / Emlash",
        MedicineType.ANTIBIOTIC: "Antibiotik",
        MedicineType.ANTIPARASITIC: "Parazitga qarshi",
        MedicineType.VITAMIN: "Vitamin / Mineral",
        MedicineType.HORMONE: "Gormonal preparat",
        MedicineType.ANALGESIC: "Og'riq qoldiruvchi",
        MedicineType.ANTIFUNGAL: "Zamburug'ga qarshi",
        MedicineType.DISINFECTANT: "Dezinfektsiya",
        MedicineType.SUPPLEMENT: "Qo'shimcha",
        MedicineType.OTHER: "Boshqa",
    }
    return labels.get(t, t.value)


# ── OMBOR HOLATI ──────────────────────────────────────────────────────────────

@router.get(
    "/summary",
    response_model=MedicineInventorySummary,
    summary="Ombor umumiy holati",
)
async def get_inventory_summary(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MedicineService(db)
    return await svc.get_inventory_summary()


@router.get(
    "/low-stock",
    response_model=list[MedicineInventoryResponse],
    summary="Kam qolgan dorlar",
)
async def get_low_stock(
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    from app.repositories.medicine_repository import MedicineRepository
    repo = MedicineRepository(db)
    items = await repo.get_low_stock()
    return [MedicineInventoryResponse.model_validate(i) for i in items]


@router.get(
    "/expiring",
    response_model=list[MedicineInventoryResponse],
    summary="Muddati tugayotgan dorlar (30 kun)",
)
async def get_expiring_medicines(
    days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    from app.repositories.medicine_repository import MedicineRepository
    repo = MedicineRepository(db)
    items = await repo.get_expiring_soon(days=days)
    return [MedicineInventoryResponse.model_validate(i) for i in items]


# ── ASOSIY CRUD ───────────────────────────────────────────────────────────────

@router.get(
    "/",
    response_model=MedicineListResponse,
    summary="Barcha dorlar ro'yxati",
)
async def list_medicines(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
    active_only: bool = Query(True),
    medicine_type: Optional[MedicineType] = Query(None),
    search: Optional[str] = Query(None, description="Nom bo'yicha qidiruv"),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MedicineService(db)
    return await svc.get_all_medicines(
        active_only=active_only,
        medicine_type=medicine_type,
        search=search,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/",
    response_model=MedicineInventoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi dori qo'shish",
)
async def create_medicine(
    data: MedicineInventoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MedicineService(db)
    medicine = await svc.create_medicine(data)
    await db.commit()
    await db.refresh(medicine)
    return medicine


@router.get(
    "/{medicine_id}",
    response_model=MedicineInventoryResponse,
    summary="Bitta dori ma'lumotlari",
)
async def get_medicine(
    medicine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MedicineService(db)
    return await svc.get_medicine(medicine_id)


@router.put(
    "/{medicine_id}",
    response_model=MedicineInventoryResponse,
    summary="Dori ma'lumotlarini tahrirlash",
)
async def update_medicine(
    medicine_id: int,
    data: MedicineInventoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MedicineService(db)
    medicine = await svc.update_medicine(medicine_id, data)
    await db.commit()
    await db.refresh(medicine)
    return medicine


@router.post(
    "/{medicine_id}/restock",
    response_model=MedicineInventoryResponse,
    summary="Ombor to'ldirish",
)
async def restock_medicine(
    medicine_id: int,
    data: MedicineRestockRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MedicineService(db)
    medicine = await svc.restock_medicine(medicine_id, data)
    await db.commit()
    await db.refresh(medicine)
    return medicine


@router.delete(
    "/{medicine_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Dorini arxivlash",
)
async def deactivate_medicine(
    medicine_id: int,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(require_manager),
):
    svc = MedicineService(db)
    await svc.deactivate_medicine(medicine_id)
    await db.commit()


# ── DORI BERISH ───────────────────────────────────────────────────────────────

@router.post(
    "/usage/",
    response_model=MedicineUsageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Jonivorga dori berish",
)
async def give_medicine_to_animal(
    data: MedicineUsageCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MedicineService(db)
    usage = await svc.give_medicine(data)
    await db.commit()
    await db.refresh(usage)
    # Qo'shimcha ma'lumotlar
    medicine = await svc.get_medicine(data.medicine_id)
    from app.schemas.medicine import MedicineUsageResponse as Resp
    resp = Resp.model_validate(usage)
    resp.medicine_name = medicine.name
    resp.medicine_unit = medicine.unit.value
    return resp


@router.get(
    "/usage/animal/{animal_id}",
    response_model=MedicineUsageListResponse,
    summary="Jonivorning dori tarixi",
)
async def get_animal_medicine_history(
    animal_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_active_user),
):
    svc = MedicineService(db)
    return await svc.get_animal_medicine_history(
        animal_id, page=page, page_size=page_size
    )