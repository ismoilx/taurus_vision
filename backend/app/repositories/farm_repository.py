"""
Taurus Vision — Farm Repository

JAVOBGARLIK: Faqat ma'lumotlar bazasi operatsiyalari.
Biznes logikasi YO'Q — bu Service qatlamining ishi.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger
from app.models.farm import Farm
from app.models.animal import Animal, AnimalStatus
from app.schemas.farm import FarmCreate, FarmUpdate

logger = get_logger(__name__)


class FarmRepository:
    """DB operatsiyalari uchun Farm Repository."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, data: FarmCreate) -> Farm:
        """Yangi ferma yaratish."""
        try:
            farm = Farm(**data.model_dump())
            self.db.add(farm)
            await self.db.commit()
            await self.db.refresh(farm)
            logger.info(f"Farm created: id={farm.id}, name='{farm.name}'")
            return farm
        except Exception as exc:
            await self.db.rollback()
            logger.error(f"Farm create error: {exc}")
            raise DatabaseError(message="Ferma yaratishda xato.", details={"error": str(exc)})

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, farm_id: int) -> Optional[Farm]:
        """ID bo'yicha ferma olish."""
        try:
            result = await self.db.execute(
                select(Farm).where(Farm.id == farm_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(message="Ferma olishda xato.", details={"error": str(exc)})

    async def get_all(
        self,
        skip: int = 0,
        limit: int = 50,
        active_only: bool = False,
    ) -> Sequence[Farm]:
        """Barcha fermalarni olish."""
        try:
            q = select(Farm)
            if active_only:
                q = q.where(Farm.is_active == True)  # noqa: E712
            q = q.order_by(Farm.name).offset(skip).limit(limit)
            result = await self.db.execute(q)
            return result.scalars().all()
        except Exception as exc:
            raise DatabaseError(message="Fermalar ro'yxatida xato.", details={"error": str(exc)})

    async def count(self, active_only: bool = False) -> int:
        """Fermalar sonini hisoblash."""
        try:
            q = select(func.count(Farm.id))
            if active_only:
                q = q.where(Farm.is_active == True)  # noqa: E712
            result = await self.db.execute(q)
            return result.scalar_one() or 0
        except Exception as exc:
            raise DatabaseError(message="Fermalar sonini hisoblashda xato.", details={"error": str(exc)})

    async def get_animal_stats(self, farm_id: int) -> dict:
        """Ferma uchun jonivor statistikasi."""
        try:
            total_q = select(func.count(Animal.id)).where(Animal.farm_id == farm_id)
            active_q = select(func.count(Animal.id)).where(
                and_(Animal.farm_id == farm_id, Animal.status == AnimalStatus.ACTIVE)
            )
            total  = (await self.db.execute(total_q)).scalar_one() or 0
            active = (await self.db.execute(active_q)).scalar_one() or 0
            return {"total": total, "active": active}
        except Exception as exc:
            logger.warning(f"Farm stats error: {exc}")
            return {"total": 0, "active": 0}

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update(self, farm: Farm, data: FarmUpdate) -> Farm:
        """Ferma ma'lumotlarini yangilash."""
        try:
            updates = data.model_dump(exclude_unset=True)
            for field, value in updates.items():
                setattr(farm, field, value)
            await self.db.commit()
            await self.db.refresh(farm)
            return farm
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Ferma yangilashda xato.", details={"error": str(exc)})

    async def update_user_farm(self, user_id: int, farm_id: Optional[int]) -> None:
        """Foydalanuvchining joriy fermasini yangilash."""
        try:
            from app.models.user import User
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user:
                user.current_farm_id = farm_id
                await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Foydalanuvchi fermasini yangilashda xato.", details={"error": str(exc)})

    # =========================================================================
    # DELETE (soft)
    # =========================================================================

    async def deactivate(self, farm: Farm) -> Farm:
        """Fermani arxivlash (o'chirilmaydi)."""
        try:
            farm.is_active = False
            await self.db.commit()
            await self.db.refresh(farm)
            logger.info(f"Farm deactivated: id={farm.id}")
            return farm
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Fermani arxivlashda xato.", details={"error": str(exc)})

    async def delete(self, farm: Farm) -> None:
        """Ferma to'liq o'chirish (faqat jonivorsiz fermalar)."""
        try:
            await self.db.delete(farm)
            await self.db.commit()
            logger.info(f"Farm deleted: id={farm.id}")
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Ferma o'chirishda xato.", details={"error": str(exc)})