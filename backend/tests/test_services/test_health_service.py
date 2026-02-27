"""
Taurus Vision — Health Record Service Tests (Sprint 11-12)

Service qatlamini unit testlari.
DB integrasiyasi bilan ishlaydi (in-memory SQLite yoki test PostgreSQL).

Test qamrovi:
    create_health_record     — Yaratish + validatsiya
    get_record_by_id         — ID bo'yicha olish
    get_animal_records       — Jonivor yozuvlari
    get_records_by_type      — Tur bo'yicha filtr
    get_records_by_severity  — Og'irlik bo'yicha filtr
    get_unresolved_records   — Hal etilmaganlar
    get_critical_records     — Kritik yozuvlar
    update_health_record     — Yangilash
    resolve_health_record    — Hal etilgan belgilash
    delete_health_record     — O'chirish
    get_health_statistics    — Statistika
    get_health_summary       — Xulosa
    _calculate_health_score  — Balni hisoblash mantiq
    _get_health_status       — Status belgilash mantiq
"""

import pytest
from datetime import datetime, date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.asyncio, pytest.mark.services]


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def service(db: AsyncSession):
    """HealthRecordService instance."""
    from app.services.health_record_service import HealthRecordService
    return HealthRecordService(db)


@pytest.fixture
def valid_types():
    """Barcha HealthRecordType lari."""
    from app.models.health_record import HealthRecordType
    return list(HealthRecordType)


@pytest.fixture
def valid_severities():
    """Barcha HealthRecordSeverity lari."""
    from app.models.health_record import HealthRecordSeverity
    return list(HealthRecordSeverity)


async def _make_record(
    service,
    db: AsyncSession,
    animal,
    **kwargs,
):
    """Yordamchi: health record yaratadi."""
    from app.models.health_record import HealthRecordType, HealthRecordSeverity
    return await service.create_health_record(
        db           = db,
        animal_id    = animal.id,
        record_type  = kwargs.get("record_type",  HealthRecordType.CHECKUP),
        severity     = kwargs.get("severity",     HealthRecordSeverity.NORMAL),
        diagnosis    = kwargs.get("diagnosis",    "Routine checkup"),
        symptoms     = kwargs.get("symptoms",     None),
        treatment    = kwargs.get("treatment",    None),
        medication   = kwargs.get("medication",   None),
        dosage       = kwargs.get("dosage",       None),
        veterinarian = kwargs.get("veterinarian", "Dr. Test"),
        clinic_name  = kwargs.get("clinic_name",  None),
        cost         = kwargs.get("cost",         None),
        notes        = kwargs.get("notes",        None),
        next_checkup_date = kwargs.get("next_checkup_date", None),
    )


# =============================================================================
# YARATISH TESTLARI
# =============================================================================

