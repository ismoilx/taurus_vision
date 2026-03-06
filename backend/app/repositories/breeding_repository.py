"""
Taurus Vision — Breeding Repository (Sprint 25-26)

Ma'lumotlar bazasi qatlami: barcha SQL so'rovlar shu yerda.
Service layer bu repository ni ishlatadi.

PATTERN:
    Barcha metodlar: async, db: AsyncSession argument oladi.
    Hech qanday biznes logika yo'q — faqat DB operatsiyalari.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, List, Tuple

from sqlalchemy import select, func, and_, or_, desc, extract
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.breeding import (
    BreedingRecord,
    BreedingStatus,
    OffspringRecord,
    MatingMethod,
)
from app.models.animal import Animal, AnimalGender, AnimalStatus
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BreedingRepository:
    """
    Nasl va homiladorlik ma'lumotlari uchun repository.
    """

    # =========================================================================
    # BREEDING RECORD — CREATE
    # =========================================================================

    async def create(
        self,
        db: AsyncSession,
        record: BreedingRecord,
    ) -> BreedingRecord:
        """Yangi nasl yozuvi yaratish."""
        db.add(record)
        await db.commit()
        await db.refresh(record)
        logger.info(f"BreedingRecord created: id={record.id}, mother={record.mother_id}")
        return record

    # =========================================================================
    # BREEDING RECORD — READ
    # =========================================================================

    async def get_by_id(
        self,
        db: AsyncSession,
        record_id: int,
        load_relations: bool = True,
    ) -> Optional[BreedingRecord]:
        """ID bo'yicha olish (mother, father, offspring bilan)."""
        q = select(BreedingRecord).where(BreedingRecord.id == record_id)
        if load_relations:
            q = q.options(
                selectinload(BreedingRecord.mother),
                selectinload(BreedingRecord.father),
                selectinload(BreedingRecord.offspring).selectinload(
                    OffspringRecord.animal
                ),
            )
        result = await db.execute(q)
        return result.scalar_one_or_none()

    async def get_list(
        self,
        db: AsyncSession,
        farm_id:    Optional[int]           = None,
        status:     Optional[BreedingStatus] = None,
        species:    Optional[str]           = None,
        mother_id:  Optional[int]           = None,
        father_id:  Optional[int]           = None,
        date_from:  Optional[date]          = None,
        date_to:    Optional[date]          = None,
        overdue_only: bool                  = False,
        skip: int = 0,
        limit: int = 20,
    ) -> Tuple[List[BreedingRecord], int]:
        """
        Filtrlangan va sahifalangan ro'yxat.

        Returns:
            (records, total_count) tuple
        """
        conditions = []

        if farm_id is not None:
            conditions.append(BreedingRecord.farm_id == farm_id)
        if status:
            conditions.append(BreedingRecord.status == status)
        if mother_id:
            conditions.append(BreedingRecord.mother_id == mother_id)
        if father_id:
            conditions.append(BreedingRecord.father_id == father_id)
        if date_from:
            conditions.append(BreedingRecord.mating_date >= date_from)
        if date_to:
            conditions.append(BreedingRecord.mating_date <= date_to)
        if overdue_only:
            conditions.append(
                and_(
                    BreedingRecord.status == BreedingStatus.CONFIRMED_PREGNANT,
                    BreedingRecord.expected_birth_date < date.today(),
                )
            )

        # Species filter (mother orqali join)
        if species:
            conditions.append(
                BreedingRecord.mother_id.in_(
                    select(Animal.id).where(Animal.species == species)
                )
            )

        where_clause = and_(*conditions) if conditions else True

        # Count
        count_q = select(func.count(BreedingRecord.id)).where(where_clause)
        total = (await db.execute(count_q)).scalar_one()

        # Data
        data_q = (
            select(BreedingRecord)
            .where(where_clause)
            .options(
                selectinload(BreedingRecord.mother),
                selectinload(BreedingRecord.father),
                selectinload(BreedingRecord.offspring),
            )
            .order_by(desc(BreedingRecord.mating_date))
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(data_q)
        records = list(result.scalars().all())

        return records, total

    async def get_active_pregnancies(
        self,
        db: AsyncSession,
        farm_id: Optional[int] = None,
    ) -> List[BreedingRecord]:
        """Hozirgi aktiv homiladorliklar (CONFIRMED_PREGNANT + PLANNED)."""
        conditions = [
            BreedingRecord.status.in_([
                BreedingStatus.CONFIRMED_PREGNANT,
                BreedingStatus.PLANNED,
            ])
        ]
        if farm_id:
            conditions.append(BreedingRecord.farm_id == farm_id)

        q = (
            select(BreedingRecord)
            .where(and_(*conditions))
            .options(
                selectinload(BreedingRecord.mother),
                selectinload(BreedingRecord.father),
            )
            .order_by(BreedingRecord.expected_birth_date)
        )
        result = await db.execute(q)
        return list(result.scalars().all())

    async def get_due_soon(
        self,
        db: AsyncSession,
        days: int = 14,
        farm_id: Optional[int] = None,
    ) -> List[BreedingRecord]:
        """Kelgusi N kunda tug'ilishi kutilayotganlar."""
        today = date.today()
        deadline = today + timedelta(days=days)

        conditions = [
            BreedingRecord.status == BreedingStatus.CONFIRMED_PREGNANT,
            BreedingRecord.expected_birth_date >= today,
            BreedingRecord.expected_birth_date <= deadline,
        ]
        if farm_id:
            conditions.append(BreedingRecord.farm_id == farm_id)

        q = (
            select(BreedingRecord)
            .where(and_(*conditions))
            .options(selectinload(BreedingRecord.mother))
            .order_by(BreedingRecord.expected_birth_date)
        )
        result = await db.execute(q)
        return list(result.scalars().all())

    async def get_by_animal(
        self,
        db: AsyncSession,
        animal_id: int,
    ) -> List[BreedingRecord]:
        """
        Jonivorning barcha nasl yozuvlari (ona sifatida yoki ota sifatida).
        """
        q = (
            select(BreedingRecord)
            .where(
                or_(
                    BreedingRecord.mother_id == animal_id,
                    BreedingRecord.father_id == animal_id,
                )
            )
            .options(
                selectinload(BreedingRecord.mother),
                selectinload(BreedingRecord.father),
                selectinload(BreedingRecord.offspring),
            )
            .order_by(desc(BreedingRecord.mating_date))
        )
        result = await db.execute(q)
        return list(result.scalars().all())

    # =========================================================================
    # BREEDING RECORD — UPDATE
    # =========================================================================

    async def update(
        self,
        db: AsyncSession,
        record: BreedingRecord,
    ) -> BreedingRecord:
        """Mavjud yozuvni saqlash."""
        await db.commit()
        await db.refresh(record)
        return record

    async def delete(
        self,
        db: AsyncSession,
        record: BreedingRecord,
    ) -> None:
        """Nasl yozuvini o'chirish (CASCADE — offspring ham o'chadi)."""
        await db.delete(record)
        await db.commit()
        logger.info(f"BreedingRecord deleted: id={record.id}")

    # =========================================================================
    # OFFSPRING
    # =========================================================================

    async def add_offspring(
        self,
        db: AsyncSession,
        offspring: OffspringRecord,
    ) -> OffspringRecord:
        db.add(offspring)
        await db.commit()
        await db.refresh(offspring)
        return offspring

    async def get_offspring_by_id(
        self,
        db: AsyncSession,
        offspring_id: int,
    ) -> Optional[OffspringRecord]:
        q = select(OffspringRecord).where(OffspringRecord.id == offspring_id)
        result = await db.execute(q)
        return result.scalar_one_or_none()

    async def get_offspring_by_breeding(
        self,
        db: AsyncSession,
        breeding_record_id: int,
    ) -> List[OffspringRecord]:
        q = (
            select(OffspringRecord)
            .where(OffspringRecord.breeding_record_id == breeding_record_id)
            .options(selectinload(OffspringRecord.animal))
            .order_by(OffspringRecord.birth_order)
        )
        result = await db.execute(q)
        return list(result.scalars().all())

    # =========================================================================
    # GENEALOGY — Shajara
    # =========================================================================

    async def get_ancestors_map(
        self,
        db: AsyncSession,
        animal_id: int,
        max_generations: int = 4,
    ) -> dict[int, tuple[Optional[int], Optional[int], Optional[str], Optional[str]]]:
        """
        Berilgan jonivorning barcha ota-onalari xaritasini qaytaradi.

        Returns:
            {animal_id: (mother_id, father_id, external_sire_tag, external_sire_breed)}

        ALGORITM:
            BFS orqali nasl yozuvlari orqali yuqoriga ko'tariladi.
            Har bir animal_id uchun ota-ona ID lari saqlanadi.
        """
        result: dict = {}
        visited: set = set()
        queue = [(animal_id, 0)]

        while queue:
            current_id, gen = queue.pop(0)
            if current_id in visited or gen >= max_generations:
                continue
            visited.add(current_id)

            # Bu jonivor ona bo'lgan eng so'nggi breeding recordni topish
            q = (
                select(BreedingRecord)
                .where(BreedingRecord.mother_id == current_id)
                .where(BreedingRecord.status == BreedingStatus.BIRTHED)
                .order_by(desc(BreedingRecord.actual_birth_date))
                .limit(1)
            )
            # Lekin bu yondashuv noto'g'ri — current_id TUG'ILGAN jonivor
            # Kerak bo'lgan: current_id OFFSPRING bo'lgan breeding record

            # Offspring yozuvi orqali breeding record topish
            off_q = (
                select(BreedingRecord)
                .join(
                    OffspringRecord,
                    and_(
                        OffspringRecord.breeding_record_id == BreedingRecord.id,
                        OffspringRecord.animal_id == current_id,
                    )
                )
                .options(
                    selectinload(BreedingRecord.mother),
                    selectinload(BreedingRecord.father),
                )
                .limit(1)
            )
            br_result = await db.execute(off_q)
            br = br_result.scalar_one_or_none()

            if br:
                result[current_id] = (
                    br.mother_id,
                    br.father_id,
                    br.external_sire_tag,
                    br.external_sire_breed,
                )
                if br.mother_id:
                    queue.append((br.mother_id, gen + 1))
                if br.father_id:
                    queue.append((br.father_id, gen + 1))
            else:
                result[current_id] = (None, None, None, None)

        return result

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(
        self,
        db: AsyncSession,
        farm_id: Optional[int] = None,
    ) -> dict:
        """Nasl statistikasini hisoblash."""
        today = date.today()
        current_year = today.year

        base_filter = []
        if farm_id:
            base_filter.append(BreedingRecord.farm_id == farm_id)
        base_where = and_(*base_filter) if base_filter else True

        # Jami
        total = (
            await db.execute(
                select(func.count(BreedingRecord.id)).where(base_where)
            )
        ).scalar_one()

        # Statuses
        status_rows = (
            await db.execute(
                select(BreedingRecord.status, func.count())
                .where(base_where)
                .group_by(BreedingRecord.status)
            )
        ).all()
        status_map = {row[0]: row[1] for row in status_rows}

        active_preg = status_map.get(BreedingStatus.CONFIRMED_PREGNANT, 0)
        planned     = status_map.get(BreedingStatus.PLANNED, 0)

        # Bu yil tug'ilganlar
        birthed_this_year = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.BIRTHED,
                        extract("year", BreedingRecord.actual_birth_date) == current_year,
                    )
                )
            )
        ).scalar_one()

        # Bu yil muvaffaqiyatsiz
        failed_year = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.FAILED,
                        extract("year", BreedingRecord.mating_date) == current_year,
                    )
                )
            )
        ).scalar_one()

        aborted_year = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.ABORTED,
                        extract("year", BreedingRecord.mating_date) == current_year,
                    )
                )
            )
        ).scalar_one()

        # Nasllar
        live_total = (
            await db.execute(
                select(func.coalesce(func.sum(BreedingRecord.live_offspring_count), 0))
                .where(base_where)
            )
        ).scalar_one()

        stillborn_total = (
            await db.execute(
                select(func.coalesce(func.sum(BreedingRecord.stillborn_count), 0))
                .where(base_where)
            )
        ).scalar_one()

        total_offspring = (live_total or 0) + (stillborn_total or 0)
        birthed_records = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(and_(base_where, BreedingRecord.status == BreedingStatus.BIRTHED))
            )
        ).scalar_one()

        avg_litter = round(
            total_offspring / birthed_records if birthed_records > 0 else 0.0, 2
        )
        stillbirth_rate = round(
            (stillborn_total / total_offspring * 100) if total_offspring > 0 else 0.0, 1
        )

        # Overdue
        overdue = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.CONFIRMED_PREGNANT,
                        BreedingRecord.expected_birth_date < today,
                    )
                )
            )
        ).scalar_one()

        due_7 = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.CONFIRMED_PREGNANT,
                        BreedingRecord.expected_birth_date.between(today, today + timedelta(days=7)),
                    )
                )
            )
        ).scalar_one()

        due_30 = (
            await db.execute(
                select(func.count(BreedingRecord.id))
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.CONFIRMED_PREGNANT,
                        BreedingRecord.expected_birth_date.between(today, today + timedelta(days=30)),
                    )
                )
            )
        ).scalar_one()

        # Usul bo'yicha
        method_rows = (
            await db.execute(
                select(BreedingRecord.mating_method, func.count())
                .where(base_where)
                .group_by(BreedingRecord.mating_method)
            )
        ).all()
        by_method = {row[0].value: row[1] for row in method_rows}

        # Oylik tug'ilishlar (so'nggi 12 oy)
        monthly_rows = (
            await db.execute(
                select(
                    extract("year",  BreedingRecord.actual_birth_date).label("yr"),
                    extract("month", BreedingRecord.actual_birth_date).label("mo"),
                    func.sum(BreedingRecord.live_offspring_count).label("cnt"),
                )
                .where(
                    and_(
                        base_where,
                        BreedingRecord.status == BreedingStatus.BIRTHED,
                        BreedingRecord.actual_birth_date >= (today.replace(day=1) - timedelta(days=365)),
                    )
                )
                .group_by("yr", "mo")
                .order_by("yr", "mo")
            )
        ).all()
        monthly_births = [
            {"month": f"{int(r.yr)}-{int(r.mo):02d}", "count": int(r.cnt or 0)}
            for r in monthly_rows
        ]

        return {
            "total_records":          total,
            "active_pregnancies":     active_preg,
            "planned":                planned,
            "birthed_this_year":      birthed_this_year,
            "failed_this_year":       failed_year,
            "aborted_this_year":      aborted_year,
            "total_live_offspring":   int(live_total or 0),
            "total_stillborn":        int(stillborn_total or 0),
            "avg_litter_size":        avg_litter,
            "stillbirth_rate_pct":    stillbirth_rate,
            "overdue_count":          overdue,
            "due_next_7_days":        due_7,
            "due_next_30_days":       due_30,
            "most_active_mother_tag": None,  # Service da hisoblanadi
            "most_used_sire_tag":     None,
            "by_mating_method":       by_method,
            "by_species":             {},    # Service da hisoblanadi
            "monthly_births":         monthly_births,
        }

    async def get_available_females(
        self,
        db: AsyncSession,
        farm_id: Optional[int] = None,
        species: Optional[str] = None,
    ) -> List[Animal]:
        """
        Naslga tayyor bo'lgan ona-jonivorlar.

        SHARTLAR:
            - status = ACTIVE
            - gender = FEMALE
            - CONFIRMED_PREGNANT holatida EMAS (hozir homilador emas)
        """
        # Hozir homilador bo'lgan ona IDlari
        pregnant_ids_q = (
            select(BreedingRecord.mother_id)
            .where(
                BreedingRecord.status.in_([
                    BreedingStatus.CONFIRMED_PREGNANT,
                    BreedingStatus.PLANNED,
                ])
            )
        )

        conditions = [
            Animal.status == AnimalStatus.ACTIVE,
            Animal.gender == AnimalGender.FEMALE,
            Animal.id.notin_(pregnant_ids_q),
        ]
        if farm_id:
            conditions.append(Animal.farm_id == farm_id)
        if species:
            conditions.append(Animal.species == species)

        q = select(Animal).where(and_(*conditions)).order_by(Animal.tag_id)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def get_available_males(
        self,
        db: AsyncSession,
        farm_id: Optional[int] = None,
        species: Optional[str] = None,
    ) -> List[Animal]:
        """Naslga tayyor bo'lgan ota-jonivorlar."""
        conditions = [
            Animal.status == AnimalStatus.ACTIVE,
            Animal.gender == AnimalGender.MALE,
        ]
        if farm_id:
            conditions.append(Animal.farm_id == farm_id)
        if species:
            conditions.append(Animal.species == species)

        q = select(Animal).where(and_(*conditions)).order_by(Animal.tag_id)
        result = await db.execute(q)
        return list(result.scalars().all())