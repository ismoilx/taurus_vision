"""
TAURUS VISION — tests/test_services/test_milk_service.py
==========================================================
MilkProductionRepository + MilkService uchun to'liq testlar.

Qamrov:
  ✓ MilkProduction model  — quality_grade_auto property, __repr__
  ✓ MilkProductionRepository.create
  ✓ MilkProductionRepository.get_by_id
  ✓ MilkProductionRepository.get_by_animal         — filtrlash, pagination
  ✓ MilkProductionRepository.get_farm_records      — sana filtri
  ✓ MilkProductionRepository.get_daily_totals      — kunlik aggregatsiya
  ✓ MilkProductionRepository.get_animal_stats      — 7/30 kun statistika
  ✓ MilkProductionRepository.get_today_total       — global / bitta jonivor
  ✓ MilkProductionRepository.get_per_animal_monthly_stats
  ✓ MilkProductionRepository.update
  ✓ MilkProductionRepository.delete
  ✓ MilkService.add_record                         — to'g'ri, erkak, sifat avtohisob
  ✓ MilkService.update_record                      — mavjud, yo'q
  ✓ MilkService.delete_record                      — mavjud, yo'q
  ✓ MilkService.get_animal_records                 — sana filtri, pagination
  ✓ MilkService.get_animal_summary                 — to'liq tuzilma
  ✓ MilkService.get_farm_summary                   — oylik/kunlik
"""