class TestCreateHealthRecord:
    """create_health_record() metodi testlari."""

    async def test_create_returns_health_record(
        self, service, db: AsyncSession, sample_animal
    ):
        """Record yaratiladi va qaytariladi."""
        from app.models.health_record import HealthRecord
        record = await _make_record(service, db, sample_animal)
        assert isinstance(record, HealthRecord)
        assert record.id is not None
        assert record.id > 0

    async def test_create_stores_correct_animal_id(
        self, service, db: AsyncSession, sample_animal
    ):
        """animal_id to'g'ri saqlanadi."""
        record = await _make_record(service, db, sample_animal)
        assert record.animal_id == sample_animal.id

    async def test_create_defaults_is_resolved_false(
        self, service, db: AsyncSession, sample_animal
    ):
        """Yangi record is_resolved=False."""
        record = await _make_record(service, db, sample_animal)
        assert record.is_resolved is False
        assert record.resolved_at is None

    async def test_create_all_record_types(
        self, service, db: AsyncSession, sample_animal, valid_types
    ):
        """Barcha HealthRecordType lari muvaffaqiyatli yaratiladi."""
        for rt in valid_types:
            from app.models.health_record import HealthRecordSeverity
            record = await _make_record(
                service, db, sample_animal,
                record_type = rt,
                diagnosis   = f"Test {rt.value}",
            )
            assert record.record_type == rt, f"Type {rt.value} mismatch"

    async def test_create_all_severities(
        self, service, db: AsyncSession, sample_animal, valid_severities
    ):
        """Barcha HealthRecordSeverity lari muvaffaqiyatli yaratiladi."""
        for sev in valid_severities:
            from app.models.health_record import HealthRecordType
            record = await _make_record(
                service, db, sample_animal,
                severity  = sev,
                diagnosis = f"Test {sev.value}",
            )
            assert record.severity == sev

    async def test_create_with_all_optional_fields(
        self, service, db: AsyncSession, sample_animal
    ):
        """Barcha ixtiyoriy maydonlar saqlanadi."""
        next_checkup = date.today() + timedelta(days=30)
        record = await _make_record(
            service, db, sample_animal,
            symptoms         = "High temperature, loss of appetite",
            treatment        = "Antibiotics administered",
            medication       = "Penicillin G",
            dosage           = "10000 IU/kg IM",
            veterinarian     = "Dr. Rahimov",
            clinic_name      = "Samarqand Vet Klinikasi",
            cost             = 75000.0,
            notes            = "Follow-up in 7 days",
            next_checkup_date = next_checkup,
        )
        assert record.symptoms     == "High temperature, loss of appetite"
        assert record.treatment    == "Antibiotics administered"
        assert record.medication   == "Penicillin G"
        assert record.dosage       == "10000 IU/kg IM"
        assert record.veterinarian == "Dr. Rahimov"
        assert record.clinic_name  == "Samarqand Vet Klinikasi"
        assert record.cost         == 75000.0
        assert record.next_checkup_date == next_checkup

    async def test_create_raises_for_nonexistent_animal(
        self, service, db: AsyncSession
    ):
        """Yo'q jonivor uchun ValueError."""
        from app.models.health_record import HealthRecordType, HealthRecordSeverity

        with pytest.raises(ValueError, match="not found"):
            await service.create_health_record(
                db          = db,
                animal_id   = 999999,
                record_type = HealthRecordType.CHECKUP,
                severity    = HealthRecordSeverity.NORMAL,
                diagnosis   = "Ghost animal test",
            )

    async def test_create_raises_for_past_checkup_date(
        self, service, db: AsyncSession, sample_animal
    ):
        """O'tgan sana next_checkup_date — ValueError."""
        past_date = date.today() - timedelta(days=1)
        with pytest.raises(ValueError, match="past"):
            await _make_record(
                service, db, sample_animal,
                next_checkup_date = past_date,
            )

    async def test_create_raises_for_negative_cost(
        self, service, db: AsyncSession, sample_animal
    ):
        """Manfiy xarajat — ValueError."""
        with pytest.raises(ValueError, match="negative"):
            await _make_record(
                service, db, sample_animal,
                cost = -100.0,
            )

    async def test_create_sets_recorded_at(
        self, service, db: AsyncSession, sample_animal
    ):
        """recorded_at avtomatik o'rnatiladi."""
        before = datetime.utcnow()
        record = await _make_record(service, db, sample_animal)
        after  = datetime.utcnow()

        assert record.recorded_at is not None
        assert before <= record.recorded_at <= after


# =============================================================================
# OLISH TESTLARI
# =============================================================================

