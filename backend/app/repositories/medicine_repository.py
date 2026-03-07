"""
Taurus Vision — Dori-Darmon Ombori Repository

Faqat DB operatsiyalari.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.logging_config import get_logger
from app.models.medicine import MedicineInventory, MedicineUsage, MedicineType
from app.schemas.medicine import (
    MedicineInventoryCreate,
    MedicineInventoryUpdate,
    MedicineUsageCreate,
    MedicineRestockRequest,
)

logger = get_logger(__name__)


class MedicineRepository:
    """Dori-darmon ombori DB operatsiyalari."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── INVENTORY: CREATE ─────────────────────────────────────────────

    async def create_medicine(self, data: MedicineInventoryCreate) -> MedicineInventory:
        medicine = MedicineInventory(**data.model_dump())
        self.db.add(medicine)
        await self.db.flush()
        await self.db.refresh(medicine)
        return medicine

    # ── INVENTORY: READ ───────────────────────────────────────────────

    async def get_by_id(self, medicine_id: int) -> Optional[MedicineInventory]:
        result = await self.db.execute(
            select(MedicineInventory).where(MedicineInventory.id == medicine_id)
        )
        return result.scalar_one_or_none()

    async def get_all(
        self,
        *,
        active_only: bool = True,
        medicine_type: Optional[MedicineType] = None,
        search: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[Sequence[MedicineInventory], int]:
        q = select(MedicineInventory)
        if active_only:
            q = q.where(MedicineInventory.is_active == True)  # noqa
        if medicine_type:
            q = q.where(MedicineInventory.medicine_type == medicine_type)
        if search:
            q = q.where(
                or_(
                    MedicineInventory.name.ilike(f"%{search}%"),
                    MedicineInventory.generic_name.ilike(f"%{search}%"),
                )
            )
        total = await self.db.scalar(select(func.count()).select_from(q.subquery()))
        items = (await self.db.execute(
            q.order_by(MedicineInventory.name).limit(limit).offset(offset)
        )).scalars().all()
        return items, total or 0

    async def get_low_stock(self) -> Sequence[MedicineInventory]:
        """Kam qolgan dorlar."""
        result = await self.db.execute(
            select(MedicineInventory)
            .where(
                and_(
                    MedicineInventory.is_active == True,  # noqa
                    MedicineInventory.quantity <= MedicineInventory.min_stock_quantity,
                )
            )
            .order_by(MedicineInventory.quantity)
        )
        return result.scalars().all()

    async def get_expired(self) -> Sequence[MedicineInventory]:
        """Muddati o'tgan dorlar."""
        result = await self.db.execute(
            select(MedicineInventory)
            .where(
                and_(
                    MedicineInventory.is_active == True,  # noqa
                    MedicineInventory.expiry_date < date.today(),
                )
            )
        )
        return result.scalars().all()

    async def get_expiring_soon(self, days: int = 30) -> Sequence[MedicineInventory]:
        """Tez orada muddati tugaydigan dorlar."""
        future = date.today() + timedelta(days=days)
        result = await self.db.execute(
            select(MedicineInventory)
            .where(
                and_(
                    MedicineInventory.is_active == True,  # noqa
                    MedicineInventory.expiry_date >= date.today(),
                    MedicineInventory.expiry_date <= future,
                )
            )
            .order_by(MedicineInventory.expiry_date)
        )
        return result.scalars().all()

    # ── INVENTORY: UPDATE ─────────────────────────────────────────────

    async def update_medicine(
        self, medicine: MedicineInventory, data: MedicineInventoryUpdate
    ) -> MedicineInventory:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(medicine, field, value)
        await self.db.flush()
        await self.db.refresh(medicine)
        return medicine

    async def restock(
        self, medicine: MedicineInventory, data: MedicineRestockRequest
    ) -> MedicineInventory:
        """Ombor to'ldirish — miqdor qo'shish."""
        medicine.quantity += data.quantity_to_add
        if data.batch_number:
            medicine.batch_number = data.batch_number
        if data.expiry_date:
            medicine.expiry_date = data.expiry_date
        if data.purchase_price is not None:
            medicine.purchase_price = data.purchase_price
        await self.db.flush()
        await self.db.refresh(medicine)
        return medicine

    async def deactivate(self, medicine: MedicineInventory) -> MedicineInventory:
        medicine.is_active = False
        await self.db.flush()
        return medicine

    # ── USAGE: CREATE ─────────────────────────────────────────────────

    async def create_usage(self, data: MedicineUsageCreate) -> MedicineUsage:
        """Dori berish va ombordan ayirish."""
        usage = MedicineUsage(**data.model_dump())
        self.db.add(usage)

        # Ombordan ayirish
        medicine = await self.get_by_id(data.medicine_id)
        if medicine:
            medicine.quantity = max(0.0, medicine.quantity - data.quantity_given)

        await self.db.flush()
        await self.db.refresh(usage)
        return usage

    # ── USAGE: READ ───────────────────────────────────────────────────

    async def get_usage_by_id(self, usage_id: int) -> Optional[MedicineUsage]:
        result = await self.db.execute(
            select(MedicineUsage)
            .options(joinedload(MedicineUsage.medicine))
            .where(MedicineUsage.id == usage_id)
        )
        return result.scalar_one_or_none()

    async def get_animal_usages(
        self,
        animal_id: int,
        *,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[Sequence[MedicineUsage], int]:
        """Bitta jonivorga berilgan dorlar tarixi."""
        q = (
            select(MedicineUsage)
            .options(joinedload(MedicineUsage.medicine))
            .where(MedicineUsage.animal_id == animal_id)
        )
        total = await self.db.scalar(select(func.count()).select_from(
            select(MedicineUsage).where(MedicineUsage.animal_id == animal_id).subquery()
        ))
        items = (await self.db.execute(
            q.order_by(desc(MedicineUsage.given_date)).limit(limit).offset(offset)
        )).scalars().all()
        return items, total or 0

    async def get_upcoming_doses(self, days: int = 7) -> Sequence[MedicineUsage]:
        """Kelgusi N kun ichida keyingi dozasi keladiganlari."""
        future = date.today() + timedelta(days=days)
        result = await self.db.execute(
            select(MedicineUsage)
            .options(joinedload(MedicineUsage.medicine))
            .where(
                and_(
                    MedicineUsage.next_dose_date >= date.today(),
                    MedicineUsage.next_dose_date <= future,
                )
            )
            .order_by(MedicineUsage.next_dose_date)
        )
        return result.scalars().all()