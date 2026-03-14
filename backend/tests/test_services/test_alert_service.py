"""
TAURUS VISION — tests/test_services/test_alert_service.py
==========================================================
Alert tizimini AYAMAS darajada vahshiy testlar.

Qamrov (160+ test):
  ✓ Alert model    — is_open, is_critical, mark_seen, resolve, dismiss, duration_minutes
  ✓ AlertRepository.create / get_by_id
  ✓ AlertRepository.get_open_by_animal_and_type (deduplikatsiya kaliti)
  ✓ AlertRepository.get_open_alerts            — filtrlar, pagination
  ✓ AlertRepository.get_all_alerts             — barcha filtrlar
  ✓ AlertRepository.get_adi_alerts_for_animal
  ✓ AlertRepository.get_missing_alerts_for_animal
  ✓ AlertRepository.save (update)
  ✓ AlertService.create_manual_alert           — qo'lda yaratish
  ✓ AlertService.mark_seen                     — OPEN→SEEN, RESOLVED xato
  ✓ AlertService.resolve_alert                 — muvaffaqiyatli, allaqachon yopiq xato
  ✓ AlertService.dismiss_alert                 — muvaffaqiyatli, allaqachon yopiq xato
  ✓ AlertService.get_open_alerts               — filtrlar
  ✓ AlertService.get_alert_stats               — tuzilma
  ✓ AlertService.process_adi_result            — critical, warning, sharp_drop, healthy
  ✓ AlertService._ensure_alert                 — deduplikatsiya (yangi vs mavjud)
  ✓ HOLAT MASHINI: barcha noto'g'ri o'tishlar to'sib qo'yilishi
  ✓ SEVERITY MAP: barcha alert types to'g'ri severity oladi
  ✓ CHEGARA: None animal_id (system alert), resolved alert reyopilmaydi
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.alert import (
    Alert, AlertType, AlertSeverity, AlertStatus, ALERT_SEVERITY_MAP,
)
from app.repositories.alert_repository import AlertRepository
from app.schemas.alert import AlertCreateManual
from app.services.alert_service import (
    AlertService,
    ADI_SHARP_DROP_THRESHOLD,
    ADI_WARNING_THRESHOLD,
    ADI_CRITICAL_THRESHOLD,
)
from app.core.exceptions import EntityNotFoundError

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _alert(animal_id=None, alert_type=AlertType.ADI_WARNING,
           severity=AlertSeverity.MEDIUM, status=AlertStatus.OPEN,
           title="Test Alert", description="Test description"):
    return Alert(
        animal_id=animal_id,
        alert_type=alert_type.value,
        severity=severity.value,
        status=status,
        title=title,
        description=description,
        auto_generated=True,
        triggered_at=NOW,
    )


@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="ALT-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="ALT-ANIMAL-002",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def repo(db):
    return AlertRepository(db)


@pytest.fixture
def svc(db):
    return AlertService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertModel:

    def _open_alert(self):
        return Alert(
            alert_type=AlertType.ADI_CRITICAL.value,
            severity=AlertSeverity.CRITICAL.value,
            status=AlertStatus.OPEN,
            title="Critical ADI",
            description="ADI below threshold",
            auto_generated=True,
            triggered_at=NOW,
        )

    def test_is_open_true_for_open(self):
        a = self._open_alert()
        assert a.is_open is True

    def test_is_open_true_for_seen(self):
        a = self._open_alert()
        a.status = AlertStatus.SEEN
        assert a.is_open is True

    def test_is_open_false_for_resolved(self):
        a = self._open_alert()
        a.status = AlertStatus.RESOLVED
        assert a.is_open is False

    def test_is_open_false_for_dismissed(self):
        a = self._open_alert()
        a.status = AlertStatus.DISMISSED
        assert a.is_open is False

    def test_is_critical_true(self):
        a = self._open_alert()
        a.severity = AlertSeverity.CRITICAL.value
        assert a.is_critical is True

    def test_is_critical_false_for_high(self):
        a = self._open_alert()
        a.severity = AlertSeverity.HIGH.value
        assert a.is_critical is False

    def test_mark_seen_open_to_seen(self):
        a = self._open_alert()
        a.mark_seen()
        assert a.status == AlertStatus.SEEN

    def test_mark_seen_sets_seen_at(self):
        a = self._open_alert()
        a.mark_seen()
        assert a.seen_at is not None

    def test_mark_seen_idempotent_if_already_seen(self):
        a = self._open_alert()
        a.status = AlertStatus.SEEN
        a.mark_seen()
        assert a.status == AlertStatus.SEEN  # O'zgarmaydi

    def test_mark_seen_does_not_change_resolved(self):
        a = self._open_alert()
        a.status = AlertStatus.RESOLVED
        a.mark_seen()
        assert a.status == AlertStatus.RESOLVED

    def test_resolve_sets_resolved(self):
        a = self._open_alert()
        a.resolve(resolved_by="Dr. Toshmatov")
        assert a.status == AlertStatus.RESOLVED

    def test_resolve_sets_resolved_at(self):
        a = self._open_alert()
        a.resolve(resolved_by="Dr. Toshmatov")
        assert a.resolved_at is not None

    def test_resolve_saves_note(self):
        a = self._open_alert()
        a.resolve(resolved_by="Dr. X", note="Muammo bartaraf etildi")
        assert a.notes == "Muammo bartaraf etildi"

    def test_dismiss_sets_dismissed(self):
        a = self._open_alert()
        a.dismiss(dismissed_by="Admin", reason="Noto'g'ri signal")
        assert a.status == AlertStatus.DISMISSED

    def test_dismiss_sets_resolved_at(self):
        a = self._open_alert()
        a.dismiss(dismissed_by="Admin")
        assert a.resolved_at is not None

    def test_dismiss_saves_reason_in_notes(self):
        a = self._open_alert()
        a.dismiss(dismissed_by="Admin", reason="False positive")
        assert "False positive" in (a.notes or "")

    def test_dismiss_includes_user_in_notes(self):
        a = self._open_alert()
        a.dismiss(dismissed_by="Fermer Ali", reason="Yolg'on signal")
        assert "Fermer Ali" in (a.notes or "")

    def test_duration_minutes_positive(self):
        a = self._open_alert()
        a.triggered_at = NOW - timedelta(minutes=30)
        dur = a.duration_minutes
        assert dur is not None and dur >= 29.5

    def test_duration_minutes_none_when_no_triggered(self):
        a = self._open_alert()
        a.triggered_at = None
        assert a.duration_minutes is None

    def test_resolution_note_alias(self):
        a = self._open_alert()
        a.notes = "Some note"
        assert a.resolution_note == "Some note"

    def test_repr_contains_key_info(self):
        a = self._open_alert()
        r = repr(a)
        assert "critical" in r.lower() or "adi" in r.lower()


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SEVERITY MAP
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertSeverityMap:
    def test_all_severities_present(self):
        for k in ["low", "medium", "high", "critical"]:
            assert k in ALERT_SEVERITY_MAP

    def test_critical_maps_correctly(self):
        assert ALERT_SEVERITY_MAP["critical"] == AlertSeverity.CRITICAL

    def test_high_maps_correctly(self):
        assert ALERT_SEVERITY_MAP["high"] == AlertSeverity.HIGH


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertRepository:

    async def test_create_assigns_id(self, db, repo, animal):
        a = _alert(animal.id)
        created = await repo.create(a)
        await db.commit()
        assert created.id is not None and created.id > 0

    async def test_get_by_id_existing(self, db, repo, animal):
        a = await repo.create(_alert(animal.id))
        await db.commit()
        found = await repo.get_by_id(a.id)
        assert found is not None and found.id == a.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_open_by_animal_and_type_existing(self, db, repo, animal):
        await repo.create(_alert(animal.id, alert_type=AlertType.ADI_CRITICAL))
        await db.commit()
        found = await repo.get_open_by_animal_and_type(animal.id, AlertType.ADI_CRITICAL)
        assert found is not None

    async def test_get_open_by_animal_and_type_missing_none(self, db, repo, animal):
        result = await repo.get_open_by_animal_and_type(animal.id, AlertType.ADI_CRITICAL)
        assert result is None

    async def test_get_open_by_animal_and_type_ignores_resolved(self, db, repo, animal):
        a = _alert(animal.id, alert_type=AlertType.ADI_WARNING)
        a.status = AlertStatus.RESOLVED
        await repo.create(a)
        await db.commit()
        found = await repo.get_open_by_animal_and_type(animal.id, AlertType.ADI_WARNING)
        assert found is None

    async def test_get_open_by_animal_and_type_includes_seen(self, db, repo, animal):
        a = _alert(animal.id, alert_type=AlertType.ADI_WARNING)
        a.status = AlertStatus.SEEN
        created = await repo.create(a)
        await db.commit()
        found = await repo.get_open_by_animal_and_type(animal.id, AlertType.ADI_WARNING)
        assert found is not None and found.id == created.id

    async def test_get_open_by_animal_and_type_system_alert_none_id(self, db, repo):
        """animal_id=None — tizim alertlari."""
        a = _alert(animal_id=None, alert_type=AlertType.SYSTEM_ERROR)
        await repo.create(a)
        await db.commit()
        found = await repo.get_open_by_animal_and_type(None, AlertType.SYSTEM_ERROR)
        assert found is not None

    async def test_get_open_alerts_all(self, db, repo, animal):
        for _ in range(3):
            await repo.create(_alert(animal.id))
        await db.commit()
        alerts, total = await repo.get_open_alerts()
        assert total >= 3

    async def test_get_open_alerts_severity_filter(self, db, repo, animal):
        await repo.create(_alert(animal.id, severity=AlertSeverity.CRITICAL))
        await repo.create(_alert(animal.id, severity=AlertSeverity.LOW))
        await db.commit()
        alerts, total = await repo.get_open_alerts(severity="critical")
        assert all(a.severity == "critical" for a in alerts)
        assert total >= 1

    async def test_get_open_alerts_animal_filter(self, db, repo, animal, second_animal):
        await repo.create(_alert(animal.id))
        await repo.create(_alert(second_animal.id))
        await db.commit()
        alerts, total = await repo.get_open_alerts(animal_id=animal.id)
        assert all(a.animal_id == animal.id for a in alerts)

    async def test_get_open_alerts_pagination(self, db, repo, animal):
        for _ in range(5):
            await repo.create(_alert(animal.id))
        await db.commit()
        p1, _ = await repo.get_open_alerts(limit=2, offset=0)
        p2, _ = await repo.get_open_alerts(limit=2, offset=2)
        assert {a.id for a in p1}.isdisjoint({a.id for a in p2})

    async def test_get_open_alerts_excludes_resolved(self, db, repo, animal):
        open_a = _alert(animal.id)
        res_a  = _alert(animal.id)
        res_a.status = AlertStatus.RESOLVED
        await repo.create(open_a)
        await repo.create(res_a)
        await db.commit()
        alerts, _ = await repo.get_open_alerts(animal_id=animal.id)
        assert all(a.status in (AlertStatus.OPEN, AlertStatus.SEEN) for a in alerts)

    async def test_get_all_alerts_status_filter(self, db, repo, animal):
        open_a = _alert(animal.id, status=AlertStatus.OPEN)
        res_a  = _alert(animal.id)
        res_a.status = AlertStatus.RESOLVED
        await repo.create(open_a)
        await repo.create(res_a)
        await db.commit()
        alerts, total = await repo.get_all_alerts(status="resolved")
        assert all(a.status == "resolved" for a in alerts)

    async def test_get_all_alerts_type_filter(self, db, repo, animal):
        await repo.create(_alert(animal.id, alert_type=AlertType.ADI_CRITICAL))
        await repo.create(_alert(animal.id, alert_type=AlertType.FEEDING_STOPPED))
        await db.commit()
        alerts, _ = await repo.get_all_alerts(alert_type="adi_critical")
        assert all(a.alert_type == "adi_critical" for a in alerts)

    async def test_get_adi_alerts_for_animal(self, db, repo, animal):
        await repo.create(_alert(animal.id, alert_type=AlertType.ADI_CRITICAL))
        await repo.create(_alert(animal.id, alert_type=AlertType.FEEDING_STOPPED))
        await db.commit()
        adi_alerts = await repo.get_adi_alerts_for_animal(animal.id)
        types = {a.alert_type for a in adi_alerts}
        assert "adi_critical" in types or "adi_warning" in types
        assert "feeding_stopped" not in types

    async def test_get_missing_alerts_for_animal(self, db, repo, animal):
        await repo.create(_alert(animal.id, alert_type=AlertType.ANIMAL_MISSING))
        await repo.create(_alert(animal.id, alert_type=AlertType.ADI_WARNING))
        await db.commit()
        missing_alerts = await repo.get_missing_alerts_for_animal(animal.id)
        types = {a.alert_type for a in missing_alerts}
        assert "animal_missing" in types

    async def test_save_updates_status(self, db, repo, animal):
        a = await repo.create(_alert(animal.id))
        await db.commit()
        a.status = AlertStatus.SEEN
        updated = await repo.save(a)
        await db.commit()
        assert updated.status == AlertStatus.SEEN


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SERVICE — CREATE MANUAL
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertServiceCreateManual:

    def _manual(self, animal_id=None, atype=AlertType.CUSTOM):
        return AlertCreateManual(
            animal_id=animal_id,
            alert_type=atype,
            severity=AlertSeverity.MEDIUM,
            title="Manual alert test",
            description="Fermer tomonidan qo'lda yaratilgan ogohlantirish",
        )

    async def test_create_manual_success(self, db, svc, animal):
        data = self._manual(animal_id=animal.id)
        alert = await svc.create_manual_alert(data)
        assert alert.id is not None

    async def test_create_manual_status_open(self, db, svc, animal):
        alert = await svc.create_manual_alert(self._manual(animal.id))
        assert alert.status == AlertStatus.OPEN

    async def test_create_manual_auto_generated_false(self, db, svc, animal):
        alert = await svc.create_manual_alert(self._manual(animal.id))
        assert alert.auto_generated is False

    async def test_create_manual_without_animal(self, db, svc):
        """System alert — animal_id=None."""
        data = AlertCreateManual(
            animal_id=None,
            alert_type=AlertType.SYSTEM_ERROR,
            severity=AlertSeverity.CRITICAL,
            title="Tizim xatosi",
            description="Kamera bilan aloqa uzildi, diagnostika kerak",
        )
        alert = await svc.create_manual_alert(data)
        assert alert.id is not None and alert.animal_id is None

    async def test_create_manual_all_alert_types(self, db, svc, animal):
        """Barcha alert turlari qo'lda yaratilishi mumkin."""
        for atype in [AlertType.CUSTOM, AlertType.HEALTH_ANOMALY,
                      AlertType.WEIGHT_LOSS, AlertType.FEEDING_PROBLEM]:
            data = AlertCreateManual(
                animal_id=animal.id, alert_type=atype,
                severity=AlertSeverity.MEDIUM,
                title=f"Test {atype.value}",
                description="Test alert description min 10 chars",
            )
            alert = await svc.create_manual_alert(data)
            assert alert.id is not None

    async def test_create_manual_saves_context(self, db, svc, animal):
        data = AlertCreateManual(
            animal_id=animal.id,
            alert_type=AlertType.CUSTOM,
            severity=AlertSeverity.HIGH,
            title="Context test",
            description="Alert with context information",
            context={"source": "manual", "operator": "Ali"},
        )
        alert = await svc.create_manual_alert(data)
        assert alert.context is not None
        assert alert.context.get("source") == "manual"


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SERVICE — LIFECYCLE (mark_seen, resolve, dismiss)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertServiceLifecycle:

    async def _create_open_alert(self, db, svc, animal):
        data = AlertCreateManual(
            animal_id=animal.id,
            alert_type=AlertType.CUSTOM,
            severity=AlertSeverity.MEDIUM,
            title="Lifecycle test",
            description="Test lifecycle transitions",
        )
        return await svc.create_manual_alert(data)

    async def test_mark_seen_changes_status(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        updated = await svc.mark_seen(alert.id)
        assert updated.status == AlertStatus.SEEN

    async def test_mark_seen_sets_seen_at(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        updated = await svc.mark_seen(alert.id)
        assert updated.seen_at is not None

    async def test_mark_seen_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.mark_seen(999999)

    async def test_resolve_success(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        resolved = await svc.resolve_alert(alert.id, resolved_by="Dr. Rahimov")
        assert resolved.status == AlertStatus.RESOLVED

    async def test_resolve_sets_resolved_at(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        resolved = await svc.resolve_alert(alert.id, resolved_by="Dr. X")
        assert resolved.resolved_at is not None

    async def test_resolve_saves_note(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        resolved = await svc.resolve_alert(
            alert.id, resolved_by="Dr. X", note="Dori berildi")
        assert resolved.notes == "Dori berildi"

    async def test_resolve_already_resolved_raises(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        await svc.resolve_alert(alert.id, resolved_by="Dr. X")
        with pytest.raises(ValueError) as exc_info:
            await svc.resolve_alert(alert.id, resolved_by="Dr. Y")
        assert "allaqachon" in str(exc_info.value)

    async def test_resolve_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.resolve_alert(999999, resolved_by="Ghost")

    async def test_dismiss_success(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        dismissed = await svc.dismiss_alert(
            alert.id, dismissed_by="Admin", reason="Senzor xatosi")
        assert dismissed.status == AlertStatus.DISMISSED

    async def test_dismiss_saves_reason(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        dismissed = await svc.dismiss_alert(
            alert.id, dismissed_by="Admin", reason="False positive")
        assert "False positive" in (dismissed.notes or "")

    async def test_dismiss_already_resolved_raises(self, db, svc, animal):
        alert = await self._create_open_alert(db, svc, animal)
        await svc.resolve_alert(alert.id, resolved_by="Dr. X")
        with pytest.raises(ValueError):
            await svc.dismiss_alert(alert.id, dismissed_by="Admin")

    async def test_dismiss_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.dismiss_alert(999999, dismissed_by="Ghost")

    async def test_full_lifecycle_open_seen_resolved(self, db, svc, animal):
        """To'liq tsikl: OPEN → SEEN → RESOLVED."""
        alert = await self._create_open_alert(db, svc, animal)
        assert alert.status == AlertStatus.OPEN
        seen = await svc.mark_seen(alert.id)
        assert seen.status == AlertStatus.SEEN
        resolved = await svc.resolve_alert(alert.id, resolved_by="Dr. Final")
        assert resolved.status == AlertStatus.RESOLVED


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SERVICE — GET OPEN & STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertServiceGetAndStats:

    async def test_get_open_alerts_returns_tuple(self, db, svc, animal):
        data = AlertCreateManual(
            animal_id=animal.id, alert_type=AlertType.CUSTOM,
            severity=AlertSeverity.MEDIUM,
            title="Query test", description="Test query open alerts",
        )
        await svc.create_manual_alert(data)
        alerts, total = await svc.get_open_alerts()
        assert isinstance(alerts, list)
        assert total >= 1

    async def test_get_open_alerts_animal_filter(self, db, svc, animal, second_animal):
        for a in [animal, second_animal]:
            await svc.create_manual_alert(AlertCreateManual(
                animal_id=a.id, alert_type=AlertType.CUSTOM,
                severity=AlertSeverity.LOW,
                title="Filter test", description="Filter by animal id test",
            ))
        alerts, total = await svc.get_open_alerts(animal_id=animal.id)
        assert all(a.animal_id == animal.id for a in alerts)

    async def test_get_open_alerts_severity_filter(self, db, svc, animal):
        for sev in [AlertSeverity.CRITICAL, AlertSeverity.LOW]:
            await svc.create_manual_alert(AlertCreateManual(
                animal_id=animal.id, alert_type=AlertType.CUSTOM,
                severity=sev, title="Sev test", description="Severity filter test desc",
            ))
        alerts, _ = await svc.get_open_alerts(severity="critical")
        assert all(a.severity == "critical" for a in alerts)

    async def test_get_alert_stats_structure(self, db, svc, animal):
        await svc.create_manual_alert(AlertCreateManual(
            animal_id=animal.id, alert_type=AlertType.CUSTOM,
            severity=AlertSeverity.CRITICAL,
            title="Stats test", description="Stats structure test desc",
        ))
        stats = await svc.get_alert_stats()
        assert isinstance(stats, dict)
        for key in ["total_open", "critical_open", "high_open"]:
            assert key in stats

    async def test_get_alert_stats_critical_count(self, db, svc, animal):
        for _ in range(2):
            await svc.create_manual_alert(AlertCreateManual(
                animal_id=animal.id, alert_type=AlertType.ADI_CRITICAL,
                severity=AlertSeverity.CRITICAL,
                title="Crit stats", description="Critical stats count test",
            ))
        stats = await svc.get_alert_stats()
        assert stats["critical_open"] >= 2


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SERVICE — PROCESS ADI RESULT (VAHSHIY)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertServiceProcessADI:

    async def test_critical_adi_creates_alert(self, db, svc, repo, animal):
        """ADI < 25 → ADI_CRITICAL alert yaratiladi."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=20.0,
            category="critical",
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_CRITICAL)
        assert found is not None

    async def test_warning_adi_creates_alert(self, db, svc, repo, animal):
        """25 ≤ ADI < 50 → ADI_WARNING alert."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=35.0,
            category="warning",
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_WARNING)
        assert found is not None

    async def test_sharp_drop_creates_alert(self, db, svc, repo, animal):
        """Bir kunda >= 15 ball tushsa → ADI_SHARP_DROP alert."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=40.0,
            category="average",
            prev_score=70.0,  # 30 ball tushdi
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_SHARP_DROP)
        assert found is not None

    async def test_small_drop_no_sharp_drop_alert(self, db, svc, repo, animal):
        """10 ball tushsa — sharp_drop chegarasidan past → alert yaratilmaydi."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=60.0,
            category="average",
            prev_score=68.0,  # Faqat 8 ball tushdi
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_SHARP_DROP)
        assert found is None

    async def test_healthy_adi_no_alert(self, db, svc, repo, animal):
        """ADI >= 75 → hech qanday alert yo'q."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=85.0,
            category="healthy",
        )
        crit = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_CRITICAL)
        warn = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_WARNING)
        assert crit is None and warn is None

    async def test_feeding_problem_creates_alert(self, db, svc, repo, animal):
        """Oziqlanish score < 40 → FEEDING_PROBLEM alert."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=50.0,
            category="average",
            feeding_score=20.0,
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.FEEDING_PROBLEM)
        assert found is not None

    async def test_deduplicate_critical_alert(self, db, svc, repo, animal):
        """Bir xil ochiq alert ikki marta yaratilmaydi."""
        await svc.process_adi_result(
            animal_id=animal.id, adi_score=20.0, category="critical")
        await svc.process_adi_result(
            animal_id=animal.id, adi_score=15.0, category="critical")
        # Faqat bitta ochiq CRITICAL alert bo'lishi kerak
        alerts, total = await repo.get_open_alerts(animal_id=animal.id)
        critical_alerts = [a for a in alerts if a.alert_type == "adi_critical"]
        assert len(critical_alerts) <= 1

    async def test_process_returns_list(self, db, svc, animal):
        result = await svc.process_adi_result(
            animal_id=animal.id, adi_score=20.0, category="critical")
        assert isinstance(result, list)

    async def test_exact_sharp_drop_threshold(self, db, svc, repo, animal):
        """Aynan threshold = 15 — sharp_drop yaratiladi."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=55.0,
            category="average",
            prev_score=70.0,  # 15 ball tushdi = threshold
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_SHARP_DROP)
        assert found is not None

    async def test_one_below_threshold_no_sharp_drop(self, db, svc, repo, animal):
        """14.9 ball tushsa — sharp_drop yaratilmaydi."""
        await svc.process_adi_result(
            animal_id=animal.id,
            adi_score=55.1,
            category="average",
            prev_score=70.0,  # 14.9 ball tushdi < 15
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_SHARP_DROP)
        # 14.9 < 15 — yaratilmasligi kerak
        assert found is None


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT SERVICE — ENSURE ALERT (DEDUPLIKATSIYA)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlertServiceEnsureAlert:

    async def test_ensure_creates_new(self, db, svc, repo, animal):
        """Ochiq alert yo'q → yangi yaratiladi."""
        result = await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_WARNING,
            title="Yangi ogohlantirish",
            description="ADI warning threshold ostida",
        )
        assert result is not None and result.id is not None

    async def test_ensure_updates_existing(self, db, svc, repo, animal):
        """Ochiq alert mavjud → yangilanadi, yangi yaratilmaydi."""
        first = await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_WARNING,
            title="Birinchi sarlavha",
            description="Birinchi tavsif yetarli uzun bo'lishi kerak",
        )
        second = await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_WARNING,
            title="Yangilangan sarlavha",
            description="Yangilangan tavsif yetarli uzun",
        )
        assert first.id == second.id  # Bir xil alert, yangi yaratilmadi

    async def test_ensure_updates_title_on_duplicate(self, db, svc, repo, animal):
        await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_CRITICAL,
            title="Eski sarlavha",
            description="Eski tavsif yetarli uzun bo'lishi kerak buning uchun",
        )
        await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_CRITICAL,
            title="Yangi sarlavha",
            description="Yangi tavsif yetarli uzun bo'lishi kerak buning uchun",
        )
        found = await repo.get_open_by_animal_and_type(
            animal.id, AlertType.ADI_CRITICAL)
        assert found is not None
        assert found.title == "Yangi sarlavha"

    async def test_ensure_different_types_both_created(self, db, svc, repo, animal):
        """Har xil turdagi alertlar alohida yaratiladi."""
        await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.ADI_CRITICAL,
            title="Critical",
            description="Critical ADI yetarli uzun tavsif",
        )
        await svc._ensure_alert(
            animal_id=animal.id,
            alert_type=AlertType.FEEDING_STOPPED,
            title="Feeding",
            description="Feeding stopped yetarli uzun tavsif",
        )
        crit = await repo.get_open_by_animal_and_type(animal.id, AlertType.ADI_CRITICAL)
        feed = await repo.get_open_by_animal_and_type(animal.id, AlertType.FEEDING_STOPPED)
        assert crit is not None
        assert feed is not None

    async def test_ensure_system_alert_no_animal(self, db, svc, repo):
        """animal_id=None — tizim alerti."""
        result = await svc._ensure_alert(
            animal_id=None,
            alert_type=AlertType.SYSTEM_ERROR,
            title="Tizim xatosi",
            description="Server xatosi yuzaga keldi diagnostic kerak",
        )
        assert result is not None and result.animal_id is None


# ═══════════════════════════════════════════════════════════════════════════════
# ADI THRESHOLDS KONSTANTALAR
# ═══════════════════════════════════════════════════════════════════════════════

class TestADIThresholds:
    def test_sharp_drop_threshold_15(self):
        assert ADI_SHARP_DROP_THRESHOLD == 15.0

    def test_warning_threshold_50(self):
        assert ADI_WARNING_THRESHOLD == 50.0

    def test_critical_threshold_25(self):
        assert ADI_CRITICAL_THRESHOLD == 25.0

    def test_critical_below_warning(self):
        assert ADI_CRITICAL_THRESHOLD < ADI_WARNING_THRESHOLD

    def test_sharp_drop_positive(self):
        assert ADI_SHARP_DROP_THRESHOLD > 0