class TestGetHealthRecord:
    """get_record_by_id() va get_animal_records() testlari."""

    async def test_get_by_id_returns_correct_record(
        self, service, db: AsyncSession, sample_animal
    ):
        """ID bo'yicha to'g'ri record qaytadi."""
        created = await _make_record(
            service, db, sample_animal, diagnosis="Get by ID test"
        )
        fetched = await service.get_record_by_id(db, created.id)
        assert fetched is not None
        assert fetched.id       == created.id
        assert fetched.diagnosis == "Get by ID test"

    async def test_get_by_id_returns_none_for_missing(
        self, service, db: AsyncSession
    ):
        """Yo'q ID — None yoki EntityNotFoundError."""
        from app.core.exceptions import EntityNotFoundError
        try:
            result = await service.get_record_by_id(db, 999999)
            assert result is None
        except EntityNotFoundError:
            pass  # Bu ham to'g'ri

    async def test_get_animal_records_returns_list(
        self, service, db: AsyncSession, sample_animal
    ):
        """Jonivor yozuvlari ro'yxat sifatida qaytadi."""
        for i in range(3):
            await _make_record(
                service, db, sample_animal,
                diagnosis=f"Record #{i}",
            )

        records, total = await service.get_animal_records(
            db, sample_animal.id, skip=0, limit=10
        )
        assert isinstance(records, list)
        assert total >= 3

    async def test_get_animal_records_pagination(
        self, service, db: AsyncSession, sample_animal
    ):
        """Pagination ishlaydi."""
        for i in range(6):
            await _make_record(
                service, db, sample_animal,
                diagnosis=f"Pagination #{i}",
            )

        records_p1, total = await service.get_animal_records(
            db, sample_animal.id, skip=0, limit=3
        )
        records_p2, _     = await service.get_animal_records(
            db, sample_animal.id, skip=3, limit=3
        )

        assert len(records_p1) <= 3
        assert len(records_p2) <= 3
        assert total >= 6

        ids_p1 = {r.id for r in records_p1}
        ids_p2 = {r.id for r in records_p2}
        assert ids_p1.isdisjoint(ids_p2), "Pagination kesishmasligi kerak"

    async def test_get_records_by_type_filters_correctly(
        self, service, db: AsyncSession, sample_animal
    ):
        """record_type filtr ishlaydi."""
        from app.models.health_record import HealthRecordType

        await _make_record(
            service, db, sample_animal,
            record_type = HealthRecordType.VACCINATION,
            diagnosis   = "Vaccination record",
        )
        await _make_record(
            service, db, sample_animal,
            record_type = HealthRecordType.INJURY,
            diagnosis   = "Injury record",
        )

        records, _ = await service.get_records_by_type(
            db, sample_animal.id, HealthRecordType.VACCINATION
        )
        for r in records:
            assert r.record_type == HealthRecordType.VACCINATION

    async def test_get_records_by_severity_filters_correctly(
        self, service, db: AsyncSession, sample_animal
    ):
        """severity filtr ishlaydi."""
        from app.models.health_record import HealthRecordSeverity, HealthRecordType

        await _make_record(
            service, db, sample_animal,
            severity    = HealthRecordSeverity.CRITICAL,
            record_type = HealthRecordType.ILLNESS,
            diagnosis   = "Critical severity test",
        )

        records, _ = await service.get_records_by_severity(
            db, sample_animal.id, HealthRecordSeverity.CRITICAL
        )
        for r in records:
            assert r.severity == HealthRecordSeverity.CRITICAL


# =============================================================================
# YANGILASH TESTLARI
# =============================================================================

class TestUpdateHealthRecord:
    """update_health_record() metodi testlari."""

    async def test_update_diagnosis(
        self, service, db: AsyncSession, sample_animal
    ):
        """Diagnosis muvaffaqiyatli yangilanadi."""
        record = await _make_record(
            service, db, sample_animal, diagnosis="Original"
        )
        updated = await service.update_health_record(
            db, record.id, {"diagnosis": "Updated diagnosis"}
        )
        assert updated.diagnosis == "Updated diagnosis"

    async def test_update_severity(
        self, service, db: AsyncSession, sample_animal
    ):
        """Severity yangilanadi."""
        from app.models.health_record import HealthRecordSeverity

        record = await _make_record(
            service, db, sample_animal,
            severity=HealthRecordSeverity.NORMAL
        )
        updated = await service.update_health_record(
            db, record.id, {"severity": HealthRecordSeverity.WARNING}
        )
        assert updated.severity == HealthRecordSeverity.WARNING

    async def test_update_nonexistent_raises(
        self, service, db: AsyncSession
    ):
        """Yo'q record yangilash — xato."""
        from app.core.exceptions import EntityNotFoundError

        with pytest.raises((EntityNotFoundError, ValueError)):
            await service.update_health_record(
                db, 999999, {"diagnosis": "Ghost"}
            )


# =============================================================================
# HAL ETISH TESTLARI
# =============================================================================

