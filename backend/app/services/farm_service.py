"""
Taurus Vision — Farm Service

JAVOBGARLIK: Faqat biznes logikasi.
DB operatsiyalari Repository orqali, HTTP — Endpoint orqali.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.core.logging_config import get_logger
from app.models.farm import Farm
from app.repositories.farm_repository import FarmRepository
from app.schemas.farm import FarmCreate, FarmUpdate, FarmResponse, FarmListResponse, FarmSwitchResponse

logger = get_logger(__name__)


class FarmService:
    """Multi-farm biznes logikasi."""

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = FarmRepository(db)

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create_farm(self, data: FarmCreate) -> FarmResponse:
        """
        Yangi ferma yaratish.

        Args:
            data: Ferma ma'lumotlari

        Returns:
            Yaratilgan ferma response
        """
        farm = await self.repo.create(data)
        return await self._to_response(farm)

    # =========================================================================
    # READ
    # =========================================================================

    async def get_farm(self, farm_id: int) -> FarmResponse:
        """
        ID bo'yicha ferma olish.

        Raises:
            EntityNotFoundError: Ferma topilmasa
        """
        farm = await self.repo.get_by_id(farm_id)
        if not farm:
            raise EntityNotFoundError(entity="Farm", entity_id=farm_id)
        return await self._to_response(farm)

    async def list_farms(
        self,
        skip: int = 0,
        limit: int = 50,
        active_only: bool = False,
    ) -> FarmListResponse:
        """Fermalar ro'yxati va umumiy soni."""
        farms = await self.repo.get_all(skip=skip, limit=limit, active_only=active_only)
        total = await self.repo.count(active_only=active_only)
        items = [await self._to_response(f) for f in farms]
        return FarmListResponse(items=items, total=total)

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_farm(self, farm_id: int, data: FarmUpdate) -> FarmResponse:
        """
        Ferma ma'lumotlarini yangilash.

        Raises:
            EntityNotFoundError: Ferma topilmasa
        """
        farm = await self.repo.get_by_id(farm_id)
        if not farm:
            raise EntityNotFoundError(entity="Farm", entity_id=farm_id)
        updated = await self.repo.update(farm, data)
        return await self._to_response(updated)

    # =========================================================================
    # SWITCH (Ferma almashtirish)
    # =========================================================================

    async def switch_farm(self, user_id: int, farm_id: int) -> FarmSwitchResponse:
        """
        Foydalanuvchining joriy fermasini o'zgartirish.

        Qoida: faqat aktiv fermaga o'tish mumkin.

        Args:
            user_id:  Foydalanuvchi ID
            farm_id:  Yangi ferma ID

        Returns:
            Switch natijasi

        Raises:
            EntityNotFoundError: Ferma topilmasa
            BusinessRuleViolationError: Ferma arxivlangan bo'lsa
        """
        farm = await self.repo.get_by_id(farm_id)
        if not farm:
            raise EntityNotFoundError(entity="Farm", entity_id=farm_id)

        if not farm.is_active:
            raise BusinessRuleViolationError(
                message="Arxivlangan fermaga o'tib bo'lmaydi.",
                details={"farm_id": farm_id},
            )

        await self.repo.update_user_farm(user_id, farm_id)
        logger.info(f"User {user_id} switched to farm {farm_id} ('{farm.name}')")

        return FarmSwitchResponse(
            message=f"'{farm.name}' fermasiga muvaffaqiyatli o'tildi.",
            farm_id=farm.id,
            farm_name=farm.name,
        )

    # =========================================================================
    # DEACTIVATE / DELETE
    # =========================================================================

    async def deactivate_farm(self, farm_id: int) -> FarmResponse:
        """Fermani arxivlash."""
        farm = await self.repo.get_by_id(farm_id)
        if not farm:
            raise EntityNotFoundError(entity="Farm", entity_id=farm_id)
        updated = await self.repo.deactivate(farm)
        return await self._to_response(updated)

    async def delete_farm(self, farm_id: int) -> None:
        """
        Fermani to'liq o'chirish.

        Qoida: agar fermada jonivorlar bo'lsa, o'chirishga ruxsat yo'q.
        """
        farm = await self.repo.get_by_id(farm_id)
        if not farm:
            raise EntityNotFoundError(entity="Farm", entity_id=farm_id)

        stats = await self.repo.get_animal_stats(farm_id)
        if stats["total"] > 0:
            raise BusinessRuleViolationError(
                message=f"Fermada {stats['total']} ta jonivor bor. Avval ularni boshqa fermaga o'tkazing.",
                details={"animal_count": stats["total"]},
            )

        await self.repo.delete(farm)

    # =========================================================================
    # PRIVATE
    # =========================================================================

    async def _to_response(self, farm: Farm) -> FarmResponse:
        """Farm modelini response schemaga aylantirish (statistika bilan)."""
        stats = await self.repo.get_animal_stats(farm.id)
        resp = FarmResponse.model_validate(farm)
        resp.animal_count        = stats["total"]
        resp.active_animal_count = stats["active"]
        return resp