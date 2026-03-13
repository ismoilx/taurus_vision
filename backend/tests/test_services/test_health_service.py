"""
TAURUS VISION — tests/test_services/test_health_service.py
============================================================
HealthRecordRepository + HealthRecordService uchun to'liq testlar.
"""

import pytest
from datetime import date, datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.health_record import HealthRecord, HealthRecordType, HealthRecordSeverity
from app.repositories.health_record import HealthRecordRepository
from app.services.health_record_service import HealthRecordService
from app.core.exceptions import EntityNotFoundError

pytestmark = pytest.mark.asyncio

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
NEXT_WEEK = TODAY + timedelta(days=7)


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="HLT-ANIMAL-001",
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
async def second_animal(db):
    a = Animal(
        tag_id="HLT-ANIMAL-002",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a)
    await db.commit()
    await db.refresh(a)
    return a


def _rec(animal_id, **kw):
    defaults = dict(
        animal_id=animal_id,
        record_type=kw.pop("record_type", HealthRecordType.CHECKUP),
        severity=kw.pop("severity", HealthRecordSeverity.NORMAL),
        diagnosis="Test",
        is_resolved=False,
        recorded_at=datetime.utcnow(),
    )
    defaults.update(kw)
    return HealthRecord(**defaults)


@pytest.fixture
def repo():
    return HealthRecordRepository()