class TestResolveHealthRecord:
    """resolve_health_record() metodi testlari."""

    async def test_resolve_sets_is_resolved(
        self, service, db: AsyncSession, sample_animal
    ):
        """is_resolved = True ga o'rnatiladi."""
        record = await _make_record(service, db, sample_animal)
        assert record.is_resolved is False

        resolved = await service.resolve_health_record(
            db, record.id, resolution_note="Fully healed"
        )
        assert resolved.is_resolved is True

    async def test_resolve_sets_resolved_at(
        self, service, db: AsyncSession, sample_animal
    ):
        """resolved_at timestamp o'rnatiladi."""
        record  = await _make_record(service, db, sample_animal)
        before  = datetime.utcnow()
        resolved = await service.resolve_health_record(db, record.id)
        after   = datetime.utcnow()

        assert resolved.resolved_at is not None
        assert before <= resolved.resolved_at <= after

    async def test_resolve_nonexistent_raises(
        self, service, db: AsyncSession
    ):
        """Yo'q record hal etish — xato."""
        from app.core.exceptions import EntityNotFoundError
        with pytest.raises((EntityNotFoundError, ValueError)):
            await service.resolve_health_record(db, 999999)


# =============================================================================
# O'CHIRISH TESTLARI
# =============================================================================

class TestDeleteHealthRecord:
    """delete_health_record() metodi testlari."""

    async def test_delete_removes_record(
        self, service, db: AsyncSession, sample_animal
    ):
        """Record o'chirilgandan so'ng topilmaydi."""
        from app.core.exceptions import EntityNotFoundError

        record = await _make_record(service, db, sample_animal)
        record_id = record.id

        await service.delete_health_record(db, record_id)

        # O'chirilgandan keyin topilmasligi kerak
        try:
            fetched = await service.get_record_by_id(db, record_id)
            assert fetched is None
        except EntityNotFoundError:
            pass  # Bu ham to'g'ri

    async def test_delete_nonexistent_raises(
        self, service, db: AsyncSession
    ):
        """Yo'q record o'chirish — xato."""
        from app.core.exceptions import EntityNotFoundError
        with pytest.raises((EntityNotFoundError, ValueError)):
            await service.delete_health_record(db, 999999)


# =============================================================================
# STATISTIKA TESTLARI
# =============================================================================

class TestHealthStatistics:
    """get_health_statistics() va get_health_summary() testlari."""

    async def test_statistics_returns_dict(
        self, service, db: AsyncSession, sample_animal
    ):
        """Statistika dict qaytaradi."""
        result = await service.get_health_statistics(db, animal_id=sample_animal.id)
        assert isinstance(result, dict)

    async def test_statistics_counts_records(
        self, service, db: AsyncSession, sample_animal
    ):
        """total_records to'g'ri hisoblanadi."""
        for i in range(3):
            await _make_record(
                service, db, sample_animal,
                diagnosis=f"Stats test #{i}",
            )
        stats = await service.get_health_statistics(db, animal_id=sample_animal.id)
        assert stats.get("total_records", 0) >= 3

    async def test_summary_structure(
        self, service, db: AsyncSession, sample_animal
    ):
        """Xulosa barcha kerakli kalitlarni o'z ichiga oladi."""
        summary = await service.get_health_summary(db, sample_animal.id)

        required = [
            "animal_id", "total_records", "unresolved_issues",
            "health_score", "health_status",
        ]
        for key in required:
            assert key in summary, f"Summary key '{key}' missing"

    async def test_summary_animal_id_matches(
        self, service, db: AsyncSession, sample_animal
    ):
        """Summary animal_id to'g'ri."""
        summary = await service.get_health_summary(db, sample_animal.id)
        assert summary["animal_id"] == sample_animal.id

    async def test_summary_nonexistent_animal_raises(
        self, service, db: AsyncSession
    ):
        """Yo'q jonivor — ValueError."""
        with pytest.raises(ValueError, match="not found"):
            await service.get_health_summary(db, 999999)


# =============================================================================
# BALL HISOBLASH TESTLARI (UNIT)
# =============================================================================

