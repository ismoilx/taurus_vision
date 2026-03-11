"""
Taurus Vision — Go'sht Ishlab Chiqarish Servisi

Biznes logika: validatsiya, statistika, summaries.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging_config import get_logger
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.repositories.meat_production_repository import MeatProductionRepository
from app.repositories.animal import AnimalRepository
from app.models.meat_production import SlaughterRecord, SlaughterPurpose, MeatQualityGrade
from app.schemas.meat_production import (
    SlaughterRecordCreate,
    SlaughterRecordUpdate,
    SlaughterRecordListResponse,
    SlaughterRecordResponse,
    AnimalMeatSummary,
    FarmMeatSummary,
    MeatStatsPeriod,
)

logger = get_logger(__name__)


class MeatService:
    """Go'sht ishlab chiqarish biznes logikasi."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = MeatProductionRepository(db)
        self.animal_repo = AnimalRepository(db)

    async def add_record(self, data: SlaughterRecordCreate) -> SlaughterRecord:
        """
        Yangi so'yish yozuvi qo'shish.

        Args:
            data: So'yish yozuvi ma'lumotlari

        Returns:
            Yaratilgan yozuv

        Raises:
            EntityNotFoundError: Jonivor topilmasa
        """
        animal = await self.animal_repo.get_by_id(data.animal_id)
        if not animal:
            raise EntityNotFoundError(f"Jonivor topilmadi: ID={data.animal_id}")

        # Sifat darajasini avtomatik hisoblash (pH asosida)
        if data.quality_grade is None and data.ph_value is not None:
            ph = data.ph_value
            if ph <= 5.8:
                data = data.model_copy(update={"quality_grade": MeatQualityGrade.PREMIUM})
            elif ph <= 6.2:
                data = data.model_copy(update={"quality_grade": MeatQualityGrade.CHOICE})
            elif ph <= 6.5:
                data = data.model_copy(update={"quality_grade": MeatQualityGrade.SELECT})
            elif ph <= 6.8:
                data = data.model_copy(update={"quality_grade": MeatQualityGrade.STANDARD})
            else:
                data = data.model_copy(update={"quality_grade": MeatQualityGrade.LOW})

        record = await self.repo.create(data)
        logger.info(
            f"So'yish yozuvi qo'shildi: animal_id={data.animal_id}, "
            f"date={data.slaughter_date}, meat_kg={data.meat_kg}"
        )
        return record

    async def update_record(
        self, record_id: int, data: SlaughterRecordUpdate
    ) -> SlaughterRecord:
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise EntityNotFoundError(f"Yozuv topilmadi: ID={record_id}")
        return await self.repo.update(record, data)

    async def delete_record(self, record_id: int) -> None:
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise EntityNotFoundError(f"Yozuv topilmadi: ID={record_id}")
        await self.repo.delete(record)

    async def get_record_by_id(self, record_id: int) -> SlaughterRecordResponse:
        """Yozuvni animal ma'lumotlari bilan birga qaytarish."""
        from app.models.animal import Animal
        record = await self.repo.get_by_id(record_id)
        if not record:
            raise EntityNotFoundError(f"Yozuv topilmadi: ID={record_id}")
        return await self._enrich_record(record)

    async def get_all_records(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        purpose: Optional[SlaughterPurpose] = None,
        quality_grade: Optional[MeatQualityGrade] = None,
    ) -> SlaughterRecordListResponse:
        """Barcha yozuvlar (filter va pagination bilan)."""
        items, total = await self.repo.get_all_records(
            date_from=date_from,
            date_to=date_to,
            purpose=purpose,
            quality_grade=quality_grade,
            limit=page_size,
            offset=(page - 1) * page_size,
        )
        enriched = [await self._enrich_record(r) for r in items]
        return SlaughterRecordListResponse(
            items=enriched,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_animal_records(
        self,
        animal_id: int,
        *,
        page: int = 1,
        page_size: int = 30,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> SlaughterRecordListResponse:
        items, total = await self.repo.get_by_animal(
            animal_id,
            limit=page_size,
            offset=(page - 1) * page_size,
            date_from=date_from,
            date_to=date_to,
        )
        return SlaughterRecordListResponse(
            items=[SlaughterRecordResponse.model_validate(i) for i in items],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_animal_summary(self, animal_id: int) -> AnimalMeatSummary:
        """Jonivorning go'sht xulosasi."""
        animal = await self.animal_repo.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(f"Jonivor topilmadi: ID={animal_id}")

        stats = await self.repo.get_animal_stats(animal_id)
        recent_items, _ = await self.repo.get_by_animal(animal_id, limit=10)

        return AnimalMeatSummary(
            animal_id=animal_id,
            animal_tag=animal.tag_id,
            animal_name=getattr(animal, "name", None),
            animal_species=animal.species.value if animal.species else "unknown",
            total_records=stats["record_count"],
            total_meat_kg=stats["total_meat_kg"],
            last_slaughter_date=stats["last_date"],
            avg_meat_kg=stats["avg_meat_kg"],
            total_revenue=stats["total_revenue"],
            recent_records=[SlaughterRecordResponse.model_validate(r) for r in recent_items],
        )

    async def get_farm_summary(
        self,
        *,
        days_trend: int = 30,
    ) -> FarmMeatSummary:
        """Ferma bo'yicha go'sht xulosasi."""
        today = date.today()
        first_of_month = today.replace(day=1)
        last_month_start = (first_of_month - timedelta(days=1)).replace(day=1)
        last_month_end = first_of_month - timedelta(days=1)

        # Bugungi stats
        today_stats = await self.repo.get_today_stats()

        # Bu oylik
        this_month_records = await self.repo.get_farm_records(
            date_from=first_of_month, date_to=today
        )
        this_month_kg = round(sum(r.meat_kg for r in this_month_records), 2)
        this_month_animals = len(this_month_records)
        this_month_revenue = sum(r.total_revenue or 0 for r in this_month_records) or None

        # O'tgan oylik
        last_month_records = await self.repo.get_farm_records(
            date_from=last_month_start, date_to=last_month_end
        )
        last_month_kg = round(sum(r.meat_kg for r in last_month_records), 2)
        last_month_animals = len(last_month_records)
        last_month_revenue = sum(r.total_revenue or 0 for r in last_month_records) or None

        # Jami statistika
        all_records = await self.repo.get_farm_records(
            date_from=date(2000, 1, 1), date_to=today
        )
        all_time_kg = round(sum(r.meat_kg for r in all_records), 2)
        all_time_animals = len(all_records)

        # 30 kunlik trend
        daily_trend = await self.repo.get_daily_totals(
            date_from=today - timedelta(days=days_trend - 1),
            date_to=today,
        )

        # Maqsad bo'yicha
        purpose_breakdown = await self.repo.get_purpose_breakdown(
            date_from=first_of_month, date_to=today
        )

        # Sifat bo'yicha
        quality_breakdown = await self.repo.get_quality_breakdown(
            date_from=first_of_month, date_to=today
        )

        # Top jonivorlar
        top_animals_raw = await self.repo.get_top_animals(
            date_from=first_of_month, date_to=today, limit=10
        )
        top_animals = await self._enrich_animal_list(top_animals_raw)

        return FarmMeatSummary(
            today_animals_count=today_stats["animals_count"],
            today_meat_kg=today_stats["meat_kg"],
            today_revenue=today_stats["revenue"],
            this_month_animals=this_month_animals,
            this_month_kg=this_month_kg,
            this_month_revenue=round(this_month_revenue, 2) if this_month_revenue else None,
            last_month_animals=last_month_animals,
            last_month_kg=last_month_kg,
            last_month_revenue=round(last_month_revenue, 2) if last_month_revenue else None,
            all_time_animals=all_time_animals,
            all_time_kg=all_time_kg,
            daily_trend=daily_trend,
            purpose_breakdown=purpose_breakdown,
            quality_breakdown=quality_breakdown,
            top_animals=top_animals,
        )

    async def get_farm_records_enriched(
        self,
        *,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ) -> list[dict]:
        """
        Ferma bo'yicha barcha yozuvlar + jonivor ma'lumotlari.
        Frontend jadval uchun.
        """
        today = date.today()
        if date_from is None:
            date_from = today.replace(day=1)
        if date_to is None:
            date_to = today

        records = await self.repo.get_farm_records(date_from=date_from, date_to=date_to)
        if not records:
            return []

        animal_ids = list({r.animal_id for r in records})
        from app.models.animal import Animal
        result = await self.db.execute(
            select(Animal.id, Animal.tag_id, Animal.name, Animal.species, Animal.breed)
            .where(Animal.id.in_(animal_ids))
        )
        animal_map: dict[int, dict] = {
            row.id: {
                "tag_id":  row.tag_id,
                "name":    row.name or "",
                "species": row.species.value if row.species else "",
                "breed":   row.breed or "",
            }
            for row in result.all()
        }

        enriched = []
        for r in records:
            animal = animal_map.get(r.animal_id, {})
            enriched.append({
                "id":               r.id,
                "animal_id":        r.animal_id,
                "tag_id":           animal.get("tag_id", f"#{r.animal_id}"),
                "name":             animal.get("name", ""),
                "species":          animal.get("species", ""),
                "breed":            animal.get("breed", ""),
                "slaughter_date":   str(r.slaughter_date),
                "purpose":          r.purpose.value if r.purpose else "sale",
                "live_weight_kg":   r.live_weight_kg,
                "carcass_weight_kg": r.carcass_weight_kg,
                "dressing_percent": r.dressing_percent,
                "meat_kg":          r.meat_kg,
                "bone_kg":          r.bone_kg,
                "fat_kg":           r.fat_kg,
                "offal_kg":         r.offal_kg,
                "hide_kg":          r.hide_kg,
                "quality_grade":    r.quality_grade.value if r.quality_grade else None,
                "ph_value":         r.ph_value,
                "price_per_kg":     r.price_per_kg,
                "total_revenue":    r.total_revenue,
                "veterinary_check": r.veterinary_check,
                "slaughtered_by":   r.slaughtered_by,
                "notes":            r.notes,
            })

        return sorted(enriched, key=lambda x: x["slaughter_date"], reverse=True)

    # ── Private helpers ───────────────────────────────────────────────

    async def _enrich_record(self, record: SlaughterRecord) -> SlaughterRecordResponse:
        """Yozuvni jonivor ma'lumotlari bilan boyitish."""
        from app.models.animal import Animal
        result = await self.db.execute(
            select(Animal.tag_id, Animal.name, Animal.species, Animal.breed)
            .where(Animal.id == record.animal_id)
        )
        row = result.one_or_none()
        resp = SlaughterRecordResponse.model_validate(record)
        if row:
            resp.animal_tag     = row.tag_id
            resp.animal_name    = row.name
            resp.animal_species = row.species.value if row.species else None
            resp.animal_breed   = row.breed
        return resp

    async def _enrich_animal_list(self, raw_list: list[dict]) -> list[dict]:
        """Top animals ro'yxatini jonivor ma'lumotlari bilan boyitish."""
        if not raw_list:
            return []
        from app.models.animal import Animal
        animal_ids = [r["animal_id"] for r in raw_list]
        result = await self.db.execute(
            select(Animal.id, Animal.tag_id, Animal.name, Animal.species, Animal.breed)
            .where(Animal.id.in_(animal_ids))
        )
        animal_map = {
            row.id: {
                "tag_id":  row.tag_id,
                "name":    row.name or "",
                "species": row.species.value if row.species else "",
                "breed":   row.breed or "",
            }
            for row in result.all()
        }
        enriched = []
        for item in raw_list:
            animal = animal_map.get(item["animal_id"], {})
            enriched.append({**item, **animal})
        return enriched