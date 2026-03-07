"""
Taurus Vision — Dori-Darmon Ombori Servisi

Biznes logika: validatsiya, ogohlantirish, statistika.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.repositories.medicine_repository import MedicineRepository
from app.models.medicine import MedicineInventory, MedicineUsage
from app.schemas.medicine import (
    MedicineInventoryCreate,
    MedicineInventoryUpdate,
    MedicineInventoryResponse,
    MedicineUsageCreate,
    MedicineUsageResponse,
    MedicineRestockRequest,
    MedicineListResponse,
    MedicineUsageListResponse,
    MedicineInventorySummary,
)

logger = get_logger(__name__)


class MedicineService:
    """Dori-darmon ombori biznes logikasi."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MedicineRepository(db)

    # ── INVENTORY ─────────────────────────────────────────────────────

    async def create_medicine(
        self, data: MedicineInventoryCreate
    ) -> MedicineInventory:
        """Yangi dori qo'shish."""
        medicine = await self.repo.create_medicine(data)
        logger.info(f"Dori qo'shildi: '{medicine.name}' ({medicine.medicine_type.value})")
        return medicine

    async def get_all_medicines(
        self,
        *,
        active_only: bool = True,
        medicine_type=None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> MedicineListResponse:
        items, total = await self.repo.get_all(
            active_only=active_only,
            medicine_type=medicine_type,
            search=search,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        low_stock = await self.repo.get_low_stock()
        expired = await self.repo.get_expired()
        expiring = await self.repo.get_expiring_soon()

        return MedicineListResponse(
            items=[MedicineInventoryResponse.model_validate(i) for i in items],
            total=total,
            low_stock_count=len(low_stock),
            expired_count=len(expired),
            expiring_soon_count=len(expiring),
        )

    async def get_medicine(self, medicine_id: int) -> MedicineInventory:
        medicine = await self.repo.get_by_id(medicine_id)
        if not medicine:
            raise EntityNotFoundError(f"Dori topilmadi: ID={medicine_id}")
        return medicine

    async def update_medicine(
        self, medicine_id: int, data: MedicineInventoryUpdate
    ) -> MedicineInventory:
        medicine = await self.get_medicine(medicine_id)
        return await self.repo.update_medicine(medicine, data)

    async def restock_medicine(
        self, medicine_id: int, data: MedicineRestockRequest
    ) -> MedicineInventory:
        """Ombor to'ldirish."""
        medicine = await self.get_medicine(medicine_id)
        updated = await self.repo.restock(medicine, data)
        logger.info(
            f"Ombor to'ldirildi: '{medicine.name}' +{data.quantity_to_add} "
            f"→ jami {updated.quantity}{updated.unit.value}"
        )
        return updated

    async def deactivate_medicine(self, medicine_id: int) -> None:
        """Dorini arxivlash."""
        medicine = await self.get_medicine(medicine_id)
        await self.repo.deactivate(medicine)
        logger.info(f"Dori arxivlandi: '{medicine.name}'")

    async def get_inventory_summary(self) -> MedicineInventorySummary:
        """Ombor umumiy holati."""
        all_items, total = await self.repo.get_all(active_only=True, limit=1000)
        active_items, active_count = await self.repo.get_all(active_only=True, limit=1000)

        low_stock = await self.repo.get_low_stock()
        expired = await self.repo.get_expired()
        expiring = await self.repo.get_expiring_soon()

        total_value = sum(
            (i.quantity * i.purchase_price)
            for i in all_items
            if i.purchase_price
        )

        return MedicineInventorySummary(
            total_medicines=total,
            active_medicines=active_count,
            low_stock_items=[MedicineInventoryResponse.model_validate(i) for i in low_stock],
            expired_items=[MedicineInventoryResponse.model_validate(i) for i in expired],
            expiring_soon_items=[MedicineInventoryResponse.model_validate(i) for i in expiring],
            total_value=round(total_value, 2),
        )

    # ── USAGE ─────────────────────────────────────────────────────────

    async def give_medicine(self, data: MedicineUsageCreate) -> MedicineUsage:
        """
        Jonivorga dori berish.

        Raises:
            EntityNotFoundError: Dori topilmasa
            BusinessRuleViolationError: Miqdor yetarli emas
        """
        medicine = await self.get_medicine(data.medicine_id)

        if medicine.quantity < data.quantity_given:
            raise BusinessRuleViolationError(
                f"Omborда yetarli miqdor yo'q. "
                f"Mavjud: {medicine.quantity}{medicine.unit.value}, "
                f"Kerak: {data.quantity_given}{medicine.unit.value}"
            )

        if medicine.is_expired:
            raise BusinessRuleViolationError(
                f"'{medicine.name}' dorining muddati o'tgan "
                f"({medicine.expiry_date}). Ishlatib bo'lmaydi."
            )

        usage = await self.repo.create_usage(data)
        logger.info(
            f"Dori berildi: animal_id={data.animal_id}, "
            f"medicine='{medicine.name}', qty={data.quantity_given}"
        )
        return usage

    async def get_animal_medicine_history(
        self,
        animal_id: int,
        *,
        page: int = 1,
        page_size: int = 20,
    ) -> MedicineUsageListResponse:
        items, total = await self.repo.get_animal_usages(
            animal_id,
            limit=page_size,
            offset=(page - 1) * page_size,
        )

        def _to_response(u: MedicineUsage) -> MedicineUsageResponse:
            d = MedicineUsageResponse.model_validate(u)
            if u.medicine:
                d.medicine_name = u.medicine.name
                d.medicine_unit = u.medicine.unit.value
            return d

        return MedicineUsageListResponse(
            items=[_to_response(u) for u in items],
            total=total,
        )