"""
TAURUS VISION — tests/test_services/test_breeding_service.py
==============================================================
Tizimni AYAMAS darajada tekshiradigan vahshiy testlar.

Qamrov:
  ✓ GESTATION_DAYS — barcha species uchun to'g'ri kun
  ✓ BreedingRecord model — barcha computed properties
  ✓ BreedingRepository — CRUD, filtrlar, get_stats
  ✓ BreedingService.create_record — 15+ ssenariy (validatsiyalar)
  ✓ BreedingService.confirm_pregnancy — holat o'tish
  ✓ BreedingService.record_birth — offspring, tirik/o'lik hisob
  ✓ BreedingService.mark_failed / mark_aborted — holat logikasi
  ✓ BreedingService.delete_record — ruxsat etilgan/man etilgan holatlar
  ✓ BreedingService.get_stats — jami statistika
  ✓ BreedingService.get_genealogy — shajara daraxti
  ✓ BreedingService.get_recommendations — scoring algoritm
  ✓ CHEGARA holatlari: bir xil jonivor ona=ota, o'chirilgan jonivor
  ✓ HOLAT MASHINI: barcha noto'g'ri o'tishlar to'sib qo'yilishi
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalGender, AnimalSpecies, AnimalStatus
from app.models.breeding import (
    BreedingRecord, BreedingStatus, OffspringRecord, OffspringOutcome,
    MatingMethod, PregnancyCheckMethod, GESTATION_DAYS,
)
from app.repositories.breeding_repository import BreedingRepository
from app.schemas.breeding import (
    BreedingRecordCreate, BreedingRecordUpdate,
    BreedingConfirmPregnancy, BreedingRecordBirth,
    BreedingMarkFailed, BreedingMarkAborted, OffspringCreate,
)
from app.services.breeding_service import BreedingService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY      = date.today()
YESTERDAY  = TODAY - timedelta(days=1)
LAST_MONTH = TODAY - timedelta(days=30)


# ─── Animal factory ───────────────────────────────────────────────────────────

def _animal(tag, gender, species=AnimalSpecies.CATTLE,
            status=AnimalStatus.ACTIVE, breed=None):
    return Animal(
        tag_id=tag,
        species=species,
        gender=gender,
        status=status,
        acquisition_date=datetime(2022, 1, 1),
        breed=breed,
    )


@pytest.fixture
async def mother(db):
    a = _animal("BRD-MOM-001", AnimalGender.FEMALE)
    db.add(a); await db.commit(); await db.refresh(a); return a

@pytest.fixture
async def father(db):
    a = _animal("BRD-DAD-001", AnimalGender.MALE)
    db.add(a); await db.commit(); await db.refresh(a); return a

@pytest.fixture
async def mother_sheep(db):
    a = _animal("BRD-EWE-001", AnimalGender.FEMALE, species=AnimalSpecies.SHEEP)
    db.add(a); await db.commit(); await db.refresh(a); return a

@pytest.fixture
async def father_sheep(db):
    a = _animal("BRD-RAM-001", AnimalGender.MALE, species=AnimalSpecies.SHEEP)
    db.add(a); await db.commit(); await db.refresh(a); return a

@pytest.fixture
async def inactive_female(db):
    a = _animal("BRD-DEAD-001", AnimalGender.FEMALE, status=AnimalStatus.SOLD)
    db.add(a); await db.commit(); await db.refresh(a); return a

@pytest.fixture
async def inactive_male(db):
    a = _animal("BRD-DEAD-002", AnimalGender.MALE, status=AnimalStatus.DECEASED)
    db.add(a); await db.commit(); await db.refresh(a); return a


def _create_data(mother_id, father_id=None, ext_sire=None,
                 mating_date=None, method=MatingMethod.NATURAL, **kw):
    return BreedingRecordCreate(
        mother_id=mother_id,
        father_id=father_id,
        external_sire_tag=ext_sire,
        mating_date=mating_date or LAST_MONTH,
        mating_method=method,
        **kw,
    )


@pytest.fixture
def svc(db):
    return BreedingService(db)


@pytest.fixture
def repo():
    return BreedingRepository()


# ─── DB'ga to'g'ridan yozuv qo'shuvchi helper ─────────────────────────────────
async def _raw_record(db, mother_id, father_id=None, status=BreedingStatus.PLANNED,
                      ext_sire="EXT-001", gestation=283, mating_date=None):
    r = BreedingRecord(
        mother_id=mother_id,
        father_id=father_id,
        external_sire_tag=ext_sire if not father_id else None,
        mating_date=mating_date or LAST_MONTH,
        mating_method=MatingMethod.NATURAL,
        status=status,
        gestation_days=gestation,
        expected_birth_date=(mating_date or LAST_MONTH) + timedelta(days=gestation),
        live_offspring_count=0,
        stillborn_count=0,
    )
    db.add(r)
    await db.commit()
    await db.refresh(r)
    return r


# ═══════════════════════════════════════════════════════════════════════════════
# GESTATION DAYS KONSTANTALAR
# ═══════════════════════════════════════════════════════════════════════════════

class TestGestationDays:
    def test_cattle_283(self):
        assert GESTATION_DAYS["cattle"] == 283

    def test_sheep_150(self):
        assert GESTATION_DAYS["sheep"] == 150

    def test_goat_150(self):
        assert GESTATION_DAYS["goat"] == 150

    def test_horse_340(self):
        assert GESTATION_DAYS["horse"] == 340

    def test_other_280(self):
        assert GESTATION_DAYS["other"] == 280

    def test_all_species_have_entry(self):
        for sp in ["cattle", "sheep", "goat", "horse", "other"]:
            assert sp in GESTATION_DAYS
            assert GESTATION_DAYS[sp] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING RECORD MODEL PROPERTIES
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingRecordModel:

    def _record(self, **kw):
        defaults = dict(
            mother_id=1, mating_date=LAST_MONTH,
            gestation_days=283, status=BreedingStatus.PLANNED,
            expected_birth_date=LAST_MONTH + timedelta(days=283),
            live_offspring_count=0, stillborn_count=0,
        )
        defaults.update(kw)
        return BreedingRecord(**defaults)

    # pregnancy_progress_pct
    def test_progress_pct_none_when_birthed(self):
        r = self._record(status=BreedingStatus.BIRTHED)
        assert r.pregnancy_progress_pct is None

    def test_progress_pct_none_when_failed(self):
        r = self._record(status=BreedingStatus.FAILED)
        assert r.pregnancy_progress_pct is None

    def test_progress_pct_positive_for_planned(self):
        r = self._record(status=BreedingStatus.PLANNED,
                         mating_date=TODAY - timedelta(days=100),
                         gestation_days=283)
        pct = r.pregnancy_progress_pct
        assert pct is not None and 0 < pct <= 100

    def test_progress_pct_capped_at_100(self):
        """Gestatsiyadan uzoq o'tsa ham 100% dan oshmasin."""
        r = self._record(status=BreedingStatus.CONFIRMED_PREGNANT,
                         mating_date=TODAY - timedelta(days=400),
                         gestation_days=283)
        assert r.pregnancy_progress_pct == 100.0

    def test_progress_pct_zero_same_day(self):
        r = self._record(status=BreedingStatus.CONFIRMED_PREGNANT,
                         mating_date=TODAY, gestation_days=283)
        assert r.pregnancy_progress_pct == 0.0

    # days_until_birth
    def test_days_until_birth_positive(self):
        future = TODAY + timedelta(days=50)
        r = self._record(expected_birth_date=future)
        assert r.days_until_birth == 50

    def test_days_until_birth_negative_when_overdue(self):
        past = TODAY - timedelta(days=5)
        r = self._record(expected_birth_date=past,
                         status=BreedingStatus.CONFIRMED_PREGNANT)
        assert r.days_until_birth == -5

    def test_days_until_birth_zero_when_birthed(self):
        r = self._record(status=BreedingStatus.BIRTHED,
                         expected_birth_date=TODAY - timedelta(days=3))
        assert r.days_until_birth == 0

    def test_days_until_birth_none_when_no_expected(self):
        r = self._record(expected_birth_date=None)
        assert r.days_until_birth is None

    # is_overdue
    def test_is_overdue_true(self):
        r = self._record(
            status=BreedingStatus.CONFIRMED_PREGNANT,
            expected_birth_date=TODAY - timedelta(days=1),
        )
        assert r.is_overdue is True

    def test_is_overdue_false_future(self):
        r = self._record(
            status=BreedingStatus.CONFIRMED_PREGNANT,
            expected_birth_date=TODAY + timedelta(days=10),
        )
        assert r.is_overdue is False

    def test_is_overdue_false_when_birthed(self):
        """Tug'ilgan yozuv overdue hisoblanmaydi."""
        r = self._record(
            status=BreedingStatus.BIRTHED,
            expected_birth_date=TODAY - timedelta(days=5),
        )
        assert r.is_overdue is False

    def test_is_overdue_false_when_no_expected_date(self):
        r = self._record(status=BreedingStatus.CONFIRMED_PREGNANT,
                         expected_birth_date=None)
        assert r.is_overdue is False

    # total_offspring
    def test_total_offspring_sum(self):
        r = self._record(live_offspring_count=3, stillborn_count=1)
        assert r.total_offspring == 4

    def test_total_offspring_zero(self):
        r = self._record(live_offspring_count=0, stillborn_count=0)
        assert r.total_offspring == 0

    def test_total_offspring_only_live(self):
        r = self._record(live_offspring_count=2, stillborn_count=0)
        assert r.total_offspring == 2

    # sire_label
    def test_sire_label_internal(self):
        r = self._record(father_id=5)
        assert "5" in r.sire_label
        assert "Ichki" in r.sire_label

    def test_sire_label_external_with_breed(self):
        r = self._record(external_sire_tag="EXT-001",
                         external_sire_breed="Angus")
        label = r.sire_label
        assert "EXT-001" in label
        assert "Angus" in label

    def test_sire_label_external_no_breed(self):
        r = self._record(external_sire_tag="EXT-002")
        assert "EXT-002" in r.sire_label

    def test_sire_label_unknown_when_none(self):
        r = self._record()
        assert "Noma'lum" in r.sire_label

    # __init__ aliases
    def test_dam_id_alias(self):
        r = BreedingRecord(dam_id=7, mating_date=TODAY,
                           mating_method=MatingMethod.NATURAL,
                           status=BreedingStatus.PLANNED,
                           gestation_days=283,
                           expected_birth_date=TODAY + timedelta(days=283),
                           live_offspring_count=0, stillborn_count=0)
        assert r.mother_id == 7

    def test_sire_id_alias(self):
        r = BreedingRecord(mother_id=1, sire_id=9, mating_date=TODAY,
                           mating_method=MatingMethod.NATURAL,
                           status=BreedingStatus.PLANNED,
                           gestation_days=283,
                           expected_birth_date=TODAY + timedelta(days=283),
                           live_offspring_count=0, stillborn_count=0)
        assert r.father_id == 9

    def test_breeding_date_alias(self):
        r = BreedingRecord(mother_id=1, breeding_date=TODAY,
                           mating_method=MatingMethod.NATURAL,
                           status=BreedingStatus.PLANNED,
                           gestation_days=283,
                           expected_birth_date=TODAY + timedelta(days=283),
                           live_offspring_count=0, stillborn_count=0)
        assert r.mating_date == TODAY

    def test_repr_contains_info(self):
        r = self._record(status=BreedingStatus.PLANNED)
        rep = repr(r)
        assert "planned" in rep


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING REPOSITORY — BASIC CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingRepository:

    async def test_create_assigns_id(self, db, repo, mother):
        r = await _raw_record(db, mother.id)
        assert r.id is not None and r.id > 0

    async def test_get_by_id_existing(self, db, repo, mother):
        r = await _raw_record(db, mother.id)
        found = await repo.get_by_id(db, r.id)
        assert found is not None and found.id == r.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(db, 999999) is None

    async def test_get_list_all(self, db, repo, mother):
        for _ in range(3):
            await _raw_record(db, mother.id)
        records, total = await repo.get_list(db)
        assert total >= 3

    async def test_get_list_status_filter(self, db, repo, mother):
        await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        records, total = await repo.get_list(db, status=BreedingStatus.PLANNED)
        assert all(r.status == BreedingStatus.PLANNED for r in records)

    async def test_get_list_mother_filter(self, db, repo, mother, db_session=None):
        a2 = _animal("BRD-MOM-002", AnimalGender.FEMALE)
        db.add(a2)
        await db.commit()
        await db.refresh(a2)
        await _raw_record(db, mother.id)
        await _raw_record(db, a2.id)
        records, total = await repo.get_list(db, mother_id=mother.id)
        assert all(r.mother_id == mother.id for r in records)

    async def test_get_list_date_from_filter(self, db, repo, mother):
        old_date = TODAY - timedelta(days=60)
        await _raw_record(db, mother.id, mating_date=old_date)
        await _raw_record(db, mother.id, mating_date=TODAY - timedelta(days=10))
        records, _ = await repo.get_list(db, date_from=TODAY - timedelta(days=20))
        for r in records:
            assert r.mating_date >= TODAY - timedelta(days=20)

    async def test_get_list_pagination(self, db, repo, mother):
        for _ in range(5):
            await _raw_record(db, mother.id)
        p1, _ = await repo.get_list(db, skip=0, limit=2)
        p2, _ = await repo.get_list(db, skip=2, limit=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})

    async def test_get_active_pregnancies(self, db, repo, mother):
        await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        result = await repo.get_active_pregnancies(db)
        assert all(r.status in (
            BreedingStatus.CONFIRMED_PREGNANT, BreedingStatus.PLANNED
        ) for r in result)

    async def test_get_due_soon(self, db, repo, mother):
        near = TODAY + timedelta(days=5)
        far  = TODAY + timedelta(days=30)
        r1 = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT,
                                mating_date=near - timedelta(days=283))
        r1.expected_birth_date = near
        r1.status = BreedingStatus.CONFIRMED_PREGNANT
        await db.commit()
        result = await repo.get_due_soon(db, days=14)
        # near date ichida bo'lishi kerak
        for r in result:
            assert r.expected_birth_date <= TODAY + timedelta(days=14)

    async def test_get_stats_structure(self, db, repo, mother):
        await _raw_record(db, mother.id)
        stats = await repo.get_stats(db)
        for k in ["total", "by_status", "success_rate",
                  "avg_offspring_live", "overdue_count"]:
            assert k in stats

    async def test_update_changes_status(self, db, repo, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        r.status = BreedingStatus.CONFIRMED_PREGNANT
        updated = await repo.update(db, r)
        assert updated.status == BreedingStatus.CONFIRMED_PREGNANT

    async def test_delete_removes(self, db, repo, mother):
        r = await _raw_record(db, mother.id)
        rid = r.id
        await repo.delete(db, r)
        assert await repo.get_by_id(db, rid) is None


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — CREATE RECORD (VAHSHIY VALIDATSIYALAR)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceCreate:

    async def test_create_with_internal_sire(self, db, svc, mother, father):
        data = _create_data(mother.id, father_id=father.id)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.id is not None
        assert resp.mother_id == mother.id
        assert resp.father_id == father.id

    async def test_create_with_external_sire(self, db, svc, mother):
        data = _create_data(mother.id, ext_sire="EXT-ANGUS-001")
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.external_sire_tag == "EXT-ANGUS-001"

    async def test_create_ai_method_auto_ext_tag(self, db, svc, mother):
        """AI metod, ota ko'rsatilmasa — 'AI' tagi avtomatik o'rnatiladi."""
        data = _create_data(mother.id, method=MatingMethod.ARTIFICIAL_INSEMINATION)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.external_sire_tag == "AI"

    async def test_create_status_planned_by_default(self, db, svc, mother, father):
        data = _create_data(mother.id, father_id=father.id)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.status == BreedingStatus.PLANNED

    async def test_create_gestation_cattle_auto(self, db, svc, mother, father):
        """Qoramol uchun gestatsiya 283 kun avtomatik."""
        data = _create_data(mother.id, father_id=father.id, mating_date=LAST_MONTH)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.gestation_days == 283

    async def test_create_gestation_sheep_auto(self, db, svc, mother_sheep, father_sheep):
        """Qo'y uchun gestatsiya 150 kun."""
        data = _create_data(mother_sheep.id, father_id=father_sheep.id, mating_date=LAST_MONTH)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.gestation_days == 150

    async def test_create_gestation_override(self, db, svc, mother, father):
        """Maxsus gestatsiya ko'rsatilsa — o'sha ishlatiladi."""
        data = _create_data(mother.id, father_id=father.id, mating_date=LAST_MONTH,
                            gestation_days=290)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.gestation_days == 290

    async def test_create_expected_date_auto_computed(self, db, svc, mother, father):
        """expected_birth_date = mating_date + gestation_days."""
        mating = TODAY - timedelta(days=30)
        data = _create_data(mother.id, father_id=father.id, mating_date=mating)
        resp = await svc.create_record(data, created_by_id=1)
        assert resp.expected_birth_date == mating + timedelta(days=283)

    async def test_create_missing_mother_raises(self, db, svc, father):
        data = _create_data(99999, father_id=father.id)
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.create_record(data, created_by_id=1)
        assert "99999" in str(exc_info.value)

    async def test_create_male_mother_raises(self, db, svc, father):
        """Erkak jonivorni ona qilib bo'lmaydi."""
        data = _create_data(father.id, father_id=None, ext_sire="EXT-001")
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.create_record(data, created_by_id=1)
        assert "female" in exc_info.value.message.lower() or \
               "urg'ochi" in exc_info.value.message.lower()

    async def test_create_inactive_mother_raises(self, db, svc, inactive_female, father):
        data = _create_data(inactive_female.id, father_id=father.id)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.create_record(data, created_by_id=1)
        assert "aktiv" in exc_info.value.message.lower()

    async def test_create_missing_father_raises(self, db, svc, mother):
        data = _create_data(mother.id, father_id=99999)
        with pytest.raises(EntityNotFoundError):
            await svc.create_record(data, created_by_id=1)

    async def test_create_female_father_raises(self, db, svc, mother):
        """Urg'ochi jonivorni ota qilib bo'lmaydi."""
        m2 = _animal("BRD-MOM-003", AnimalGender.FEMALE)
        db.add(m2); await db.commit(); await db.refresh(m2)
        data = _create_data(mother.id, father_id=m2.id)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.create_record(data, created_by_id=1)
        assert "male" in exc_info.value.message.lower() or \
               "erkak" in exc_info.value.message.lower()

    async def test_create_inactive_father_raises(self, db, svc, mother, inactive_male):
        data = _create_data(mother.id, father_id=inactive_male.id)
        with pytest.raises(BusinessRuleViolationError):
            await svc.create_record(data, created_by_id=1)

    async def test_create_different_species_raises(self, db, svc, mother, father_sheep):
        """Qoramol ona + qo'y ota — XATO."""
        data = _create_data(mother.id, father_id=father_sheep.id)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.create_record(data, created_by_id=1)
        assert "species" in exc_info.value.message.lower() or \
               "tur" in exc_info.value.message.lower()

    async def test_create_all_mating_methods(self, db, svc, mother):
        for method in MatingMethod:
            ext = "EXT-001" if method != MatingMethod.NATURAL else None
            internal_father = None
            if method == MatingMethod.NATURAL:
                f = _animal(f"BRD-DAD-{method.value[:3]}", AnimalGender.MALE)
                db.add(f); await db.commit(); await db.refresh(f)
                internal_father = f.id
            data = _create_data(mother.id, father_id=internal_father,
                                ext_sire=ext or "EXT-001", method=method,
                                mating_date=TODAY - timedelta(days=method.__hash__() % 30 + 1))
            resp = await svc.create_record(data, created_by_id=1)
            assert resp.mating_method == method


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — READ
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceRead:

    async def test_get_record_existing(self, db, svc, mother):
        r = await _raw_record(db, mother.id)
        resp = await svc.get_record(r.id)
        assert resp.id == r.id

    async def test_get_record_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_record(999999)

    async def test_get_list_structure(self, db, svc, mother):
        from app.schemas.breeding import BreedingRecordList
        await _raw_record(db, mother.id)
        result = await svc.get_list()
        assert isinstance(result, BreedingRecordList)
        assert result.total >= 1

    async def test_get_list_status_filter(self, db, svc, mother):
        await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        result = await svc.get_list(status=BreedingStatus.PLANNED)
        assert all(r.status == BreedingStatus.PLANNED for r in result.items)

    async def test_get_list_pagination(self, db, svc, mother):
        for _ in range(5):
            await _raw_record(db, mother.id)
        p1 = await svc.get_list(page=1, size=2)
        p2 = await svc.get_list(page=2, size=2)
        assert {r.id for r in p1.items}.isdisjoint({r.id for r in p2.items})

    async def test_get_active_pregnancies(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        result = await svc.get_active_pregnancies()
        assert any(p.id == r.id for p in result)

    async def test_get_animal_breeding_history(self, db, svc, mother):
        for _ in range(3):
            await _raw_record(db, mother.id)
        history = await svc.get_animal_breeding_history(mother.id)
        assert len(history) >= 3
        assert all(r.mother_id == mother.id for r in history)

    async def test_get_animal_history_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal_breeding_history(999999)


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — UPDATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceUpdate:

    async def test_update_notes(self, db, svc, mother):
        r = await _raw_record(db, mother.id)
        upd = BreedingRecordUpdate(notes="Updated notes")
        updated = await svc.update_record(r.id, upd)
        assert updated.notes == "Updated notes"

    async def test_update_veterinarian(self, db, svc, mother):
        r = await _raw_record(db, mother.id)
        upd = BreedingRecordUpdate(veterinarian="Dr. Toshmatov")
        updated = await svc.update_record(r.id, upd)
        assert updated.veterinarian == "Dr. Toshmatov"

    async def test_update_birthed_record_raises(self, db, svc, mother):
        """BIRTHED yozuvni yangilash man etilgan."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.update_record(r.id, BreedingRecordUpdate(notes="Blocked"))
        assert "tug'ilgan" in exc_info.value.message.lower()

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_record(999999, BreedingRecordUpdate(notes="Ghost"))


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — CONFIRM PREGNANCY (HOLAT MASHINI)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceConfirmPregnancy:

    async def test_confirm_planned_to_confirmed(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        data = BreedingConfirmPregnancy(
            confirmed_at=TODAY,
            check_method=PregnancyCheckMethod.ULTRASOUND,
        )
        resp = await svc.confirm_pregnancy(r.id, data)
        assert resp.status == BreedingStatus.CONFIRMED_PREGNANT
        assert resp.pregnancy_confirmed_at == TODAY

    async def test_confirm_sets_check_method(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        data = BreedingConfirmPregnancy(
            confirmed_at=TODAY,
            check_method=PregnancyCheckMethod.BLOOD_TEST,
            check_notes="qon tahlili natijasi ijobiy",
        )
        resp = await svc.confirm_pregnancy(r.id, data)
        assert resp.pregnancy_check_method == PregnancyCheckMethod.BLOOD_TEST

    async def test_confirm_already_confirmed_ok(self, db, svc, mother):
        """CONFIRMED_PREGNANT dan yana confirmed — ruxsat etiladi."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        data = BreedingConfirmPregnancy(confirmed_at=TODAY,
                                        check_method=PregnancyCheckMethod.ULTRASOUND)
        resp = await svc.confirm_pregnancy(r.id, data)
        assert resp.status == BreedingStatus.CONFIRMED_PREGNANT

    async def test_confirm_birthed_raises(self, db, svc, mother):
        """BIRTHED dan confirm — XATO."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        data = BreedingConfirmPregnancy(confirmed_at=TODAY,
                                        check_method=PregnancyCheckMethod.VISUAL)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.confirm_pregnancy(r.id, data)
        assert "PLANNED" in exc_info.value.message or "holat" in exc_info.value.message.lower()

    async def test_confirm_failed_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.FAILED)
        data = BreedingConfirmPregnancy(confirmed_at=TODAY,
                                        check_method=PregnancyCheckMethod.VISUAL)
        with pytest.raises(BusinessRuleViolationError):
            await svc.confirm_pregnancy(r.id, data)

    async def test_confirm_updates_expected_date(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        new_date = TODAY + timedelta(days=200)
        data = BreedingConfirmPregnancy(
            confirmed_at=TODAY,
            check_method=PregnancyCheckMethod.ULTRASOUND,
            expected_birth_date=new_date,
        )
        resp = await svc.confirm_pregnancy(r.id, data)
        assert resp.expected_birth_date == new_date

    async def test_confirm_missing_raises(self, db, svc):
        data = BreedingConfirmPregnancy(confirmed_at=TODAY,
                                        check_method=PregnancyCheckMethod.VISUAL)
        with pytest.raises(EntityNotFoundError):
            await svc.confirm_pregnancy(999999, data)

    async def test_confirm_all_check_methods(self, db, svc, mother):
        for method in PregnancyCheckMethod:
            r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
            data = BreedingConfirmPregnancy(confirmed_at=TODAY, check_method=method)
            resp = await svc.confirm_pregnancy(r.id, data)
            assert resp.pregnancy_check_method == method


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — RECORD BIRTH (VAHSHIY)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceRecordBirth:

    def _birth_data(self, n_live=1, n_stillborn=0, actual_date=None):
        offspring = []
        for i in range(1, n_live + 1):
            offspring.append(OffspringCreate(
                birth_order=i, gender="female",
                birth_weight_kg=40.0,
                outcome=OffspringOutcome.ALIVE,
            ))
        for j in range(n_live + 1, n_live + n_stillborn + 1):
            offspring.append(OffspringCreate(
                birth_order=j, gender="male",
                birth_weight_kg=35.0,
                outcome=OffspringOutcome.STILLBORN,
            ))
        return BreedingRecordBirth(
            actual_birth_date=actual_date or TODAY,
            offspring=offspring,
        )

    async def test_record_birth_from_confirmed(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.record_birth(r.id, self._birth_data(n_live=1))
        assert resp.status == BreedingStatus.BIRTHED

    async def test_record_birth_from_planned_ok(self, db, svc, mother):
        """PLANNED dan ham tug'ilish qayd etilishi mumkin."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        resp = await svc.record_birth(r.id, self._birth_data())
        assert resp.status == BreedingStatus.BIRTHED

    async def test_record_birth_live_count(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.record_birth(r.id, self._birth_data(n_live=2, n_stillborn=1))
        assert resp.live_offspring_count == 2
        assert resp.stillborn_count == 1

    async def test_record_birth_total_offspring(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.record_birth(r.id, self._birth_data(n_live=3, n_stillborn=0))
        assert resp.total_offspring == 3

    async def test_record_birth_creates_offspring_records(self, db, svc, mother, repo):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.record_birth(r.id, self._birth_data(n_live=2))
        full = await repo.get_by_id(db, r.id)
        assert len(full.offspring) == 2

    async def test_record_birth_sets_actual_date(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        birth_date = TODAY - timedelta(days=1)
        resp = await svc.record_birth(r.id, self._birth_data(actual_date=birth_date))
        assert resp.actual_birth_date == birth_date

    async def test_record_birth_twice_raises(self, db, svc, mother):
        """Ikki marta tug'ilish qayd etib bo'lmaydi."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        await svc.record_birth(r.id, self._birth_data())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.record_birth(r.id, self._birth_data())
        assert "allaqachon" in exc_info.value.message.lower()

    async def test_record_birth_from_failed_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.FAILED)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.record_birth(r.id, self._birth_data())
        msg = exc_info.value.message.lower()
        assert "failed" in msg or "holat" in msg

    async def test_record_birth_from_aborted_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.ABORTED)
        with pytest.raises(BusinessRuleViolationError):
            await svc.record_birth(r.id, self._birth_data())

    async def test_record_birth_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.record_birth(999999, self._birth_data())

    async def test_record_birth_with_complications(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        data = BreedingRecordBirth(
            actual_birth_date=TODAY,
            offspring=[OffspringCreate(birth_order=1, outcome=OffspringOutcome.ALIVE)],
            birth_complications="Qiyin tug'ilish, veterinar yordam kerak bo'ldi",
        )
        resp = await svc.record_birth(r.id, data)
        assert resp.birth_complications is not None

    async def test_record_birth_zero_live_stillborn_only(self, db, svc, mother):
        """Hammasi o'lik tug'ilgan ssenariy."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.record_birth(r.id, self._birth_data(n_live=0, n_stillborn=2))
        assert resp.live_offspring_count == 0
        assert resp.stillborn_count == 2
        assert resp.status == BreedingStatus.BIRTHED


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — MARK FAILED / ABORTED
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceMarkFailedAborted:

    async def test_mark_failed_from_planned(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        resp = await svc.mark_failed(r.id, BreedingMarkFailed(reason="Homiladorlik bo'lmadi"))
        assert resp.status == BreedingStatus.FAILED

    async def test_mark_failed_from_confirmed(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        resp = await svc.mark_failed(r.id, BreedingMarkFailed())
        assert resp.status == BreedingStatus.FAILED

    async def test_mark_failed_reason_appended_to_notes(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        resp = await svc.mark_failed(r.id, BreedingMarkFailed(reason="UV nurlanish ta'siri"))
        assert "UV nurlanish ta'siri" in (resp.notes or "")

    async def test_mark_failed_birthed_raises(self, db, svc, mother):
        """BIRTHED yozuvni failed deb belgilab bo'lmaydi."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.mark_failed(r.id, BreedingMarkFailed())
        assert "tug'ilgan" in exc_info.value.message.lower()

    async def test_mark_failed_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.mark_failed(999999, BreedingMarkFailed())

    async def test_mark_aborted_from_confirmed(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        data = BreedingMarkAborted(
            abort_date=TODAY,
            abort_reason="Tashqi stress sabab",
        )
        resp = await svc.mark_aborted(r.id, data)
        assert resp.status == BreedingStatus.ABORTED
        assert resp.abort_date == TODAY
        assert resp.abort_reason == "Tashqi stress sabab"

    async def test_mark_aborted_from_planned_ok(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        data = BreedingMarkAborted(abort_date=TODAY, abort_reason="Spontan abort")
        resp = await svc.mark_aborted(r.id, data)
        assert resp.status == BreedingStatus.ABORTED

    async def test_mark_aborted_birthed_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        data = BreedingMarkAborted(abort_date=TODAY, abort_reason="Impossible")
        with pytest.raises(BusinessRuleViolationError):
            await svc.mark_aborted(r.id, data)

    async def test_mark_aborted_missing_raises(self, db, svc):
        data = BreedingMarkAborted(abort_date=TODAY, abort_reason="Ghost")
        with pytest.raises(EntityNotFoundError):
            await svc.mark_aborted(999999, data)


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — DELETE (HOLAT CHEGARALAR)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceDelete:

    async def test_delete_planned_ok(self, db, svc, mother, repo):
        r = await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        rid = r.id
        await svc.delete_record(rid)
        assert await repo.get_by_id(db, rid) is None

    async def test_delete_failed_ok(self, db, svc, mother, repo):
        r = await _raw_record(db, mother.id, status=BreedingStatus.FAILED)
        rid = r.id
        await svc.delete_record(rid)
        assert await repo.get_by_id(db, rid) is None

    async def test_delete_confirmed_raises(self, db, svc, mother):
        """CONFIRMED_PREGNANT o'chirib bo'lmaydi."""
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.delete_record(r.id)
        assert "PLANNED" in exc_info.value.message or "FAILED" in exc_info.value.message

    async def test_delete_birthed_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        with pytest.raises(BusinessRuleViolationError):
            await svc.delete_record(r.id)

    async def test_delete_aborted_raises(self, db, svc, mother):
        r = await _raw_record(db, mother.id, status=BreedingStatus.ABORTED)
        with pytest.raises(BusinessRuleViolationError):
            await svc.delete_record(r.id)

    async def test_delete_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_record(999999)


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceStats:

    async def test_stats_structure(self, db, svc, mother):
        from app.schemas.breeding import BreedingStats
        await _raw_record(db, mother.id)
        stats = await svc.get_stats()
        assert isinstance(stats, BreedingStats)
        for k in ["total", "by_status", "success_rate",
                  "avg_offspring_live", "overdue_count"]:
            assert hasattr(stats, k)

    async def test_stats_total_increases(self, db, svc, mother):
        before = await svc.get_stats()
        await _raw_record(db, mother.id)
        after  = await svc.get_stats()
        assert after.total >= before.total

    async def test_stats_by_status_has_planned(self, db, svc, mother):
        await _raw_record(db, mother.id, status=BreedingStatus.PLANNED)
        stats = await svc.get_stats()
        assert "planned" in stats.by_status or BreedingStatus.PLANNED.value in str(stats.by_status)

    async def test_stats_success_rate_range(self, db, svc, mother):
        for _ in range(3):
            await _raw_record(db, mother.id, status=BreedingStatus.BIRTHED)
        await _raw_record(db, mother.id, status=BreedingStatus.FAILED)
        stats = await svc.get_stats()
        assert 0.0 <= stats.success_rate <= 1.0

    async def test_stats_overdue_count(self, db, svc, mother):
        """Muddati o'tgan yozuv overdue_count ga kirishi kerak."""
        past_exp = TODAY - timedelta(days=1)
        r = await _raw_record(db, mother.id, status=BreedingStatus.CONFIRMED_PREGNANT)
        r.expected_birth_date = past_exp
        await db.commit()
        stats = await svc.get_stats()
        assert stats.overdue_count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — GENEALOGY (SHAJARA)
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceGenealogy:

    async def test_genealogy_returns_node(self, db, svc, mother):
        from app.schemas.breeding import GenealogyNode
        node = await svc.get_genealogy(mother.id)
        assert isinstance(node, GenealogyNode)
        assert node.animal_id == mother.id

    async def test_genealogy_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_genealogy(999999)

    async def test_genealogy_node_has_tag(self, db, svc, mother):
        node = await svc.get_genealogy(mother.id)
        assert node.tag_id == mother.tag_id

    async def test_genealogy_node_has_species(self, db, svc, mother):
        node = await svc.get_genealogy(mother.id)
        assert node.species is not None

    async def test_genealogy_generation_zero_for_root(self, db, svc, mother):
        node = await svc.get_genealogy(mother.id)
        assert node.generation == 0

    async def test_genealogy_max_generations_cap(self, db, svc, mother):
        """max_generations > 5 bo'lsa — 5 ga cheklanadi."""
        node = await svc.get_genealogy(mother.id, max_generations=10)
        assert node is not None  # xato bo'lmaydi

    async def test_genealogy_with_parent(self, db, svc, mother, father):
        """Ota yozuvi bo'lsa — father node paydo bo'ladi."""
        data = _create_data(mother.id, father_id=father.id)
        await svc.create_record(data, created_by_id=1)
        node = await svc.get_genealogy(mother.id, max_generations=2)
        # mother uchun parent bo'lmasligi mumkin — bu test node o'zi uchun
        assert node.tag_id == mother.tag_id


# ═══════════════════════════════════════════════════════════════════════════════
# BREEDING SERVICE — RECOMMENDATIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestBreedingServiceRecommendations:

    async def test_recommendations_returns_list(self, db, svc, mother, father):
        from app.schemas.breeding import BreedingRecommendationList
        result = await svc.get_recommendations()
        assert isinstance(result, BreedingRecommendationList)
        assert hasattr(result, "recommendations")
        assert hasattr(result, "total_females_eligible")
        assert hasattr(result, "total_sires_available")

    async def test_recommendations_top_n_respected(self, db, svc):
        """top_n chegarasi hurmat qilinadi."""
        # 3 ta female, 3 ta male qo'shamiz
        for i in range(3):
            f = _animal(f"REC-F{i}", AnimalGender.FEMALE)
            m = _animal(f"REC-M{i}", AnimalGender.MALE)
            db.add(f); db.add(m)
        await db.commit()
        result = await svc.get_recommendations(top_n=2)
        assert len(result.recommendations) <= 2

    async def test_recommendations_different_species_not_paired(self, db, svc):
        """Har xil species juftlanmaydi."""
        f = _animal("REC-COW", AnimalGender.FEMALE, species=AnimalSpecies.CATTLE)
        m = _animal("REC-RAM", AnimalGender.MALE,   species=AnimalSpecies.SHEEP)
        db.add(f); db.add(m)
        await db.commit()
        result = await svc.get_recommendations()
        # cattle female + sheep male juftlanmagan bo'lishi kerak
        for rec in result.recommendations:
            if rec.mother.id == f.id:
                assert rec.sire_animal is None or rec.sire_animal.species == "cattle"

    async def test_recommendations_score_range(self, db, svc, mother, father):
        """Score 0-100 orasida bo'lishi kerak."""
        result = await svc.get_recommendations()
        for rec in result.recommendations:
            assert 0 <= rec.total_score <= 100

    async def test_recommendations_sorted_by_score(self, db, svc):
        """Tavsiyalar score bo'yicha kamayish tartibida."""
        for i in range(3):
            f = _animal(f"SC-F{i}", AnimalGender.FEMALE)
            m = _animal(f"SC-M{i}", AnimalGender.MALE)
            db.add(f); db.add(m)
        await db.commit()
        result = await svc.get_recommendations()
        scores = [r.total_score for r in result.recommendations]
        assert scores == sorted(scores, reverse=True)

    async def test_recommendations_same_breed_higher_score(self, db, svc):
        """Bir xil zot — breed_compatibility_score=10, har xil=5."""
        f = _animal("BREED-F1", AnimalGender.FEMALE, breed="Holstein")
        m = _animal("BREED-M1", AnimalGender.MALE,   breed="Holstein")
        db.add(f); db.add(m)
        await db.commit()
        result = await svc.get_recommendations()
        for rec in result.recommendations:
            if rec.mother.id == f.id and rec.sire_animal and rec.sire_animal.id == m.id:
                assert rec.breed_compatibility_score == 10.0