class TestCalculateHealthScore:
    """_calculate_health_score() mantiq testlari."""

    def test_perfect_score_no_issues(self, service):
        """Muammo yo'q — 100 ball."""
        stats = {
            "total_records":         5,
            "unresolved":            0,
            "critical_unresolved":   0,
            "by_severity":           {"normal": 5, "warning": 0, "critical": 0},
        }
        score = service._calculate_health_score(stats)
        assert score == 100

    def test_critical_unresolved_deducts_points(self, service):
        """Hal etilmagan kritik — ball kamayadi."""
        stats_clean = {
            "total_records": 5, "unresolved": 0, "critical_unresolved": 0,
            "by_severity": {"normal": 5},
        }
        stats_critical = {
            "total_records": 5, "unresolved": 2, "critical_unresolved": 2,
            "by_severity": {"normal": 3, "critical": 2},
        }
        score_clean    = service._calculate_health_score(stats_clean)
        score_critical = service._calculate_health_score(stats_critical)
        assert score_critical < score_clean

    def test_score_minimum_is_zero(self, service):
        """Ball 0 dan past tushmaydi."""
        stats = {
            "total_records":         20,
            "unresolved":            15,
            "critical_unresolved":   10,
            "by_severity":           {"critical": 15, "warning": 5},
        }
        score = service._calculate_health_score(stats)
        assert score >= 0

    def test_score_maximum_is_100(self, service):
        """Ball 100 dan oshib ketmaydi."""
        stats = {
            "total_records": 0, "unresolved": 0, "critical_unresolved": 0,
            "by_severity": {},
        }
        score = service._calculate_health_score(stats)
        assert score <= 100


# =============================================================================
# STATUS BELGILASH TESTLARI (UNIT)
# =============================================================================

class TestGetHealthStatus:
    """_get_health_status() mantiq testlari."""

    @pytest.mark.parametrize("score,expected", [
        (100, "excellent"),
        (90,  "excellent"),
        (89,  "good"),
        (75,  "good"),
        (74,  "fair"),
        (60,  "fair"),
        (59,  "poor"),
        (40,  "poor"),
        (39,  "critical"),
        (0,   "critical"),
    ])
    def test_status_boundaries(self, service, score: int, expected: str):
        """Chegaradagi qiymatlar to'g'ri status qaytaradi."""
        result = service._get_health_status(score)
        assert result == expected, (
            f"score={score}: expected='{expected}', got='{result}'"
        )

    def test_all_statuses_covered(self, service):
        """Barcha 5 ta status qaytarilishi mumkin."""
        all_statuses = set()
        for score in range(0, 101, 5):
            all_statuses.add(service._get_health_status(score))

        expected_statuses = {"excellent", "good", "fair", "poor", "critical"}
        assert all_statuses == expected_statuses


# =============================================================================
# UNRESOLVED VA CRITICAL TESTLARI
# =============================================================================

class TestUnresolvedAndCritical:
    """get_unresolved_records() va get_critical_records() testlari."""

    async def test_unresolved_excludes_resolved(
        self, service, db: AsyncSession, sample_animal
    ):
        """Hal etilgan record unresolved da ko'rinmaydi."""
        record = await _make_record(
            service, db, sample_animal,
            diagnosis="Will be resolved"
        )
        await service.resolve_health_record(db, record.id)

        unresolved, total = await service.get_unresolved_records(
            db, animal_id=sample_animal.id
        )
        resolved_ids = {r.id for r in unresolved}
        assert record.id not in resolved_ids

    async def test_critical_records_only_critical(
        self, service, db: AsyncSession, sample_animal
    ):
        """Critical ro'yxatda faqat critical severity."""
        from app.models.health_record import HealthRecordSeverity, HealthRecordType

        await _make_record(
            service, db, sample_animal,
            severity    = HealthRecordSeverity.CRITICAL,
            record_type = HealthRecordType.ILLNESS,
            diagnosis   = "Critical test record",
        )
        await _make_record(
            service, db, sample_animal,
            severity  = HealthRecordSeverity.NORMAL,
            diagnosis = "Normal test record",
        )

        critical, _ = await service.get_critical_records(db)
        for r in critical:
            assert r.severity == HealthRecordSeverity.CRITICAL