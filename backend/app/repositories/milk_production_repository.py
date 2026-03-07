"""
Taurus Vision — Sut Ishlab Chiqarish Repository

Faqat DB operatsiyalari. Biznes logika milk_service.py da.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional, List, Sequence

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.milk_production import MilkProduction, MilkSession
from app.schemas.milk_production import MilkProductionCreate, MilkProductionUpdate

logger = get_logger(__name__)


class MilkProductionRepository:
    """Sut ishlab chiqarish DB operatsiyalari."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CREATE ────────────────────────────────────────────────────────

    async def create(self, data: MilkProductionCreate) -> MilkProduction:
        record = MilkProduction(**data.model_dump())
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    # ── READ ──────────────────────────────────────────────────────────

    async def get_by_id(self, record_id: int) -> Optional[MilkProduction]:
        result = await self.db.execute(
            select(MilkProduction).where(MilkProduction.id == record_id)
        )
        return result.scalar_one_or_none()

    async def get_by_animal(
        self,
        animal_id: int,
        *,
        limit: int = 30,
        offset: int = 0,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> tuple[Sequence[MilkProduction], int]:
        """Bitta jonivorning sut yozuvlari."""
        q = select(MilkProduction).where(MilkProduction.animal_id == animal_id)
        if date_from:
            q = q.where(MilkProduction.record_date >= date_from)
        if date_to:
            q = q.where(MilkProduction.record_date <= date_to)

        total = await self.db.scalar(
            select(func.count()).select_from(q.subquery())
        )
        items = (await self.db.execute(
            q.order_by(desc(MilkProduction.record_date)).limit(limit).offset(offset)
        )).scalars().all()

        return items, total or 0

    async def get_farm_records(
        self,
        *,
        date_from: date,
        date_to: date,
        animal_ids: Optional[List[int]] = None,
    ) -> Sequence[MilkProduction]:
        """Ferma bo'yicha davr ichidagi sut yozuvlari."""
        q = select(MilkProduction).where(
            and_(
                MilkProduction.record_date >= date_from,
                MilkProduction.record_date <= date_to,
            )
        )
        if animal_ids:
            q = q.where(MilkProduction.animal_id.in_(animal_ids))
        result = await self.db.execute(q.order_by(MilkProduction.record_date))
        return result.scalars().all()

    async def get_daily_totals(
        self,
        *,
        date_from: date,
        date_to: date,
        animal_id: Optional[int] = None,
    ) -> list[dict]:
        """Kunlik jami sut miqdori."""
        q = (
            select(
                MilkProduction.record_date,
                func.sum(MilkProduction.milk_kg).label("total_kg"),
                func.count(MilkProduction.animal_id.distinct()).label("animal_count"),
                func.avg(MilkProduction.fat_percent).label("avg_fat"),
            )
            .where(
                and_(
                    MilkProduction.record_date >= date_from,
                    MilkProduction.record_date <= date_to,
                )
            )
            .group_by(MilkProduction.record_date)
            .order_by(MilkProduction.record_date)
        )
        if animal_id:
            q = q.where(MilkProduction.animal_id == animal_id)

        result = await self.db.execute(q)
        return [
            {
                "date": str(row.record_date),
                "total_kg": round(row.total_kg or 0, 2),
                "animal_count": row.animal_count,
                "avg_fat": round(row.avg_fat, 2) if row.avg_fat else None,
            }
            for row in result
        ]

    async def get_animal_stats(
        self,
        animal_id: int,
        days: int = 30,
    ) -> dict:
        """Jonivorning so'nggi N kun sut statistikasi."""
        date_from = date.today() - timedelta(days=days)
        result = await self.db.execute(
            select(
                func.sum(MilkProduction.milk_kg).label("total_kg"),
                func.avg(MilkProduction.milk_kg).label("avg_kg"),
                func.avg(MilkProduction.fat_percent).label("avg_fat"),
                func.avg(MilkProduction.protein_percent).label("avg_protein"),
                func.avg(MilkProduction.somatic_cell_count).label("avg_scc"),
                func.max(MilkProduction.milk_kg).label("max_kg"),
                func.count(MilkProduction.id).label("record_count"),
            )
            .where(
                and_(
                    MilkProduction.animal_id == animal_id,
                    MilkProduction.record_date >= date_from,
                )
            )
        )
        row = result.one()
        return {
            "total_kg": round(row.total_kg or 0, 2),
            "avg_daily_kg": round(row.avg_kg or 0, 2),
            "avg_fat_percent": round(row.avg_fat, 2) if row.avg_fat else None,
            "avg_protein_percent": round(row.avg_protein, 2) if row.avg_protein else None,
            "avg_scc": round(row.avg_scc) if row.avg_scc else None,
            "best_day_kg": round(row.max_kg or 0, 2),
            "days_recorded": row.record_count,
        }

    async def get_today_total(self, animal_id: Optional[int] = None) -> float:
        """Bugungi sut (jami yoki bitta jonivor)."""
        q = select(func.sum(MilkProduction.milk_kg)).where(
            MilkProduction.record_date == date.today()
        )
        if animal_id:
            q = q.where(MilkProduction.animal_id == animal_id)
        result = await self.db.scalar(q)
        return round(result or 0, 2)

    # ── UPDATE ────────────────────────────────────────────────────────

    async def update(
        self, record: MilkProduction, data: MilkProductionUpdate
    ) -> MilkProduction:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    # ── DELETE ────────────────────────────────────────────────────────

    async def delete(self, record: MilkProduction) -> None:
        await self.db.delete(record)
        await self.db.flush()