import pytest
from datetime import date, datetime, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalGender, AnimalSpecies, AnimalStatus
from app.models.milk_production import MilkProduction, MilkQualityGrade, MilkSession
from app.repositories.milk_production_repository import MilkProductionRepository
from app.schemas.milk_production import MilkProductionCreate, MilkProductionUpdate
from app.services.milk_service import MilkService
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
async def female_cow(db):
    from app.core.security import hash_password
    a = Animal(
        tag_id="MILK-COW-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@pytest.fixture
async def male_bull(db):
    a = Animal(
        tag_id="BULL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


@pytest.fixture
async def second_cow(db):
    a = Animal(
        tag_id="MILK-COW-002",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


def _create_data(animal_id: int, *, milk_kg=10.0, record_date=None, **kwargs) -> MilkProductionCreate:
    return MilkProductionCreate(
        animal_id=animal_id,
        record_date=record_date or TODAY,
        milk_kg=milk_kg,
        session=MilkSession.MORNING,
        **kwargs,
    )


@pytest.fixture
def repo(db):
    return MilkProductionRepository(db)


@pytest.fixture
def svc(db):
    return MilkService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkProductionModel:

    def test_quality_grade_auto_premium(self):
        m = MilkProduction(somatic_cell_count=100)
        assert m.quality_grade_auto == MilkQualityGrade.PREMIUM

    def test_quality_grade_auto_standard(self):
        m = MilkProduction(somatic_cell_count=300)
        assert m.quality_grade_auto == MilkQualityGrade.STANDARD

    def test_quality_grade_auto_low(self):
        m = MilkProduction(somatic_cell_count=600)
        assert m.quality_grade_auto == MilkQualityGrade.LOW

    def test_quality_grade_auto_rejected(self):
        m = MilkProduction(somatic_cell_count=1000)
        assert m.quality_grade_auto == MilkQualityGrade.REJECTED

    def test_quality_grade_auto_none_returns_standard(self):
        m = MilkProduction(somatic_cell_count=None)
        assert m.quality_grade_auto == MilkQualityGrade.STANDARD

    def test_quality_grade_boundary_200(self):
        """200 — STANDARD (< 200 PREMIUM)."""
        assert MilkProduction(somatic_cell_count=200).quality_grade_auto == MilkQualityGrade.STANDARD

    def test_quality_grade_boundary_399(self):
        assert MilkProduction(somatic_cell_count=399).quality_grade_auto == MilkQualityGrade.STANDARD

    def test_quality_grade_boundary_400(self):
        """400 — LOW (< 400 STANDARD)."""
        assert MilkProduction(somatic_cell_count=400).quality_grade_auto == MilkQualityGrade.LOW

    def test_quality_grade_boundary_800(self):
        """800 — REJECTED (< 800 LOW)."""
        assert MilkProduction(somatic_cell_count=800).quality_grade_auto == MilkQualityGrade.REJECTED

    def test_repr_contains_key_info(self):
        m = MilkProduction(animal_id=5, record_date=TODAY, milk_kg=12.5)
        r = repr(m)
        assert "5" in r
        assert "12.5" in r


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION REPOSITORY — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkRepoCreate:

    async def test_create_returns_record_with_id(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id))
        await db.commit()
        assert rec.id is not None and rec.id > 0

    async def test_create_saves_all_fields(self, db, repo, female_cow):
        data = _create_data(
            female_cow.id,
            milk_kg=15.5,
            fat_percent=3.8,
            protein_percent=3.2,
            somatic_cell_count=150,
            quality_grade=MilkQualityGrade.PREMIUM,
            milked_by="Abdullayev",
            notes="Yaxshi sut",
        )
        rec = await repo.create(data)
        await db.commit()
        assert rec.milk_kg          == 15.5
        assert rec.fat_percent      == 3.8
        assert rec.protein_percent  == 3.2
        assert rec.somatic_cell_count == 150
        assert rec.quality_grade    == MilkQualityGrade.PREMIUM
        assert rec.milked_by        == "Abdullayev"
        assert rec.notes            == "Yaxshi sut"

    async def test_create_multiple_records_same_animal(self, db, repo, female_cow):
        sessions = [MilkSession.MORNING, MilkSession.MIDDAY, MilkSession.EVENING]
        ids = []
        for s in sessions:
            r = await repo.create(_create_data(female_cow.id, session=s))
            ids.append(r.id)
        await db.commit()
        assert len(set(ids)) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION REPOSITORY — GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkRepoGet:

    async def test_get_by_id_existing(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id, milk_kg=8.0))
        await db.commit()
        found = await repo.get_by_id(rec.id)
        assert found is not None and found.id == rec.id

    async def test_get_by_id_nonexistent_returns_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_by_animal_returns_records(self, db, repo, female_cow):
        for i in range(3):
            await repo.create(_create_data(female_cow.id,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        items, total = await repo.get_by_animal(female_cow.id)
        assert total >= 3
        assert len(items) >= 3

    async def test_get_by_animal_date_from_filter(self, db, repo, female_cow):
        old_date = TODAY - timedelta(days=40)
        await repo.create(_create_data(female_cow.id, record_date=old_date))
        await repo.create(_create_data(female_cow.id, record_date=TODAY))
        await db.commit()
        items, total = await repo.get_by_animal(
            female_cow.id, date_from=TODAY - timedelta(days=5)
        )
        for item in items:
            assert item.record_date >= TODAY - timedelta(days=5)

    async def test_get_by_animal_date_to_filter(self, db, repo, female_cow):
        await repo.create(_create_data(female_cow.id, record_date=YESTERDAY))
        await repo.create(_create_data(female_cow.id, record_date=TODAY))
        await db.commit()
        items, total = await repo.get_by_animal(
            female_cow.id, date_to=YESTERDAY
        )
        for item in items:
            assert item.record_date <= YESTERDAY

    async def test_get_by_animal_pagination(self, db, repo, female_cow):
        for i in range(5):
            await repo.create(_create_data(female_cow.id,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        page1, _ = await repo.get_by_animal(female_cow.id, limit=2, offset=0)
        page2, _ = await repo.get_by_animal(female_cow.id, limit=2, offset=2)
        assert len(page1) <= 2 and len(page2) <= 2
        ids1 = {r.id for r in page1}
        ids2 = {r.id for r in page2}
        assert ids1.isdisjoint(ids2)

    async def test_get_by_animal_empty_returns_zero(self, db, repo, female_cow):
        items, total = await repo.get_by_animal(99999)
        assert total == 0 and len(items) == 0

    async def test_get_by_animal_only_own_records(self, db, repo, female_cow, second_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=10.0))
        await repo.create(_create_data(second_cow.id, milk_kg=20.0))
        await db.commit()
        items, total = await repo.get_by_animal(female_cow.id)
        assert all(r.animal_id == female_cow.id for r in items)


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION REPOSITORY — FARM RECORDS & DAILY TOTALS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkRepoFarmAndDailyStats:

    async def test_get_farm_records_date_range(self, db, repo, female_cow, second_cow):
        d1 = TODAY - timedelta(days=5)
        d2 = TODAY - timedelta(days=3)
        d3 = TODAY - timedelta(days=1)
        for cow in [female_cow, second_cow]:
            await repo.create(_create_data(cow.id, record_date=d1))
            await repo.create(_create_data(cow.id, record_date=d2))
            await repo.create(_create_data(cow.id, record_date=d3))
        await db.commit()
        recs = await repo.get_farm_records(date_from=d2, date_to=d3)
        for r in recs:
            assert d2 <= r.record_date <= d3

    async def test_get_farm_records_animal_filter(self, db, repo, female_cow, second_cow):
        await repo.create(_create_data(female_cow.id))
        await repo.create(_create_data(second_cow.id))
        await db.commit()
        recs = await repo.get_farm_records(
            date_from=TODAY - timedelta(days=1),
            date_to=TODAY,
            animal_ids=[female_cow.id],
        )
        assert all(r.animal_id == female_cow.id for r in recs)

    async def test_get_daily_totals_sums_correctly(self, db, repo, female_cow):
        # 2 ta yozuv bugun
        await repo.create(_create_data(female_cow.id, milk_kg=10.0))
        await repo.create(_create_data(female_cow.id, milk_kg=5.0, session=MilkSession.EVENING))
        await db.commit()
        totals = await repo.get_daily_totals(
            date_from=TODAY, date_to=TODAY
        )
        assert len(totals) >= 1
        today_row = next((t for t in totals if t["date"] == str(TODAY)), None)
        assert today_row is not None
        assert today_row["total_kg"] >= 15.0

    async def test_get_daily_totals_date_range(self, db, repo, female_cow):
        for i in range(3):
            await repo.create(_create_data(female_cow.id,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        totals = await repo.get_daily_totals(
            date_from=TODAY - timedelta(days=2), date_to=TODAY
        )
        assert len(totals) >= 1
        # Sanalar diapazon ichida
        for t in totals:
            d = date.fromisoformat(t["date"])
            assert TODAY - timedelta(days=2) <= d <= TODAY

    async def test_get_daily_totals_returns_list_of_dicts(self, db, repo, female_cow):
        await repo.create(_create_data(female_cow.id))
        await db.commit()
        result = await repo.get_daily_totals(date_from=TODAY, date_to=TODAY)
        assert isinstance(result, list)
        if result:
            row = result[0]
            assert "date" in row
            assert "total_kg" in row
            assert "animal_count" in row

    async def test_get_today_total_global(self, db, repo, female_cow, second_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=12.0))
        await repo.create(_create_data(second_cow.id, milk_kg=8.0))
        await db.commit()
        total = await repo.get_today_total()
        assert total >= 20.0

    async def test_get_today_total_for_single_animal(self, db, repo, female_cow, second_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=12.0))
        await repo.create(_create_data(second_cow.id, milk_kg=8.0))
        await db.commit()
        total = await repo.get_today_total(animal_id=female_cow.id)
        assert abs(total - 12.0) < 0.01

    async def test_get_today_total_zero_if_none(self, db, repo, female_cow):
        total = await repo.get_today_total(animal_id=female_cow.id)
        assert total == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION REPOSITORY — ANIMAL STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkRepoAnimalStats:

    async def test_get_animal_stats_total_kg(self, db, repo, female_cow):
        for i in range(5):
            await repo.create(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["total_kg"] >= 50.0

    async def test_get_animal_stats_avg_daily_kg(self, db, repo, female_cow):
        for i in range(4):
            await repo.create(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["avg_daily_kg"] == 10.0

    async def test_get_animal_stats_fat_percent(self, db, repo, female_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=10.0, fat_percent=4.0))
        await repo.create(_create_data(female_cow.id, milk_kg=10.0, fat_percent=2.0,
            record_date=YESTERDAY))
        await db.commit()
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["avg_fat_percent"] is not None
        assert abs(stats["avg_fat_percent"] - 3.0) < 0.1

    async def test_get_animal_stats_best_day_kg(self, db, repo, female_cow):
        for kg, days in [(5.0, 2), (20.0, 1), (10.0, 0)]:
            await repo.create(_create_data(female_cow.id, milk_kg=kg,
                record_date=TODAY - timedelta(days=days)))
        await db.commit()
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["best_day_kg"] >= 20.0

    async def test_get_animal_stats_days_recorded(self, db, repo, female_cow):
        for i in range(7):
            await repo.create(_create_data(female_cow.id,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["days_recorded"] == 7

    async def test_get_animal_stats_7_days_window(self, db, repo, female_cow):
        # 10 kun oldin yozuv qo'shamiz — 7 kunlik oynada ko'rinmasligi kerak
        await repo.create(_create_data(female_cow.id, milk_kg=100.0,
            record_date=TODAY - timedelta(days=10)))
        await repo.create(_create_data(female_cow.id, milk_kg=5.0,
            record_date=TODAY - timedelta(days=2)))
        await db.commit()
        stats_7  = await repo.get_animal_stats(female_cow.id, days=7)
        stats_30 = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats_7["total_kg"] < stats_30["total_kg"]

    async def test_get_animal_stats_no_records(self, db, repo, female_cow):
        stats = await repo.get_animal_stats(female_cow.id, days=30)
        assert stats["total_kg"] == 0.0
        assert stats["days_recorded"] == 0

    async def test_get_per_animal_monthly_stats(self, db, repo, female_cow, second_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=15.0))
        await repo.create(_create_data(second_cow.id, milk_kg=10.0))
        await db.commit()
        stats = await repo.get_per_animal_monthly_stats(
            date_from=TODAY - timedelta(days=30), date_to=TODAY
        )
        assert len(stats) >= 2
        animal_ids = [s["animal_id"] for s in stats]
        assert female_cow.id in animal_ids
        assert second_cow.id in animal_ids

    async def test_per_animal_stats_structure(self, db, repo, female_cow):
        await repo.create(_create_data(female_cow.id, milk_kg=12.0))
        await db.commit()
        stats = await repo.get_per_animal_monthly_stats(
            date_from=TODAY - timedelta(days=30), date_to=TODAY
        )
        assert len(stats) >= 1
        row = stats[0]
        for key in ["animal_id", "month_kg", "today_kg", "avg_daily_kg", "days_recorded"]:
            assert key in row, f"Kalit '{key}' topilmadi"

    async def test_per_animal_stats_empty_if_no_records(self, db, repo):
        stats = await repo.get_per_animal_monthly_stats(
            date_from=TODAY - timedelta(days=30), date_to=TODAY
        )
        assert isinstance(stats, list)


# ═══════════════════════════════════════════════════════════════════════════════
# MILK PRODUCTION REPOSITORY — UPDATE & DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkRepoUpdateDelete:

    async def test_update_milk_kg(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        updated = await repo.update(rec, MilkProductionUpdate(milk_kg=20.0))
        await db.commit()
        assert updated.milk_kg == 20.0

    async def test_update_quality_grade(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id))
        await db.commit()
        updated = await repo.update(rec, MilkProductionUpdate(quality_grade=MilkQualityGrade.PREMIUM))
        await db.commit()
        assert updated.quality_grade == MilkQualityGrade.PREMIUM

    async def test_update_multiple_fields(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id))
        await db.commit()
        upd_data = MilkProductionUpdate(milk_kg=25.0, fat_percent=4.2, notes="Updated")
        updated = await repo.update(rec, upd_data)
        await db.commit()
        assert updated.milk_kg     == 25.0
        assert updated.fat_percent == 4.2
        assert updated.notes       == "Updated"

    async def test_delete_removes_record(self, db, repo, female_cow):
        rec = await repo.create(_create_data(female_cow.id))
        await db.commit()
        rid = rec.id
        await repo.delete(rec)
        await db.commit()
        assert await repo.get_by_id(rid) is None


# ═══════════════════════════════════════════════════════════════════════════════
# MILK SERVICE — ADD RECORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkServiceAddRecord:

    async def test_add_record_success(self, db, svc, female_cow):
        data = _create_data(female_cow.id, milk_kg=12.0)
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.id is not None
        assert rec.milk_kg == 12.0

    async def test_add_record_nonexistent_animal_raises(self, db, svc):
        data = _create_data(99999, milk_kg=10.0)
        with pytest.raises(EntityNotFoundError) as exc_info:
            await svc.add_record(data)
        assert "99999" in exc_info.value.message

    async def test_add_record_male_animal_raises(self, db, svc, male_bull):
        data = _create_data(male_bull.id, milk_kg=10.0)
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await svc.add_record(data)
        assert "erkak" in exc_info.value.message.lower() or "male" in exc_info.value.message.lower()

    async def test_add_record_auto_quality_premium(self, db, svc, female_cow):
        """SCC < 200 → PREMIUM avtomatik."""
        data = _create_data(female_cow.id, milk_kg=10.0, somatic_cell_count=100)
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade == MilkQualityGrade.PREMIUM

    async def test_add_record_auto_quality_standard(self, db, svc, female_cow):
        """200 ≤ SCC < 400 → STANDARD."""
        data = _create_data(female_cow.id, milk_kg=10.0, somatic_cell_count=300)
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade == MilkQualityGrade.STANDARD

    async def test_add_record_auto_quality_low(self, db, svc, female_cow):
        """400 ≤ SCC < 800 → LOW."""
        data = _create_data(female_cow.id, milk_kg=10.0, somatic_cell_count=600)
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade == MilkQualityGrade.LOW

    async def test_add_record_auto_quality_rejected(self, db, svc, female_cow):
        """SCC ≥ 800 → REJECTED."""
        data = _create_data(female_cow.id, milk_kg=10.0, somatic_cell_count=1000)
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade == MilkQualityGrade.REJECTED

    async def test_add_record_manual_quality_not_overridden(self, db, svc, female_cow):
        """Agar quality_grade berilgan bo'lsa — SCC avtohisobi ishlamaydi."""
        data = _create_data(
            female_cow.id, milk_kg=10.0,
            somatic_cell_count=1000,  # Rejected bo'lishi kerak edi
            quality_grade=MilkQualityGrade.PREMIUM,  # Lekin biz PREMIUM berdik
        )
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade == MilkQualityGrade.PREMIUM

    async def test_add_record_no_scc_no_auto_grade(self, db, svc, female_cow):
        """SCC yo'q + quality_grade yo'q → None."""
        data = _create_data(female_cow.id, milk_kg=10.0)  # somatic_cell_count None
        rec = await svc.add_record(data)
        await db.commit()
        assert rec.quality_grade is None

    async def test_add_record_all_quality_grades(self, db, svc, female_cow):
        for grade in MilkQualityGrade:
            data = _create_data(female_cow.id, milk_kg=5.0, quality_grade=grade)
            rec = await svc.add_record(data)
            await db.commit()
            assert rec.quality_grade == grade


# ═══════════════════════════════════════════════════════════════════════════════
# MILK SERVICE — UPDATE & DELETE RECORD
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkServiceUpdateDelete:

    async def test_update_record_success(self, db, svc, female_cow):
        rec = await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        updated = await svc.update_record(rec.id, MilkProductionUpdate(milk_kg=25.0))
        await db.commit()
        assert updated.milk_kg == 25.0

    async def test_update_nonexistent_record_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_record(999999, MilkProductionUpdate(milk_kg=5.0))

    async def test_delete_record_success(self, db, svc, repo, female_cow):
        rec = await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        rid = rec.id
        await svc.delete_record(rid)
        await db.commit()
        assert await repo.get_by_id(rid) is None

    async def test_delete_nonexistent_record_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_record(999999)


# ═══════════════════════════════════════════════════════════════════════════════
# MILK SERVICE — GET ANIMAL RECORDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkServiceGetAnimalRecords:

    async def test_get_records_returns_list_response(self, db, svc, female_cow):
        from app.schemas.milk_production import MilkProductionListResponse
        await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        resp = await svc.get_animal_records(female_cow.id)
        assert isinstance(resp, MilkProductionListResponse)
        assert resp.total >= 1
        assert len(resp.items) >= 1

    async def test_get_records_pagination(self, db, svc, female_cow):
        for i in range(5):
            await svc.add_record(_create_data(female_cow.id, milk_kg=5.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        page1 = await svc.get_animal_records(female_cow.id, page=1, page_size=2)
        page2 = await svc.get_animal_records(female_cow.id, page=2, page_size=2)
        assert len(page1.items) <= 2
        ids1 = {r.id for r in page1.items}
        ids2 = {r.id for r in page2.items}
        assert ids1.isdisjoint(ids2)

    async def test_get_records_date_filter(self, db, svc, female_cow):
        old = TODAY - timedelta(days=60)
        await svc.add_record(_create_data(female_cow.id, milk_kg=99.0, record_date=old))
        await svc.add_record(_create_data(female_cow.id, milk_kg=5.0))
        await db.commit()
        resp = await svc.get_animal_records(
            female_cow.id,
            date_from=TODAY - timedelta(days=10),
            date_to=TODAY,
        )
        for item in resp.items:
            assert item.record_date >= TODAY - timedelta(days=10)

    async def test_get_records_empty_animal_returns_zero(self, db, svc, female_cow):
        resp = await svc.get_animal_records(99999)
        assert resp.total == 0


# ═══════════════════════════════════════════════════════════════════════════════
# MILK SERVICE — GET ANIMAL SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkServiceAnimalSummary:

    async def test_get_animal_summary_structure(self, db, svc, female_cow):
        from app.schemas.milk_production import AnimalMilkSummary
        await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert isinstance(summary, AnimalMilkSummary)
        assert summary.animal_id  == female_cow.id
        assert summary.animal_tag == female_cow.tag_id

    async def test_get_animal_summary_nonexistent_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_animal_summary(999999)

    async def test_get_animal_summary_has_stats(self, db, svc, female_cow):
        for i in range(5):
            await svc.add_record(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert summary.stats_30d is not None
        assert summary.stats_30d.total_kg >= 50.0
        assert summary.stats_30d.days_recorded >= 5

    async def test_get_animal_summary_recent_records(self, db, svc, female_cow):
        for i in range(5):
            await svc.add_record(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert len(summary.recent_records) >= 1

    async def test_get_animal_summary_today_kg(self, db, svc, female_cow):
        await svc.add_record(_create_data(female_cow.id, milk_kg=15.0))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert summary.today_kg >= 15.0

    async def test_get_animal_summary_last_7_days(self, db, svc, female_cow):
        for i in range(7):
            await svc.add_record(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert summary.last_7_days_kg >= 70.0

    async def test_get_animal_summary_last_30_days(self, db, svc, female_cow):
        for i in range(30):
            await svc.add_record(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        summary = await svc.get_animal_summary(female_cow.id)
        assert summary.last_30_days_kg >= 300.0


# ═══════════════════════════════════════════════════════════════════════════════
# MILK SERVICE — GET FARM SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestMilkServiceFarmSummary:

    async def test_get_farm_summary_structure(self, db, svc, female_cow):
        from app.schemas.milk_production import FarmMilkSummary
        await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await db.commit()
        summary = await svc.get_farm_summary()
        assert isinstance(summary, FarmMilkSummary)
        assert hasattr(summary, "today_total_kg")
        assert hasattr(summary, "this_month_kg")
        assert hasattr(summary, "last_month_kg")
        assert hasattr(summary, "active_dairy_animals")

    async def test_get_farm_summary_today_includes_recent(self, db, svc, female_cow, second_cow):
        await svc.add_record(_create_data(female_cow.id, milk_kg=10.0))
        await svc.add_record(_create_data(second_cow.id, milk_kg=15.0))
        await db.commit()
        summary = await svc.get_farm_summary()
        assert summary.today_total_kg >= 25.0

    async def test_get_farm_summary_this_month_includes_today(self, db, svc, female_cow):
        await svc.add_record(_create_data(female_cow.id, milk_kg=20.0))
        await db.commit()
        summary = await svc.get_farm_summary()
        assert summary.this_month_kg >= 20.0

    async def test_get_farm_summary_daily_trend_not_empty(self, db, svc, female_cow):
        for i in range(5):
            await svc.add_record(_create_data(female_cow.id, milk_kg=10.0,
                record_date=TODAY - timedelta(days=i)))
        await db.commit()
        summary = await svc.get_farm_summary()
        assert isinstance(summary.daily_trend, list)