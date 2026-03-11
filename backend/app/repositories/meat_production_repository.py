"""
Taurus Vision — Go'sht Ishlab Chiqarish Repository

Faqat DB operatsiyalari. Biznes logika meat_service.py da.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, List, Sequence

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.models.meat_production import SlaughterRecord, SlaughterPurpose, MeatQualityGrade
from app.schemas.meat_production import SlaughterRecordCreate, SlaughterRecordUpdate

logger = get_logger(__name__)


class MeatProductionRepository:
    """Go'sht ishlab chiqarish DB operatsiyalari."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── CREATE ────────────────────────────────────────────────────────

    async def create(self, data: SlaughterRecordCreate) -> SlaughterRecord:
        record = SlaughterRecord(**data.model_dump())
        self.db.add(record)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    # ── READ ──────────────────────────────────────────────────────────

    async def get_by_id(self, record_id: int) -> Optional[SlaughterRecord]:
        result = await self.db.execute(
            select(SlaughterRecord).where(SlaughterRecord.id == record_id)
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
    ) -> tuple[Sequence[SlaughterRecord], int]:
        """Bitta jonivorning so'yish yozuvlari."""
        q = select(SlaughterRecord).where(SlaughterRecord.animal_id == animal_id)
        if date_from:
            q = q.where(SlaughterRecord.slaughter_date >= date_from)
        if date_to:
            q = q.where(SlaughterRecord.slaughter_date <= date_to)

        total = await self.db.scalar(
            select(func.count()).select_from(q.subquery())
        )
        items = (await self.db.execute(
            q.order_by(desc(SlaughterRecord.slaughter_date)).limit(limit).offset(offset)
        )).scalars().all()

        return items, total or 0

    async def get_all_records(
        self,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        purpose: Optional[SlaughterPurpose] = None,
        quality_grade: Optional[MeatQualityGrade] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[Sequence[SlaughterRecord], int]:
        """Barcha so'yish yozuvlari (filter bilan)."""
        q = select(SlaughterRecord)
        if date_from:
            q = q.where(SlaughterRecord.slaughter_date >= date_from)
        if date_to:
            q = q.where(SlaughterRecord.slaughter_date <= date_to)
        if purpose:
            q = q.where(SlaughterRecord.purpose == purpose)
        if quality_grade:
            q = q.where(SlaughterRecord.quality_grade == quality_grade)

        total = await self.db.scalar(
            select(func.count()).select_from(q.subquery())
        )
        items = (await self.db.execute(
            q.order_by(desc(SlaughterRecord.slaughter_date)).limit(limit).offset(offset)
        )).scalars().all()

        return items, total or 0

    async def get_farm_records(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> Sequence[SlaughterRecord]:
        """Ferma bo'yicha davr ichidagi so'yish yozuvlari."""
        result = await self.db.execute(
            select(SlaughterRecord).where(
                and_(
                    SlaughterRecord.slaughter_date >= date_from,
                    SlaughterRecord.slaughter_date <= date_to,
                )
            ).order_by(SlaughterRecord.slaughter_date)
        )
        return result.scalars().all()

    async def get_daily_totals(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Kunlik jami go'sht miqdori va statistika."""
        result = await self.db.execute(
            select(
                SlaughterRecord.slaughter_date,
                func.sum(SlaughterRecord.meat_kg).label("meat_kg"),
                func.count(SlaughterRecord.id).label("animals_count"),
                func.sum(SlaughterRecord.total_revenue).label("revenue"),
                func.avg(SlaughterRecord.dressing_percent).label("avg_dressing"),
            )
            .where(
                and_(
                    SlaughterRecord.slaughter_date >= date_from,
                    SlaughterRecord.slaughter_date <= date_to,
                )
            )
            .group_by(SlaughterRecord.slaughter_date)
            .order_by(SlaughterRecord.slaughter_date)
        )
        return [
            {
                "date":         str(row.slaughter_date),
                "meat_kg":      round(row.meat_kg or 0, 2),
                "animals_count": row.animals_count,
                "revenue":      round(row.revenue, 2) if row.revenue else None,
                "avg_dressing": round(row.avg_dressing, 2) if row.avg_dressing else None,
            }
            for row in result
        ]

    async def get_purpose_breakdown(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Maqsad bo'yicha statistika."""
        result = await self.db.execute(
            select(
                SlaughterRecord.purpose,
                func.count(SlaughterRecord.id).label("count"),
                func.sum(SlaughterRecord.meat_kg).label("meat_kg"),
                func.sum(SlaughterRecord.total_revenue).label("revenue"),
            )
            .where(
                and_(
                    SlaughterRecord.slaughter_date >= date_from,
                    SlaughterRecord.slaughter_date <= date_to,
                )
            )
            .group_by(SlaughterRecord.purpose)
            .order_by(desc("count"))
        )
        return [
            {
                "purpose": row.purpose.value if row.purpose else "unknown",
                "count":   row.count,
                "meat_kg": round(row.meat_kg or 0, 2),
                "revenue": round(row.revenue, 2) if row.revenue else None,
            }
            for row in result
        ]

    async def get_quality_breakdown(
        self,
        *,
        date_from: date,
        date_to: date,
    ) -> list[dict]:
        """Sifat darajasi bo'yicha statistika."""
        result = await self.db.execute(
            select(
                SlaughterRecord.quality_grade,
                func.count(SlaughterRecord.id).label("count"),
                func.sum(SlaughterRecord.meat_kg).label("meat_kg"),
            )
            .where(
                and_(
                    SlaughterRecord.slaughter_date >= date_from,
                    SlaughterRecord.slaughter_date <= date_to,
                    SlaughterRecord.quality_grade.isnot(None),
                )
            )
            .group_by(SlaughterRecord.quality_grade)
            .order_by(desc("meat_kg"))
        )
        rows = result.all()
        total_count = sum(r.count for r in rows)
        return [
            {
                "grade":   row.quality_grade.value if row.quality_grade else "unknown",
                "count":   row.count,
                "meat_kg": round(row.meat_kg or 0, 2),
                "percent": round((row.count / total_count) * 100, 1) if total_count > 0 else 0,
            }
            for row in rows
        ]

    async def get_top_animals(
        self,
        *,
        date_from: date,
        date_to: date,
        limit: int = 10,
    ) -> list[dict]:
        """Eng ko'p go'sht bergan jonivorlar."""
        result = await self.db.execute(
            select(
                SlaughterRecord.animal_id,
                func.sum(SlaughterRecord.meat_kg).label("total_meat_kg"),
                func.sum(SlaughterRecord.total_revenue).label("total_revenue"),
                func.count(SlaughterRecord.id).label("slaughter_count"),
                func.avg(SlaughterRecord.dressing_percent).label("avg_dressing"),
                func.max(SlaughterRecord.slaughter_date).label("last_date"),
            )
            .where(
                and_(
                    SlaughterRecord.slaughter_date >= date_from,
                    SlaughterRecord.slaughter_date <= date_to,
                )
            )
            .group_by(SlaughterRecord.animal_id)
            .order_by(desc("total_meat_kg"))
            .limit(limit)
        )
        return [
            {
                "animal_id":       row.animal_id,
                "total_meat_kg":   round(row.total_meat_kg or 0, 2),
                "total_revenue":   round(row.total_revenue, 2) if row.total_revenue else None,
                "slaughter_count": row.slaughter_count,
                "avg_dressing":    round(row.avg_dressing, 2) if row.avg_dressing else None,
                "last_date":       str(row.last_date),
            }
            for row in result
        ]

    async def get_today_stats(self) -> dict:
        """Bugungi so'yish statistikasi."""
        today = date.today()
        result = await self.db.execute(
            select(
                func.sum(SlaughterRecord.meat_kg).label("meat_kg"),
                func.count(SlaughterRecord.id).label("animals_count"),
                func.sum(SlaughterRecord.total_revenue).label("revenue"),
            )
            .where(SlaughterRecord.slaughter_date == today)
        )
        row = result.one()
        return {
            "meat_kg":      round(row.meat_kg or 0, 2),
            "animals_count": row.animals_count or 0,
            "revenue":       round(row.revenue, 2) if row.revenue else None,
        }

    async def get_animal_stats(self, animal_id: int) -> dict:
        """Jonivorning umumiy so'yish statistikasi."""
        result = await self.db.execute(
            select(
                func.sum(SlaughterRecord.meat_kg).label("total_meat_kg"),
                func.avg(SlaughterRecord.meat_kg).label("avg_meat_kg"),
                func.sum(SlaughterRecord.total_revenue).label("total_revenue"),
                func.count(SlaughterRecord.id).label("record_count"),
                func.max(SlaughterRecord.meat_kg).label("max_meat_kg"),
                func.max(SlaughterRecord.slaughter_date).label("last_date"),
            )
            .where(SlaughterRecord.animal_id == animal_id)
        )
        row = result.one()
        return {
            "total_meat_kg":   round(row.total_meat_kg or 0, 2),
            "avg_meat_kg":     round(row.avg_meat_kg or 0, 2),
            "total_revenue":   round(row.total_revenue, 2) if row.total_revenue else None,
            "record_count":    row.record_count or 0,
            "max_meat_kg":     round(row.max_meat_kg or 0, 2),
            "last_date":       str(row.last_date) if row.last_date else None,
        }

    # ── UPDATE ────────────────────────────────────────────────────────

    async def update(
        self, record: SlaughterRecord, data: SlaughterRecordUpdate
    ) -> SlaughterRecord:
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(record, field, value)
        await self.db.flush()
        await self.db.refresh(record)
        return record

    # ── DELETE ────────────────────────────────────────────────────────

    async def delete(self, record: SlaughterRecord) -> None:
        await self.db.delete(record)
        await self.db.flush()