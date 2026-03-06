"""
Taurus Vision — Breeding Service (Sprint 25-26)

BIZNES LOGIKA QATLAMI.

Ushbu service quyidagilarni boshqaradi:
    1. Nasl yozuvi yaratish + validatsiya (gestatsiya avtomatik hisoblash)
    2. Homiladorlikni tasdiqlash
    3. Tug'ilishni qayd etish (offspring records)
    4. Shajara daraxti (genealogy tree) — rekursiv BFS
    5. Nasl tavsiyalari (breeding recommendations) — scoring algoritm
    6. Statistika

ARXITEKTURA QOIDASI:
    Service → Repository → DB
    Service hech qachon to'g'ridan-to'g'ri DB ga yozmaydi.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.breeding import (
    BreedingRecord,
    BreedingStatus,
    OffspringRecord,
    GESTATION_DAYS,
    MatingMethod,
)
from app.models.animal import Animal, AnimalGender, AnimalStatus
from app.repositories.breeding_repository import BreedingRepository
from app.repositories.animal import AnimalRepository
from app.schemas.breeding import (
    BreedingRecordCreate,
    BreedingRecordUpdate,
    BreedingConfirmPregnancy,
    BreedingRecordBirth,
    BreedingMarkFailed,
    BreedingMarkAborted,
    BreedingRecordResponse,
    BreedingRecordList,
    OffspringResponse,
    GenealogyNode,
    BreedingStats,
    BreedingRecommendation,
    BreedingRecommendationList,
    AnimalBrief,
)
from app.core.exceptions import (
    EntityNotFoundError,
    BusinessRuleViolationError,
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class BreedingService:
    """
    Nasl va zotchilik boshqaruvi uchun service.

    Args:
        db: Async database session (injected per request).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = BreedingRepository()
        self.animal_repo = AnimalRepository(db)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _build_response(self, record: BreedingRecord) -> BreedingRecordResponse:
        """BreedingRecord → BreedingRecordResponse."""
        offspring_resp = []
        for off in (record.offspring or []):
            animal_tag = off.animal.tag_id if off.animal else None
            offspring_resp.append(
                OffspringResponse(
                    id=off.id,
                    breeding_record_id=off.breeding_record_id,
                    animal_id=off.animal_id,
                    birth_order=off.birth_order,
                    gender=off.gender,
                    birth_weight_kg=off.birth_weight_kg,
                    outcome=off.outcome,
                    notes=off.notes,
                    created_at=off.created_at,
                    animal_tag_id=animal_tag,
                )
            )

        mother_brief = None
        if record.mother:
            mother_brief = AnimalBrief(
                id=record.mother.id,
                tag_id=record.mother.tag_id,
                species=record.mother.species.value,
                breed=record.mother.breed,
                gender=record.mother.gender.value,
                status=record.mother.status.value,
            )

        father_brief = None
        if record.father:
            father_brief = AnimalBrief(
                id=record.father.id,
                tag_id=record.father.tag_id,
                species=record.father.species.value,
                breed=record.father.breed,
                gender=record.father.gender.value,
                status=record.father.status.value,
            )

        return BreedingRecordResponse(
            id=record.id,
            farm_id=record.farm_id,
            mother_id=record.mother_id,
            father_id=record.father_id,
            external_sire_tag=record.external_sire_tag,
            external_sire_breed=record.external_sire_breed,
            external_sire_farm=record.external_sire_farm,
            mating_date=record.mating_date,
            mating_method=record.mating_method,
            status=record.status,
            gestation_days=record.gestation_days,
            expected_birth_date=record.expected_birth_date,
            pregnancy_confirmed_at=record.pregnancy_confirmed_at,
            pregnancy_check_method=record.pregnancy_check_method,
            pregnancy_check_notes=record.pregnancy_check_notes,
            actual_birth_date=record.actual_birth_date,
            live_offspring_count=record.live_offspring_count,
            stillborn_count=record.stillborn_count,
            birth_complications=record.birth_complications,
            abort_date=record.abort_date,
            abort_reason=record.abort_reason,
            veterinarian=record.veterinarian,
            notes=record.notes,
            created_by_id=record.created_by_id,
            created_at=record.created_at,
            updated_at=record.updated_at,
            # Computed fields
            pregnancy_progress_pct=record.pregnancy_progress_pct,
            days_until_birth=record.days_until_birth,
            is_overdue=record.is_overdue,
            total_offspring=record.total_offspring,
            sire_label=record.sire_label,
            mother=mother_brief,
            father=father_brief,
            offspring=offspring_resp,
        )

    def _get_gestation(self, species: str, override: Optional[int]) -> int:
        """Species bo'yicha gestatsiya kunini aniqlash."""
        if override:
            return override
        return GESTATION_DAYS.get(species.lower(), 283)

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create_record(
        self,
        data: BreedingRecordCreate,
        created_by_id: int,
    ) -> BreedingRecordResponse:
        """
        Yangi nasl yozuvi yaratish.

        VALIDATSIYALAR:
            1. Ona jonivor mavjud + female + active
            2. Ota jonivor (agar ichki) mavjud + male + active
            3. Bir xil species (agar ichki ota)
            4. Gestatsiya avtomatik hisoblanadi
        """
        # 1. Ona tekshiruvi
        mother = await self.animal_repo.get_by_id(data.mother_id)
        if not mother:
            raise EntityNotFoundError(
                entity="Animal", entity_id=data.mother_id,
                message=f"Ona jonivor topilmadi: id={data.mother_id}",
            )
        if mother.gender != AnimalGender.FEMALE:
            raise BusinessRuleViolationError(
                message="Ona jonivor female (urg'ochi) bo'lishi kerak.",
                details={"animal_id": data.mother_id, "gender": mother.gender.value},
            )
        if mother.status != AnimalStatus.ACTIVE:
            raise BusinessRuleViolationError(
                message="Ona jonivor aktiv bo'lishi kerak.",
                details={"animal_id": data.mother_id, "status": mother.status.value},
            )

        # 2. Ota tekshiruvi (agar ichki)
        father: Optional[Animal] = None
        if data.father_id:
            father = await self.animal_repo.get_by_id(data.father_id)
            if not father:
                raise EntityNotFoundError(
                    entity="Animal", entity_id=data.father_id,
                    message=f"Ota jonivor topilmadi: id={data.father_id}",
                )
            if father.gender != AnimalGender.MALE:
                raise BusinessRuleViolationError(
                    message="Ota jonivor male (erkak) bo'lishi kerak.",
                    details={"animal_id": data.father_id, "gender": father.gender.value},
                )
            if father.status != AnimalStatus.ACTIVE:
                raise BusinessRuleViolationError(
                    message="Ota jonivor aktiv bo'lishi kerak.",
                    details={"animal_id": data.father_id, "status": father.status.value},
                )
            if mother.species != father.species:
                raise BusinessRuleViolationError(
                    message="Ona va ota bir xil tur (species) bo'lishi kerak.",
                    details={
                        "mother_species": mother.species.value,
                        "father_species": father.species.value,
                    },
                )

        # 3. Gestatsiya va kutilgan sana
        gestation = self._get_gestation(mother.species.value, data.gestation_days)
        expected = data.expected_birth_date or (
            data.mating_date + timedelta(days=gestation)
        )

        # 4. Model yaratish
        record = BreedingRecord(
            farm_id=data.farm_id or mother.farm_id,
            mother_id=data.mother_id,
            father_id=data.father_id,
            external_sire_tag=data.external_sire_tag,
            external_sire_breed=data.external_sire_breed,
            external_sire_farm=data.external_sire_farm,
            mating_date=data.mating_date,
            mating_method=data.mating_method,
            status=BreedingStatus.PLANNED,
            gestation_days=gestation,
            expected_birth_date=expected,
            veterinarian=data.veterinarian,
            notes=data.notes,
            created_by_id=created_by_id,
        )

        saved = await self.repo.create(self.db, record)
        # Relations ni yuklash
        full = await self.repo.get_by_id(self.db, saved.id)
        logger.info(
            f"Breeding record created: id={saved.id}, "
            f"mother={mother.tag_id}, "
            f"sire={'internal:'+str(father.tag_id) if father else 'external:'+str(data.external_sire_tag)}"
        )
        return self._build_response(full)

    # =========================================================================
    # READ
    # =========================================================================

    async def get_record(self, record_id: int) -> BreedingRecordResponse:
        record = await self.repo.get_by_id(self.db, record_id)
        if not record:
            raise EntityNotFoundError(
                entity="BreedingRecord", entity_id=record_id,
            )
        return self._build_response(record)

    async def get_list(
        self,
        farm_id:      Optional[int]           = None,
        status:       Optional[BreedingStatus] = None,
        species:      Optional[str]           = None,
        mother_id:    Optional[int]           = None,
        father_id:    Optional[int]           = None,
        date_from:    Optional[date]          = None,
        date_to:      Optional[date]          = None,
        overdue_only: bool                    = False,
        page: int = 1,
        size: int = 20,
    ) -> BreedingRecordList:
        skip = (page - 1) * size
        records, total = await self.repo.get_list(
            self.db,
            farm_id=farm_id,
            status=status,
            species=species,
            mother_id=mother_id,
            father_id=father_id,
            date_from=date_from,
            date_to=date_to,
            overdue_only=overdue_only,
            skip=skip,
            limit=size,
        )
        import math
        return BreedingRecordList(
            total=total,
            page=page,
            size=size,
            pages=math.ceil(total / size) if total > 0 else 1,
            items=[self._build_response(r) for r in records],
        )

    async def get_active_pregnancies(
        self, farm_id: Optional[int] = None
    ) -> List[BreedingRecordResponse]:
        records = await self.repo.get_active_pregnancies(self.db, farm_id)
        return [self._build_response(r) for r in records]

    async def get_animal_breeding_history(
        self, animal_id: int
    ) -> List[BreedingRecordResponse]:
        animal = await self.animal_repo.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(entity="Animal", entity_id=animal_id)
        records = await self.repo.get_by_animal(self.db, animal_id)
        return [self._build_response(r) for r in records]

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update_record(
        self,
        record_id: int,
        data: BreedingRecordUpdate,
    ) -> BreedingRecordResponse:
        record = await self.repo.get_by_id(self.db, record_id)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status == BreedingStatus.BIRTHED:
            raise BusinessRuleViolationError(
                message="Tug'ilgan yozuvni o'zgartirish mumkin emas.",
            )

        update_data = data.model_dump(exclude_none=True)
        for field, value in update_data.items():
            setattr(record, field, value)

        updated = await self.repo.update(self.db, record)
        full = await self.repo.get_by_id(self.db, updated.id)
        return self._build_response(full)

    # =========================================================================
    # STATE TRANSITIONS
    # =========================================================================

    async def confirm_pregnancy(
        self,
        record_id: int,
        data: BreedingConfirmPregnancy,
    ) -> BreedingRecordResponse:
        """PLANNED → CONFIRMED_PREGNANT."""
        record = await self.repo.get_by_id(self.db, record_id)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status not in (BreedingStatus.PLANNED, BreedingStatus.CONFIRMED_PREGNANT):
            raise BusinessRuleViolationError(
                message=f"Homiladorlikni tasdiqlash uchun holat PLANNED yoki CONFIRMED_PREGNANT bo'lishi kerak. Hozir: {record.status.value}",
            )

        record.status = BreedingStatus.CONFIRMED_PREGNANT
        record.pregnancy_confirmed_at = data.confirmed_at
        record.pregnancy_check_method = data.check_method
        record.pregnancy_check_notes = data.check_notes
        if data.expected_birth_date:
            record.expected_birth_date = data.expected_birth_date

        updated = await self.repo.update(self.db, record)
        full = await self.repo.get_by_id(self.db, updated.id)
        logger.info(f"Pregnancy confirmed: breeding_id={record_id}")
        return self._build_response(full)

    async def record_birth(
        self,
        record_id: int,
        data: BreedingRecordBirth,
    ) -> BreedingRecordResponse:
        """
        CONFIRMED_PREGNANT / PLANNED → BIRTHED.

        Tug'ilishni qayd etish va offspring yozuvlarini yaratish.
        """
        record = await self.repo.get_by_id(self.db, record_id, load_relations=True)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status == BreedingStatus.BIRTHED:
            raise BusinessRuleViolationError(
                message="Bu yozuv allaqachon tug'ildi deb belgilangan.",
            )
        if record.status in (BreedingStatus.FAILED, BreedingStatus.ABORTED):
            raise BusinessRuleViolationError(
                message=f"Holati '{record.status.value}' — tug'ilish qayd etib bo'lmaydi.",
            )

        live_count     = sum(1 for o in data.offspring if o.outcome.value == "alive")
        stillborn_count = sum(1 for o in data.offspring if o.outcome.value != "alive")

        record.status              = BreedingStatus.BIRTHED
        record.actual_birth_date   = data.actual_birth_date
        record.live_offspring_count = live_count
        record.stillborn_count     = stillborn_count
        record.birth_complications  = data.birth_complications
        if data.notes:
            record.notes = (record.notes or "") + f"\n[Tug'ilish]: {data.notes}"

        await self.repo.update(self.db, record)

        # Offspring records yaratish
        for off_data in data.offspring:
            offspring = OffspringRecord(
                breeding_record_id=record_id,
                birth_order=off_data.birth_order,
                gender=off_data.gender,
                birth_weight_kg=off_data.birth_weight_kg,
                outcome=off_data.outcome,
                notes=off_data.notes,
            )
            await self.repo.add_offspring(self.db, offspring)

        full = await self.repo.get_by_id(self.db, record_id)
        logger.info(
            f"Birth recorded: breeding_id={record_id}, "
            f"live={live_count}, stillborn={stillborn_count}"
        )
        return self._build_response(full)

    async def mark_failed(
        self,
        record_id: int,
        data: BreedingMarkFailed,
    ) -> BreedingRecordResponse:
        """Muvaffaqiyatsiz — homiladorlik bo'lmadi."""
        record = await self.repo.get_by_id(self.db, record_id)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status == BreedingStatus.BIRTHED:
            raise BusinessRuleViolationError(
                message="Tug'ilgan yozuvni muvaffaqiyatsiz deb belgilab bo'lmaydi.",
            )

        record.status = BreedingStatus.FAILED
        if data.reason:
            record.notes = (record.notes or "") + f"\n[Sabab]: {data.reason}"

        updated = await self.repo.update(self.db, record)
        full = await self.repo.get_by_id(self.db, updated.id)
        return self._build_response(full)

    async def mark_aborted(
        self,
        record_id: int,
        data: BreedingMarkAborted,
    ) -> BreedingRecordResponse:
        """Abort belgilash."""
        record = await self.repo.get_by_id(self.db, record_id)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status == BreedingStatus.BIRTHED:
            raise BusinessRuleViolationError(
                message="Tug'ilgan yozuvni abort deb belgilab bo'lmaydi.",
            )

        record.status      = BreedingStatus.ABORTED
        record.abort_date  = data.abort_date
        record.abort_reason = data.abort_reason

        updated = await self.repo.update(self.db, record)
        full = await self.repo.get_by_id(self.db, updated.id)
        return self._build_response(full)

    async def delete_record(self, record_id: int) -> None:
        """O'chirish — faqat PLANNED holati o'chirilishi mumkin."""
        record = await self.repo.get_by_id(self.db, record_id, load_relations=False)
        if not record:
            raise EntityNotFoundError(entity="BreedingRecord", entity_id=record_id)

        if record.status not in (BreedingStatus.PLANNED, BreedingStatus.FAILED):
            raise BusinessRuleViolationError(
                message="Faqat PLANNED yoki FAILED holiatdagi yozuvlarni o'chirish mumkin.",
                details={"current_status": record.status.value},
            )
        await self.repo.delete(self.db, record)

    async def link_offspring_to_animal(
        self,
        offspring_id: int,
        animal_id: int,
    ) -> OffspringResponse:
        """Tug'ilgan naslni ro'yxatdagi jonivorgа bog'lash."""
        offspring = await self.repo.get_offspring_by_id(self.db, offspring_id)
        if not offspring:
            raise EntityNotFoundError(entity="OffspringRecord", entity_id=offspring_id)

        animal = await self.animal_repo.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(entity="Animal", entity_id=animal_id)

        offspring.animal_id = animal_id
        await self.db.commit()
        await self.db.refresh(offspring)

        return OffspringResponse(
            id=offspring.id,
            breeding_record_id=offspring.breeding_record_id,
            animal_id=offspring.animal_id,
            birth_order=offspring.birth_order,
            gender=offspring.gender,
            birth_weight_kg=offspring.birth_weight_kg,
            outcome=offspring.outcome,
            notes=offspring.notes,
            created_at=offspring.created_at,
            animal_tag_id=animal.tag_id,
        )

    # =========================================================================
    # GENEALOGY — Shajara daraxti
    # =========================================================================

    async def get_genealogy(
        self,
        animal_id: int,
        max_generations: int = 3,
    ) -> GenealogyNode:
        """
        Jonivorning shajara daraxtini qaytarish.

        Rekursiv BFS yordamida ota-ona zanjirini quramiz.

        Args:
            animal_id: Bosh jonivor ID
            max_generations: Necha avlod yuqoriga (max 5)
        """
        if max_generations > 5:
            max_generations = 5

        animal = await self.animal_repo.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(entity="Animal", entity_id=animal_id)

        # Barcha ota-onalar xaritasini olish
        ancestors_map = await self.repo.get_ancestors_map(
            self.db, animal_id, max_generations
        )

        # Jonivor ma'lumotlarini olish
        all_animal_ids = set()
        for anc_id, (m_id, f_id, _, _) in ancestors_map.items():
            all_animal_ids.add(anc_id)
            if m_id: all_animal_ids.add(m_id)
            if f_id: all_animal_ids.add(f_id)

        from sqlalchemy import select as sa_select
        animals_q = sa_select(Animal).where(Animal.id.in_(all_animal_ids))
        result = await self.db.execute(animals_q)
        animals_dict = {a.id: a for a in result.scalars().all()}

        def _build_node(aid: int, gen: int) -> GenealogyNode:
            a = animals_dict.get(aid)
            if not a:
                return GenealogyNode(
                    animal_id=aid, tag_id=None, species=None, breed=None,
                    gender=None, birth_date=None, generation=gen,
                )

            node = GenealogyNode(
                animal_id=a.id,
                tag_id=a.tag_id,
                species=a.species.value if a.species else None,
                breed=a.breed,
                gender=a.gender.value if a.gender else None,
                birth_date=a.birth_date.date() if isinstance(a.birth_date, __import__("datetime").datetime) else a.birth_date,
                is_external=False,
                generation=gen,
            )

            if gen >= max_generations:
                return node

            ancestry = ancestors_map.get(aid, (None, None, None, None))
            mother_id, father_id, ext_tag, ext_breed = ancestry

            if mother_id:
                node.mother = _build_node(mother_id, gen + 1)
            if father_id:
                node.father = _build_node(father_id, gen + 1)
            elif ext_tag:
                node.father = GenealogyNode(
                    animal_id=None,
                    tag_id=ext_tag,
                    species=None,
                    breed=ext_breed,
                    gender="male",
                    birth_date=None,
                    is_external=True,
                    external_label=f"Tashqi: {ext_tag}" + (f" ({ext_breed})" if ext_breed else ""),
                    generation=gen + 1,
                )
            return node

        return _build_node(animal_id, 0)

    # =========================================================================
    # BREEDING RECOMMENDATIONS — Juft tavsiyalari
    # =========================================================================

    async def get_recommendations(
        self,
        farm_id: Optional[int] = None,
        species: Optional[str] = None,
        top_n: int = 10,
    ) -> BreedingRecommendationList:
        """
        Optimal juftlashish tavsiyalari.

        SCORING ALGORITMI (100 baldan):
            1. Genetic diversity (40 ball)
               - Agar ota-ona common ancestor bo'lsa: -20 ball har darajada
               - 3+ avlod uzoqlik: to'liq 40 ball

            2. ADI compatibility (30 ball)
               - Ikkala jonivor ADI > 70: +30
               - ADI > 60: +20
               - ADI > 50: +10

            3. Weight compatibility (20 ball)
               - Ota vazni ona vaznidan 10-50% yuqori: +20
               - 50-100% yuqori: +10
               - Teng yoki past: +5

            4. Breed compatibility (10 ball)
               - Bir xil zot: +10
               - Mos zotlar: +7
               - Har xil: +3
        """
        females = await self.repo.get_available_females(self.db, farm_id, species)
        males   = await self.repo.get_available_males(self.db, farm_id, species)

        recommendations: list[BreedingRecommendation] = []

        # ADI ma'lumotlarini olish
        try:
            from app.services.adi_service import ADIService
            adi_svc = ADIService(self.db)
            # female ADI scores
            female_adi: dict[int, float] = {}
            male_adi:   dict[int, float] = {}
            for f in females:
                try:
                    score = await adi_svc.get_latest_score(f.id)
                    female_adi[f.id] = score or 60.0
                except Exception:
                    female_adi[f.id] = 60.0
            for m in males:
                try:
                    score = await adi_svc.get_latest_score(m.id)
                    male_adi[m.id] = score or 60.0
                except Exception:
                    male_adi[m.id] = 60.0
        except Exception:
            female_adi = {f.id: 65.0 for f in females}
            male_adi   = {m.id: 65.0 for m in males}

        # Weight measurements
        try:
            from app.repositories.weight_measurement_repository import WeightMeasurementRepository
            wm_repo = WeightMeasurementRepository()
            female_weights: dict[int, float] = {}
            male_weights: dict[int, float] = {}
            for f in females:
                try:
                    w = await wm_repo.get_latest(self.db, f.id)
                    female_weights[f.id] = w.weight_kg if w else 0.0
                except Exception:
                    female_weights[f.id] = 0.0
            for m in males:
                try:
                    w = await wm_repo.get_latest(self.db, m.id)
                    male_weights[m.id] = w.weight_kg if w else 0.0
                except Exception:
                    male_weights[m.id] = 0.0
        except Exception:
            female_weights = {f.id: 0.0 for f in females}
            male_weights   = {m.id: 0.0 for m in males}

        # Juftlarni baholash
        pairs: list[tuple[float, Animal, Animal]] = []

        for female in females:
            for male in males:
                if female.species != male.species:
                    continue

                # 1. Genetic diversity score (0-40)
                gen_score = 40.0  # Default — biz faqat DB dagi nasl orqali tekshiramiz
                # Oddiy tekshiruv: ota yoki ona bir xil emasligini qarang
                # (To'liq COI hisoblash kelajak versiyada)

                # 2. ADI compatibility (0-30)
                f_adi = female_adi.get(female.id, 60.0)
                m_adi = male_adi.get(male.id, 60.0)
                avg_adi = (f_adi + m_adi) / 2
                adi_score = 30.0 if avg_adi >= 70 else (20.0 if avg_adi >= 60 else 10.0)

                # 3. Weight compatibility (0-20)
                fw = female_weights.get(female.id, 0.0)
                mw = male_weights.get(male.id, 0.0)
                if fw > 0 and mw > 0:
                    ratio = mw / fw
                    if 1.1 <= ratio <= 1.5:
                        weight_score = 20.0
                    elif 1.5 < ratio <= 2.0:
                        weight_score = 12.0
                    elif 0.8 <= ratio < 1.1:
                        weight_score = 8.0
                    else:
                        weight_score = 5.0
                else:
                    weight_score = 10.0  # Ma'lumot yo'q — o'rta ball

                # 4. Breed compatibility (0-10)
                if female.breed and male.breed:
                    breed_score = 10.0 if female.breed == male.breed else 5.0
                elif not female.breed and not male.breed:
                    breed_score = 7.0
                else:
                    breed_score = 5.0

                total = gen_score + adi_score + weight_score + breed_score

                pairs.append((total, female, male, gen_score, adi_score, weight_score, breed_score))

        # Top N sort
        pairs.sort(key=lambda x: x[0], reverse=True)

        today = date.today()
        for item in pairs[:top_n]:
            total, female, male, gen_s, adi_s, weight_s, breed_s = item

            gestation = GESTATION_DAYS.get(female.species.value, 283)
            expected_center = today + timedelta(days=gestation)

            # Izoh generatsiya
            reasons = []
            warnings = []
            if gen_s >= 35:
                reasons.append("Yaqin qarindoshlik aniqlanmadi")
            if adi_s >= 25:
                reasons.append(f"ADI ko'rsatkichlari mos (o'rtacha {(female_adi.get(female.id,60)+male_adi.get(male.id,60))/2:.0f})")
            if weight_s >= 18:
                reasons.append("Vazn nisbati optimal (ota 10-50% og'irroq)")
            if breed_s == 10:
                reasons.append(f"Bir xil zot: {female.breed}")

            reason_text = ". ".join(reasons) if reasons else "Umumiy mos juft"

            f_brief = AnimalBrief(
                id=female.id, tag_id=female.tag_id,
                species=female.species.value, breed=female.breed,
                gender=female.gender.value, status=female.status.value,
            )
            m_brief = AnimalBrief(
                id=male.id, tag_id=male.tag_id,
                species=male.species.value, breed=male.breed,
                gender=male.gender.value, status=male.status.value,
            )

            recommendations.append(
                BreedingRecommendation(
                    mother=f_brief,
                    sire_animal=m_brief,
                    sire_external_label=None,
                    total_score=round(total, 1),
                    genetic_diversity_score=gen_s,
                    adi_compatibility_score=adi_s,
                    weight_compatibility_score=weight_s,
                    breed_compatibility_score=breed_s,
                    recommendation_reason=reason_text,
                    warnings=warnings,
                    estimated_gestation_days=gestation,
                    expected_birth_range_start=expected_center - timedelta(days=7),
                    expected_birth_range_end=expected_center + timedelta(days=7),
                )
            )

        from datetime import datetime as dt
        return BreedingRecommendationList(
            total_females_eligible=len(females),
            total_sires_available=len(males),
            recommendations=recommendations,
            generated_at=dt.utcnow(),
        )

    # =========================================================================
    # STATISTICS
    # =========================================================================

    async def get_stats(
        self, farm_id: Optional[int] = None
    ) -> BreedingStats:
        raw = await self.repo.get_stats(self.db, farm_id)
        return BreedingStats(**raw)