@pytest.fixture
def svc():
    return HealthRecordService(db=None)


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRecordModel:
    def test_repr_contains_key_info(self):
        r = HealthRecord(animal_id=5, record_type=HealthRecordType.VACCINATION,
                         severity=HealthRecordSeverity.NORMAL, diagnosis="FMD")
        s = repr(r)
        assert "5" in s and "vaccination" in s and "normal" in s

    def test_to_dict_required_keys(self):
        r = HealthRecord(animal_id=1, record_type=HealthRecordType.CHECKUP,
                         severity=HealthRecordSeverity.NORMAL, diagnosis="T",
                         is_resolved=False, recorded_at=datetime.utcnow())
        d = r.to_dict()
        for k in ["animal_id", "record_type", "severity", "diagnosis", "is_resolved"]:
            assert k in d

    def test_to_dict_enum_values_are_strings(self):
        r = HealthRecord(animal_id=1, record_type=HealthRecordType.VACCINATION,
                         severity=HealthRecordSeverity.CRITICAL, diagnosis="T")
        d = r.to_dict()
        assert d["record_type"] == "vaccination"
        assert d["severity"]    == "critical"

    def test_to_dict_is_resolved_false(self):
        r = HealthRecord(animal_id=1, record_type=HealthRecordType.CHECKUP,
                         severity=HealthRecordSeverity.NORMAL, diagnosis="T", is_resolved=False)
        assert r.to_dict()["is_resolved"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY — CREATE & GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRepoCreateGet:
    async def test_create_assigns_id(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        assert r.id is not None and r.id > 0

    async def test_create_saves_fields(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id,
            record_type=HealthRecordType.VACCINATION,
            severity=HealthRecordSeverity.WARNING,
            diagnosis="FMD", veterinarian="Dr. X", cost=50000.0))
        assert r.record_type  == HealthRecordType.VACCINATION
        assert r.severity     == HealthRecordSeverity.WARNING
        assert r.veterinarian == "Dr. X"
        assert r.cost         == 50000.0

    async def test_get_by_id_existing(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        found = await repo.get_by_id(db, r.id)
        assert found is not None and found.id == r.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(db, 999999) is None

    async def test_get_by_animal_counts(self, db, repo, animal):
        for _ in range(3):
            await repo.create(db, _rec(animal.id))
        recs, total = await repo.get_by_animal(db, animal.id)
        assert total >= 3

    async def test_get_by_animal_pagination(self, db, repo, animal):
        for _ in range(5):
            await repo.create(db, _rec(animal.id))
        p1, _ = await repo.get_by_animal(db, animal.id, skip=0, limit=2)
        p2, _ = await repo.get_by_animal(db, animal.id, skip=2, limit=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})

    async def test_get_by_animal_own_only(self, db, repo, animal, second_animal):
        await repo.create(db, _rec(animal.id))
        await repo.create(db, _rec(second_animal.id))
        recs, _ = await repo.get_by_animal(db, animal.id)
        assert all(r.animal_id == animal.id for r in recs)


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY — FILTERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRepoFilters:
    async def test_get_by_type_vaccination(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, record_type=HealthRecordType.VACCINATION, diagnosis="v"))
        await repo.create(db, _rec(animal.id, record_type=HealthRecordType.CHECKUP))
        recs, total = await repo.get_by_type(db, HealthRecordType.VACCINATION)
        assert all(r.record_type == HealthRecordType.VACCINATION for r in recs)
        assert total >= 1

    async def test_get_by_severity_critical(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, severity=HealthRecordSeverity.CRITICAL))
        recs, total = await repo.get_by_severity(db, HealthRecordSeverity.CRITICAL)
        assert all(r.severity == HealthRecordSeverity.CRITICAL for r in recs)
        assert total >= 1

    async def test_get_unresolved_only_unresolved(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, is_resolved=False))
        await repo.create(db, _rec(animal.id, is_resolved=True, resolved_at=datetime.utcnow()))
        recs, _ = await repo.get_unresolved(db)
        assert all(not r.is_resolved for r in recs)

    async def test_get_unresolved_by_animal(self, db, repo, animal, second_animal):
        await repo.create(db, _rec(animal.id, is_resolved=False))
        await repo.create(db, _rec(second_animal.id, is_resolved=False))
        recs, _ = await repo.get_unresolved(db, animal_id=animal.id)
        assert all(r.animal_id == animal.id for r in recs)

    async def test_get_critical_unresolved(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, severity=HealthRecordSeverity.CRITICAL, is_resolved=False))
        await repo.create(db, _rec(animal.id, severity=HealthRecordSeverity.CRITICAL,
                                   is_resolved=True, resolved_at=datetime.utcnow()))
        recs, total = await repo.get_critical_unresolved(db)
        assert all(r.severity == HealthRecordSeverity.CRITICAL and not r.is_resolved for r in recs)
        assert total >= 1

    async def test_get_upcoming_in_range(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, next_checkup_date=TODAY + timedelta(days=3)))
        recs, total = await repo.get_upcoming_checkups(db, days_ahead=7)
        assert total >= 1
        for r in recs:
            assert r.next_checkup_date >= TODAY
            assert r.next_checkup_date <= TODAY + timedelta(days=7)

    async def test_get_upcoming_excludes_past(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, next_checkup_date=TODAY - timedelta(days=1)))
        recs, _ = await repo.get_upcoming_checkups(db, days_ahead=7)
        assert all(r.next_checkup_date >= TODAY for r in recs)

    async def test_get_upcoming_excludes_far_future(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, next_checkup_date=TODAY + timedelta(days=30)))
        recs, _ = await repo.get_upcoming_checkups(db, days_ahead=7)
        assert all(r.next_checkup_date <= TODAY + timedelta(days=7) for r in recs)


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY — UPDATE, RESOLVE, DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRepoUpdateResolveDelete:
    async def test_update_field(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        updated = await repo.update(db, r.id, diagnosis="Updated")
        assert updated.diagnosis == "Updated"

    async def test_update_multiple(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        u = await repo.update(db, r.id, treatment="New TX", notes="Note", cost=10000.0)
        assert u.treatment == "New TX" and u.notes == "Note" and u.cost == 10000.0

    async def test_update_missing_returns_none(self, db, repo):
        assert await repo.update(db, 999999, diagnosis="Ghost") is None

    async def test_mark_resolved(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id, is_resolved=False))
        resolved = await repo.mark_resolved(db, r.id)
        assert resolved.is_resolved is True and resolved.resolved_at is not None

    async def test_mark_resolved_custom_ts(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id, is_resolved=False))
        ts = datetime(2025, 6, 15)
        resolved = await repo.mark_resolved(db, r.id, resolved_at=ts)
        assert resolved.resolved_at == ts

    async def test_mark_resolved_missing_returns_none(self, db, repo):
        assert await repo.mark_resolved(db, 999999) is None

    async def test_delete_returns_true(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        assert await repo.delete(db, r.id) is True

    async def test_delete_removes(self, db, repo, animal):
        r = await repo.create(db, _rec(animal.id))
        rid = r.id
        await repo.delete(db, rid)
        assert await repo.get_by_id(db, rid) is None

    async def test_delete_missing_returns_false(self, db, repo):
        assert await repo.delete(db, 999999) is False


# ═══════════════════════════════════════════════════════════════════════════════
# REPOSITORY — STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthRepoStatistics:
    async def test_statistics_structure(self, db, repo, animal):
        stats = await repo.get_statistics(db, animal_id=animal.id)
        for k in ["total_records", "by_type", "by_severity", "unresolved", "critical_unresolved"]:
            assert k in stats

    async def test_total_count(self, db, repo, animal):
        for _ in range(3):
            await repo.create(db, _rec(animal.id))
        stats = await repo.get_statistics(db, animal_id=animal.id)
        assert stats["total_records"] >= 3

    async def test_by_type_counts(self, db, repo, animal):
        for _ in range(2):
            await repo.create(db, _rec(animal.id, record_type=HealthRecordType.VACCINATION, diagnosis="v"))
        await repo.create(db, _rec(animal.id, record_type=HealthRecordType.CHECKUP))
        stats = await repo.get_statistics(db, animal_id=animal.id)
        assert stats["by_type"].get("vaccination", 0) >= 2
        assert stats["by_type"].get("checkup", 0) >= 1

    async def test_unresolved_count(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, is_resolved=False))
        await repo.create(db, _rec(animal.id, is_resolved=False))
        await repo.create(db, _rec(animal.id, is_resolved=True, resolved_at=datetime.utcnow()))
        stats = await repo.get_statistics(db, animal_id=animal.id)
        assert stats["unresolved"] >= 2

    async def test_critical_unresolved_count(self, db, repo, animal):
        await repo.create(db, _rec(animal.id, severity=HealthRecordSeverity.CRITICAL, is_resolved=False))
        stats = await repo.get_statistics(db, animal_id=animal.id)
        assert stats["critical_unresolved"] >= 1

    async def test_global_stats_no_filter(self, db, repo, animal, second_animal):
        await repo.create(db, _rec(animal.id))
        await repo.create(db, _rec(second_animal.id))
        stats = await repo.get_statistics(db)
        assert stats["total_records"] >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthServiceCreate:
    async def test_create_success(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Routine")
        assert r.id is not None and r.animal_id == animal.id

    async def test_create_missing_animal_raises(self, db, svc):
        with pytest.raises(ValueError) as exc_info:
            await svc.create_health_record(db, 999999,
                record_type=HealthRecordType.CHECKUP,
                severity=HealthRecordSeverity.NORMAL, diagnosis="T")
        assert "999999" in str(exc_info.value)

    async def test_create_negative_cost_raises(self, db, svc, animal):
        with pytest.raises(ValueError):
            await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.TREATMENT,
                severity=HealthRecordSeverity.NORMAL, diagnosis="T", cost=-100.0)

    async def test_create_past_checkup_date_raises(self, db, svc, animal):
        with pytest.raises(ValueError):
            await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.CHECKUP,
                severity=HealthRecordSeverity.NORMAL, diagnosis="T",
                next_checkup_date=TODAY - timedelta(days=1))

    async def test_create_today_checkup_date_ok(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="T",
            next_checkup_date=TODAY)
        assert r.next_checkup_date == TODAY

    async def test_create_zero_cost_ok(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Free", cost=0.0)
        assert r.cost == 0.0

    async def test_create_is_resolved_false(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.WARNING, diagnosis="Cold")
        assert r.is_resolved is False

    async def test_create_all_record_types(self, db, svc, animal):
        for rtype in HealthRecordType:
            r = await svc.create_health_record(db, animal.id,
                record_type=rtype, severity=HealthRecordSeverity.NORMAL,
                diagnosis=f"T {rtype.value}")
            assert r.record_type == rtype

    async def test_create_all_severities(self, db, svc, animal):
        for sev in HealthRecordSeverity:
            r = await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.CHECKUP, severity=sev, diagnosis="T")
            assert r.severity == sev


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE — GET & FILTER
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthServiceGet:
    async def test_get_by_id_existing(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="T")
        found = await svc.get_record_by_id(db, r.id)
        assert found is not None and found.id == r.id

    async def test_get_by_id_missing_none(self, db, svc):
        assert await svc.get_record_by_id(db, 999999) is None

    async def test_get_animal_records_tuple(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.VACCINATION,
            severity=HealthRecordSeverity.NORMAL, diagnosis="T")
        recs, total = await svc.get_animal_records(db, animal.id)
        assert total >= 1 and isinstance(recs, list)

    async def test_get_animal_records_pagination(self, db, svc, animal):
        for i in range(5):
            await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.CHECKUP,
                severity=HealthRecordSeverity.NORMAL, diagnosis=f"C{i}")
        p1, _ = await svc.get_animal_records(db, animal.id, skip=0, limit=2)
        p2, _ = await svc.get_animal_records(db, animal.id, skip=2, limit=2)
        assert {r.id for r in p1}.isdisjoint({r.id for r in p2})

    async def test_get_animal_records_missing_raises(self, db, svc):
        with pytest.raises(ValueError):
            await svc.get_animal_records(db, 999999)

    async def test_get_records_by_type(self, db, svc, animal):
        for _ in range(2):
            await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.VACCINATION,
                severity=HealthRecordSeverity.NORMAL, diagnosis="V")
        recs, total = await svc.get_records_by_type(db, animal.id, HealthRecordType.VACCINATION)
        assert total >= 2
        assert all(r.record_type == HealthRecordType.VACCINATION for r in recs)

    async def test_get_records_by_severity(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.CRITICAL, diagnosis="Serious")
        recs, total = await svc.get_records_by_severity(db, animal.id, HealthRecordSeverity.CRITICAL)
        assert total >= 1
        assert all(r.severity == HealthRecordSeverity.CRITICAL for r in recs)

    async def test_get_unresolved(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.WARNING, diagnosis="Active")
        recs, total = await svc.get_unresolved_records(db, animal_id=animal.id)
        assert total >= 1
        assert all(not r.is_resolved for r in recs)

    async def test_get_critical(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.SURGERY,
            severity=HealthRecordSeverity.CRITICAL, diagnosis="Critical")
        recs, total = await svc.get_critical_records(db, animal_id=animal.id)
        assert total >= 1
        assert all(r.severity == HealthRecordSeverity.CRITICAL for r in recs)

    async def test_get_upcoming_checkups(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Upcoming",
            next_checkup_date=TODAY + timedelta(days=3))
        recs, total = await svc.get_upcoming_checkups(db, days_ahead=7)
        assert total >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE — UPDATE & RESOLVE & DELETE
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthServiceUpdateResolveDelete:
    async def test_update_with_dict(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Original")
        u = await svc.update_health_record(db, r.id, {"diagnosis": "Updated"})
        assert u.diagnosis == "Updated"

    async def test_update_with_kwargs(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Original")
        u = await svc.update_health_record(db, r.id, diagnosis="Via kwargs")
        assert u.diagnosis == "Via kwargs"

    async def test_update_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_health_record(db, 999999, {"diagnosis": "Ghost"})

    async def test_resolve(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.WARNING, diagnosis="Healing")
        resolved = await svc.resolve_health_record(db, r.id)
        assert resolved.is_resolved is True and resolved.resolved_at is not None

    async def test_resolve_with_note(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Minor")
        resolved = await svc.resolve_health_record(db, r.id, resolution_note="Recovered")
        assert resolved.notes == "Recovered"

    async def test_resolve_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.resolve_health_record(db, 999999)

    async def test_delete_success(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="To delete")
        assert await svc.delete_health_record(db, r.id) is True

    async def test_delete_removes(self, db, svc, animal):
        r = await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Gone")
        rid = r.id
        await svc.delete_health_record(db, rid)
        assert await svc.get_record_by_id(db, rid) is None

    async def test_delete_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_health_record(db, 999999)


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE — STATISTICS & SCORE
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthServiceStatistics:
    async def test_statistics_structure(self, db, svc, animal):
        stats = await svc.get_health_statistics(db, animal_id=animal.id)
        for k in ["total_records", "unresolved", "critical_unresolved",
                  "by_severity", "by_type", "health_score"]:
            assert k in stats

    async def test_score_100_no_issues(self, db, svc, animal):
        stats = await svc.get_health_statistics(db, animal_id=animal.id)
        assert stats["health_score"] == 100

    async def test_score_decreases_with_unresolved(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Issue")
        stats = await svc.get_health_statistics(db, animal_id=animal.id)
        assert stats["health_score"] < 100

    async def test_score_never_below_zero(self, db, svc, animal):
        for _ in range(10):
            await svc.create_health_record(db, animal.id,
                record_type=HealthRecordType.ILLNESS,
                severity=HealthRecordSeverity.CRITICAL, diagnosis="Critical")
        stats = await svc.get_health_statistics(db, animal_id=animal.id)
        assert stats["health_score"] >= 0

    def test_calculate_score_no_issues(self):
        svc = HealthRecordService(db=None)
        assert svc._calculate_health_score({"critical_unresolved": 0, "unresolved": 0}) == 100

    def test_calculate_score_one_critical(self):
        svc = HealthRecordService(db=None)
        score = svc._calculate_health_score({"critical_unresolved": 1, "unresolved": 1})
        assert score == 75  # 100 - 20 - 5

    def test_calculate_score_clamp_max(self):
        svc = HealthRecordService(db=None)
        assert svc._calculate_health_score({"critical_unresolved": 0, "unresolved": 0}) <= 100

    def test_calculate_score_clamp_min(self):
        svc = HealthRecordService(db=None)
        assert svc._calculate_health_score({"critical_unresolved": 100, "unresolved": 100}) == 0

    def test_status_excellent(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(95) == "excellent"
        assert svc._get_health_status(90) == "excellent"

    def test_status_good(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(89) == "good"
        assert svc._get_health_status(75) == "good"

    def test_status_fair(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(74) == "fair"
        assert svc._get_health_status(60) == "fair"

    def test_status_poor(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(59) == "poor"
        assert svc._get_health_status(40) == "poor"

    def test_status_critical(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(39) == "critical"
        assert svc._get_health_status(0)  == "critical"

    def test_score_boundary_90(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(90) == "excellent"
        assert svc._get_health_status(89) == "good"

    def test_score_boundary_75(self):
        svc = HealthRecordService(db=None)
        assert svc._get_health_status(75) == "good"
        assert svc._get_health_status(74) == "fair"


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE — SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthServiceSummary:
    async def test_summary_structure(self, db, svc, animal):
        summary = await svc.get_health_summary(db, animal.id)
        for k in ["animal_id", "animal_tag", "total_records",
                  "unresolved_issues", "upcoming_checkups",
                  "statistics", "health_score", "health_status"]:
            assert k in summary

    async def test_summary_animal_id(self, db, svc, animal):
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["animal_id"] == animal.id

    async def test_summary_animal_tag(self, db, svc, animal):
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["animal_tag"] == animal.tag_id

    async def test_summary_missing_raises(self, db, svc):
        with pytest.raises(ValueError) as exc_info:
            await svc.get_health_summary(db, 999999)
        assert "999999" in str(exc_info.value)

    async def test_summary_unresolved_issues(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.ILLNESS,
            severity=HealthRecordSeverity.WARNING, diagnosis="Active issue")
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["unresolved_issues"]["count"] >= 1

    async def test_summary_health_score_range(self, db, svc, animal):
        summary = await svc.get_health_summary(db, animal.id)
        assert 0 <= summary["health_score"] <= 100

    async def test_summary_health_status_valid(self, db, svc, animal):
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["health_status"] in {"excellent", "good", "fair", "poor", "critical"}

    async def test_summary_latest_record(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Latest")
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["latest_record"] is not None
        assert "diagnosis" in summary["latest_record"]

    async def test_summary_upcoming_checkups(self, db, svc, animal):
        await svc.create_health_record(db, animal.id,
            record_type=HealthRecordType.CHECKUP,
            severity=HealthRecordSeverity.NORMAL, diagnosis="Future",
            next_checkup_date=TODAY + timedelta(days=3))
        summary = await svc.get_health_summary(db, animal.id)
        assert summary["upcoming_checkups"]["count"] >= 1
        assert summary["upcoming_checkups"]["next_date"] is not None