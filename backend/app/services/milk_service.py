"""
Taurus Vision — Sut Ishlab Chiqarish Servisi

Biznes logika: validatsiya, statistika, summaries.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.repositories.milk_production_repository import MilkProductionRepository
from app.repositories.animal import AnimalRepository
from app.models.milk_production import MilkProduction, MilkQualityGrade
from app.schemas.milk_production import (
    MilkProductionCreate,
    MilkProductionUpdate,
    MilkProductionListResponse,
    MilkStatsPeriod,
    AnimalMilkSummary,
    FarmMilkSummary,
)

logger = get_logger(__name__)


class MilkService:
    """Sut ishlab chiqarish biznes logikasi."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MilkProductionRepository(db)
        self.animal_repo = AnimalRepository(db)

    async def add_record(self, data: MilkProductionCreate) -> MilkProduction:
        """
        Yangi sut yozuvi qo'shish.

        Args:
            data: Sut yozuvi ma'lumotlari

        Returns:
            Yaratilgan yozuv

        Raises:
            EntityNotFoundError: Jonivor topilmasa
            BusinessRuleViolationError: Jonivor urg'ochi emas
        """
        animal = await self.animal_repo.get_by_id(data.animal_id)
        if not animal:
            raise EntityNotFoundError(f"Jonivor topilmadi: ID={data.animal_id}")

        if animal.gender == "male":
            raise BusinessRuleViolationError(
                "Erkak jonivorga sut yozuvi qo'shib bo'lmaydi"
            )

        # Sifat darajasini avtomatik hisoblash (agar berilmasa)
        if data.quality_grade is None and data.somatic_cell_count is not None:
            scc = data.somatic_cell_count
            if scc < 200:
                data = data.model_copy(update={"quality_grade": MilkQualityGrade.PREMIUM})
            elif scc < 400:
                data = data.model_copy(update={"quality_grade": MilkQualityGrade.STANDARD})
            elif scc < 800:
                data = data.model_copy(update={"quality_grade": MilkQualityGrade.LOW})
            else:
                data = data.model_copy(update={"quality_grade": MilkQualityGrade.REJECTED})

        record = await self.repo.create(data)
        logger.info(
            f"Sut yozuvi qo'shildi: animal_id={data.animal_id}, "
            f"date={data.record_date}, milk_kg={data.milk_kg}"
        )
        return record

    async def update_record(
        self, record_id: int, data: MilkProductionUpdate
    ) -> MilkProduction:
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise EntityNotFoundError(f"Yozuv topilmadi: ID={record_id}")
        return await self.repo.update(record, data)

    async def delete_record(self, record_id: int) -> None:
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise EntityNotFoundError(f"Yozuv topilmadi: ID={record_id}")
        await self.repo.delete(record)

    async def get_animal_records(
        self,
        animal_id: int,
        *,
        page: int = 1,
        page_size: int = 30,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> MilkProductionListResponse:
        items, total = await self.repo.get_by_animal(
            animal_id,
            limit=page_size,
            offset=(page - 1) * page_size,
            date_from=date_from,
            date_to=date_to,
        )
        from app.schemas.milk_production import MilkProductionResponse
        return MilkProductionListResponse(
            items=[MilkProductionResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_animal_summary(self, animal_id: int) -> AnimalMilkSummary:
        """Jonivorning sut xulosasi."""
        animal = await self.animal_repo.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(f"Jonivor topilmadi: ID={animal_id}")

        stats_30d = await self.repo.get_animal_stats(animal_id, days=30)
        stats_7d = await self.repo.get_animal_stats(animal_id, days=7)
        today_kg = await self.repo.get_today_total(animal_id)
        recent_items, _ = await self.repo.get_by_animal(animal_id, limit=10)

        from app.schemas.milk_production import MilkProductionResponse
        return AnimalMilkSummary(
            animal_id=animal_id,
            animal_tag=animal.tag_id,
            current_lactation=None,
            days_in_milk=None,
            last_7_days_kg=stats_7d["total_kg"],
            last_30_days_kg=stats_30d["total_kg"],
            today_kg=today_kg,
            stats_30d=MilkStatsPeriod(
                total_kg=stats_30d["total_kg"],
                avg_daily_kg=stats_30d["avg_daily_kg"],
                avg_fat_percent=stats_30d.get("avg_fat_percent"),
                avg_protein_percent=stats_30d.get("avg_protein_percent"),
                avg_scc=stats_30d.get("avg_scc"),
                days_recorded=stats_30d["days_recorded"],
                best_day_kg=stats_30d.get("best_day_kg"),
                trend_percent=None,
            ),
            recent_records=[MilkProductionResponse.model_validate(r) for r in recent_items],
        )

    async def get_farm_summary(self) -> FarmMilkSummary:
        """Ferma bo'yicha sut xulosasi."""
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month_start = (first_of_month - timedelta(days=1)).replace(day=1)

        today_total = await self.repo.get_today_total()

        # Bu oylik
        this_month_records = await self.repo.get_farm_records(
            date_from=first_of_month, date_to=today
        )
        this_month_kg = sum(r.milk_kg for r in this_month_records)

        # O'tgan oylik
        last_month_records = await self.repo.get_farm_records(
            date_from=last_month_start,
            date_to=first_of_month - timedelta(days=1),
        )
        last_month_kg = sum(r.milk_kg for r in last_month_records)

        # 30 kunlik trend
        daily_trend = await self.repo.get_daily_totals(
            date_from=today - timedelta(days=29),
            date_to=today,
        )

        return FarmMilkSummary(
            today_total_kg=today_total,
            this_month_kg=round(this_month_kg, 2),
            last_month_kg=round(last_month_kg, 2),
            active_dairy_animals=len({r.animal_id for r in this_month_records}),
            avg_per_animal_kg=0,
            top_producers=[],
            daily_trend=daily_trend,
        )