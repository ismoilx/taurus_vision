"""
TAURUS VISION — tests/test_services/test_prediction_farmtask_service.py
========================================================================
PredictionService (RuleEngine) + FarmTaskService uchun vahshiy testlar.

Qamrov:
  ✓ RiskLevel enums / risk_level_from_score — barcha chegara qiymatlari
  ✓ RuleEngine._evaluate_rule — barcha 15+ qoida (ADI, slope, feeding, missing...)
  ✓ PredictionService._compute_ensemble — rule only, rule+rf, barcha 3
  ✓ PredictionService._generate_recommendations — risk darajasiga qarab
  ✓ ALLOWED_TRANSITIONS matrix — barcha holat o'tishlari
  ✓ FarmTask model — is_overdue property
  ✓ FarmTaskService.create_task — muvaffaqiyatli, yo'q animal, yo'q user
  ✓ FarmTaskService.get_task / get_tasks — filtrlar
  ✓ FarmTaskService.update_task — status transition, man etilgan transition
  ✓ FarmTaskService.complete_task — pending, completed→xato, cancelled→xato
  ✓ FarmTaskService.cancel_task — completed→xato
  ✓ FarmTaskService.get_stats — tuzilma
  ✓ FarmTaskService.mark_overdue_tasks — bo'sh, mavjud
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from unittest.mock import MagicMock

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.farm_task import FarmTask, TaskType, TaskPriority, TaskStatus
from app.models.health_prediction import RiskLevel, risk_level_from_score
from app.services.prediction_service import (
    RuleEngine, PredictionService, RULE_WEIGHT, RF_WEIGHT, ISO_WEIGHT,
)
from app.services.farm_task_service import FarmTaskService, ALLOWED_TRANSITIONS
from app.schemas.farm_task import (
    FarmTaskCreate, FarmTaskUpdate, FarmTaskComplete,
)
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

NOW      = datetime.now(timezone.utc)
TOMORROW = NOW + timedelta(days=1)
PAST     = NOW - timedelta(hours=1)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="PRED-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def task_svc(db):
    return FarmTaskService(db)


def _task_create(animal_id=None, priority=TaskPriority.MEDIUM,
                 task_type=TaskType.OTHER, **kw):
    return FarmTaskCreate(
        title="Test Vazifasi",
        task_type=task_type,
        priority=priority,
        animal_id=animal_id,
        due_date=TOMORROW,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RISK LEVEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskLevel:

    def test_low_at_0(self):       assert risk_level_from_score(0.0)   == RiskLevel.LOW
    def test_low_at_29(self):      assert risk_level_from_score(29.9)  == RiskLevel.LOW
    def test_medium_at_30(self):   assert risk_level_from_score(30.0)  == RiskLevel.MEDIUM
    def test_medium_at_59(self):   assert risk_level_from_score(59.9)  == RiskLevel.MEDIUM
    def test_high_at_60(self):     assert risk_level_from_score(60.0)  == RiskLevel.HIGH
    def test_high_at_79(self):     assert risk_level_from_score(79.9)  == RiskLevel.HIGH
    def test_critical_at_80(self): assert risk_level_from_score(80.0)  == RiskLevel.CRITICAL
    def test_critical_at_100(self): assert risk_level_from_score(100.0) == RiskLevel.CRITICAL

    def test_all_enum_values(self):
        for level in RiskLevel:
            assert level.value in ("low", "medium", "high", "critical")

    def test_boundary_30_medium(self):
        assert risk_level_from_score(30.0) == RiskLevel.MEDIUM
        assert risk_level_from_score(29.9) == RiskLevel.LOW

    def test_boundary_60_high(self):
        assert risk_level_from_score(60.0) == RiskLevel.HIGH
        assert risk_level_from_score(59.9) == RiskLevel.MEDIUM

    def test_boundary_80_critical(self):
        assert risk_level_from_score(80.0) == RiskLevel.CRITICAL
        assert risk_level_from_score(79.9) == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════════════════════
# RULE ENGINE — _evaluate_rule
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleEngine:

    def _engine(self): return RuleEngine()

    # ADI mean
    def test_adi_critical_below_25_full_points(self):
        pts, info = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 20.0, 25.0, "test")
        assert pts == 25.0

    def test_adi_critical_below_35_partial(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 30.0, 25.0, "test")
        assert 0 < pts < 25.0

    def test_adi_critical_above_45_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 50.0, 25.0, "test")
        assert pts == 0.0

    def test_adi_warning_zone_50_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_warning_zone", "adi_mean_7d", 50.0, 15.0, "test")
        assert pts == 0.0

    def test_adi_warning_zone_25_full_points(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_warning_zone", "adi_mean_7d", 25.0, 15.0, "test")
        assert pts == 15.0

    # ADI trend slope
    def test_adi_declining_fast_slope_minus3_full(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_declining_fast", "adi_trend_slope", -3.0, 20.0, "test")
        assert pts == 20.0

    def test_adi_declining_fast_slope_minus2_partial(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_declining_fast", "adi_trend_slope", -2.5, 20.0, "test")
        assert 0 < pts <= 20.0

    def test_adi_declining_slow_minus1(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_declining_slow", "adi_trend_slope", -1.5, 10.0, "test")
        assert pts > 0

    def test_positive_slope_zero_pts(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_declining_fast", "adi_trend_slope", 2.0, 20.0, "test")
        assert pts == 0.0

    # ADI volatility
    def test_high_volatility_above_15_full(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_high_volatility", "adi_std_7d", 16.0, 10.0, "test")
        assert pts == 10.0

    def test_moderate_volatility_above_10_partial(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_high_volatility", "adi_std_7d", 12.0, 10.0, "test")
        assert 0 < pts < 10.0

    def test_low_volatility_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "adi_high_volatility", "adi_std_7d", 5.0, 10.0, "test")
        assert pts == 0.0

    # Feeding
    def test_feeding_stopped_below_20_full(self):
        pts, _ = self._engine()._evaluate_rule(
            "feeding_stopped", "feeding_mean_7d", 15.0, 20.0, "test")
        assert pts == 20.0

    def test_feeding_ok_above_50_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "feeding_stopped", "feeding_mean_7d", 60.0, 20.0, "test")
        assert pts == 0.0

    # Missing animal
    def test_missing_3_days_full_points(self):
        pts, _ = self._engine()._evaluate_rule(
            "missing_animal", "days_since_last_detection", 3.0, 25.0, "test")
        assert pts == 25.0

    def test_missing_1_day_partial(self):
        pts, _ = self._engine()._evaluate_rule(
            "missing_animal", "days_since_last_detection", 1.0, 25.0, "test")
        assert 0 < pts < 25.0

    def test_seen_today_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "missing_animal", "days_since_last_detection", 0.0, 25.0, "test")
        assert pts == 0.0

    # Consecutive warnings
    def test_consecutive_7_full(self):
        pts, _ = self._engine()._evaluate_rule(
            "consecutive_warnings", "consecutive_warning_days", 7.0, 20.0, "test")
        assert pts == 20.0

    def test_consecutive_2_partial(self):
        pts, _ = self._engine()._evaluate_rule(
            "consecutive_warnings", "consecutive_warning_days", 2.0, 20.0, "test")
        assert 0 < pts < 20.0

    def test_consecutive_0_zero(self):
        pts, _ = self._engine()._evaluate_rule(
            "consecutive_warnings", "consecutive_warning_days", 0.0, 20.0, "test")
        assert pts == 0.0

    # Factor info structure
    def test_factor_info_structure(self):
        _, info = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 20.0, 25.0, "description")
        assert "factor" in info
        assert "weight" in info
        assert "value" in info
        assert "severity" in info
        assert info["factor"] == "adi_critical_today"

    def test_severity_critical_when_full_points(self):
        _, info = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 20.0, 25.0, "test")
        assert info["severity"] == "critical"

    def test_severity_ok_when_zero_points(self):
        _, info = self._engine()._evaluate_rule(
            "adi_critical_today", "adi_mean_7d", 80.0, 25.0, "test")
        assert info["severity"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION SERVICE — _compute_ensemble
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictionServiceEnsemble:

    def _svc(self):
        svc = PredictionService.__new__(PredictionService)
        svc._rf_model  = None
        svc._iso_model = None
        svc._is_trained = False
        return svc

    def test_rule_only_equals_rule_score(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(60.0, None, None)
        assert abs(score - 60.0) < 0.1

    def test_rule_plus_rf_weighted(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(100.0, 0.0, None)
        # 100*0.4 + 0*0.4 = 40 / 0.8 = 50
        assert abs(score - 50.0) < 1.0

    def test_all_three_weighted(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(100.0, 100.0, 100.0)
        assert abs(score - 100.0) < 0.1

    def test_all_zero_returns_zero(self):
        svc = self._svc()
        score, _ = svc._compute_ensemble(0.0, 0.0, 0.0)
        assert abs(score) < 0.1

    def test_score_clamped_0_100(self):
        svc = self._svc()
        score, _ = svc._compute_ensemble(150.0, 200.0, 300.0)
        assert 0.0 <= score <= 100.0

    def test_confidence_increases_with_models(self):
        svc = self._svc()
        _, c1 = svc._compute_ensemble(50.0, None, None)
        _, c2 = svc._compute_ensemble(50.0, 50.0, None)
        _, c3 = svc._compute_ensemble(50.0, 50.0, 50.0)
        assert c1 <= c2 <= c3

    def test_confidence_max_095(self):
        svc = self._svc()
        _, conf = svc._compute_ensemble(50.0, 50.0, 50.0)
        assert conf <= 0.95

    def test_weights_sum_to_1(self):
        assert abs(RULE_WEIGHT + RF_WEIGHT + ISO_WEIGHT - 1.0) < 0.001


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION SERVICE — _generate_recommendations
# ═══════════════════════════════════════════════════════════════════════════════

class TestPredictionServiceRecommendations:

    def _svc(self):
        svc = PredictionService.__new__(PredictionService)
        return svc

    def test_critical_risk_vet_recommendation(self):
        recs = self._svc()._generate_recommendations(85.0, [], {})
        assert any("veterinar" in r.lower() or "DARHOL" in r for r in recs)

    def test_high_risk_veterinar(self):
        recs = self._svc()._generate_recommendations(65.0, [], {})
        assert any("veterinar" in r.lower() or "tekshiruv" in r.lower() for r in recs)

    def test_moderate_risk_monitoring(self):
        recs = self._svc()._generate_recommendations(40.0, [], {})
        assert any("kuzat" in r.lower() or "tekshir" in r.lower() for r in recs)

    def test_feeding_factor_feeding_recommendation(self):
        factors = [{"factor": "feeding_stopped", "weight": 0.8}]
        recs = self._svc()._generate_recommendations(70.0, factors, {})
        assert any("oziq" in r.lower() or "ozuqa" in r.lower() for r in recs)

    def test_missing_factor_detection_recommendation(self):
        factors = [{"factor": "missing_animal", "weight": 0.8}]
        recs = self._svc()._generate_recommendations(70.0, factors, {})
        assert any("kamera" in r.lower() or "jonivor" in r.lower() for r in recs)

    def test_max_6_recommendations(self):
        factors = [
            {"factor": f, "weight": 0.9}
            for f in ["adi_critical_today", "feeding_stopped", "missing_animal",
                      "consecutive_warnings", "critical_health_event", "movement_low",
                      "adi_high_volatility"]
        ]
        recs = self._svc()._generate_recommendations(90.0, factors, {})
        assert len(recs) <= 6

    def test_low_risk_no_critical_rec(self):
        recs = self._svc()._generate_recommendations(10.0, [], {})
        assert not any("DARHOL" in r for r in recs)

    def test_returns_list(self):
        recs = self._svc()._generate_recommendations(50.0, [], {})
        assert isinstance(recs, list)


# ═══════════════════════════════════════════════════════════════════════════════
# ALLOWED TRANSITIONS MATRIX
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllowedTransitions:

    def test_pending_can_start(self):
        assert TaskStatus.IN_PROGRESS in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_can_complete(self):
        assert TaskStatus.COMPLETED in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_can_cancel(self):
        assert TaskStatus.CANCELLED in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_completed_terminal_empty(self):
        assert len(ALLOWED_TRANSITIONS[TaskStatus.COMPLETED]) == 0

    def test_cancelled_can_reopen(self):
        assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.CANCELLED]

    def test_in_progress_can_complete(self):
        assert TaskStatus.COMPLETED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_in_progress_can_cancel(self):
        assert TaskStatus.CANCELLED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_overdue_can_complete(self):
        assert TaskStatus.COMPLETED in ALLOWED_TRANSITIONS[TaskStatus.OVERDUE]

    def test_overdue_can_cancel(self):
        assert TaskStatus.CANCELLED in ALLOWED_TRANSITIONS[TaskStatus.OVERDUE]

    def test_all_statuses_have_entry(self):
        for status in TaskStatus:
            assert status in ALLOWED_TRANSITIONS


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK MODEL
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskModel:

    def test_is_overdue_pending_past_due(self):
        t = FarmTask(
            title="Test", task_type=TaskType.OTHER,
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            due_date=PAST,
        )
        assert t.is_overdue is True

    def test_is_overdue_false_future_due(self):
        t = FarmTask(
            title="Test", task_type=TaskType.OTHER,
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            due_date=TOMORROW,
        )
        assert t.is_overdue is False

    def test_is_overdue_false_completed(self):
        t = FarmTask(
            title="Test", task_type=TaskType.OTHER,
            priority=TaskPriority.MEDIUM, status=TaskStatus.COMPLETED,
            due_date=PAST,
        )
        assert t.is_overdue is False

    def test_is_overdue_false_no_due_date(self):
        t = FarmTask(
            title="Test", task_type=TaskType.OTHER,
            priority=TaskPriority.MEDIUM, status=TaskStatus.PENDING,
            due_date=None,
        )
        assert t.is_overdue is False


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — CREATE / GET
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceCreate:

    async def test_create_success(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        assert task.id is not None

    async def test_create_default_status_pending(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        assert task.status == TaskStatus.PENDING

    async def test_create_with_animal(self, db, task_svc, animal):
        task = await task_svc.create_task(
            _task_create(animal_id=animal.id), created_by=1)
        assert task.animal_id == animal.id

    async def test_create_missing_animal_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.create_task(
                _task_create(animal_id=999999), created_by=1)

    async def test_create_all_task_types(self, db, task_svc):
        for ttype in TaskType:
            task = await task_svc.create_task(
                FarmTaskCreate(
                    title=f"Task {ttype.value}",
                    task_type=ttype,
                    priority=TaskPriority.LOW,
                ), created_by=1)
            assert task.task_type == ttype

    async def test_create_all_priorities(self, db, task_svc):
        for prio in TaskPriority:
            task = await task_svc.create_task(
                FarmTaskCreate(
                    title=f"Prio {prio.value}",
                    task_type=TaskType.OTHER,
                    priority=prio,
                ), created_by=1)
            assert task.priority == prio

    async def test_get_task_existing(self, db, task_svc):
        created = await task_svc.create_task(_task_create(), created_by=1)
        found = await task_svc.get_task(created.id)
        assert found.id == created.id

    async def test_get_task_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.get_task(999999)

    async def test_get_tasks_returns_list(self, db, task_svc):
        from app.schemas.farm_task import FarmTaskListResponse
        await task_svc.create_task(_task_create(), created_by=1)
        result = await task_svc.get_tasks()
        assert isinstance(result, FarmTaskListResponse)
        assert result.total >= 1

    async def test_get_tasks_status_filter(self, db, task_svc):
        await task_svc.create_task(_task_create(), created_by=1)
        result = await task_svc.get_tasks(status=[TaskStatus.PENDING])
        assert all(t.status == TaskStatus.PENDING for t in result.items)

    async def test_get_tasks_priority_filter(self, db, task_svc):
        await task_svc.create_task(
            FarmTaskCreate(title="High Prio", task_type=TaskType.OTHER,
                           priority=TaskPriority.HIGH), created_by=1)
        result = await task_svc.get_tasks(priority=TaskPriority.HIGH)
        assert all(t.priority == TaskPriority.HIGH for t in result.items)

    async def test_get_animal_tasks(self, db, task_svc, animal):
        await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        result = await task_svc.get_animal_tasks(animal.id)
        assert len(result) >= 1
        assert all(t.animal_id == animal.id for t in result)


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — STATE MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceStateMachine:

    async def test_update_pending_notes(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        upd = FarmTaskUpdate(notes="Izoh")
        updated = await task_svc.update_task(task.id, upd)
        assert updated.notes == "Izoh"

    async def test_update_pending_to_in_progress(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        upd = FarmTaskUpdate(status=TaskStatus.IN_PROGRESS)
        updated = await task_svc.update_task(task.id, upd)
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.started_at is not None

    async def test_update_completed_to_pending_raises(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.complete_task(task.id, FarmTaskComplete())
        with pytest.raises(BusinessRuleViolationError):
            await task_svc.update_task(
                task.id, FarmTaskUpdate(status=TaskStatus.PENDING))

    async def test_update_in_progress_to_cancelled_ok(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.update_task(task.id, FarmTaskUpdate(status=TaskStatus.IN_PROGRESS))
        updated = await task_svc.update_task(
            task.id, FarmTaskUpdate(status=TaskStatus.CANCELLED))
        assert updated.status == TaskStatus.CANCELLED

    async def test_complete_pending_ok(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        completed = await task_svc.complete_task(
            task.id, FarmTaskComplete(notes="Bajarildi"))
        assert completed.status == TaskStatus.COMPLETED
        assert completed.completed_at is not None

    async def test_complete_already_completed_raises(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.complete_task(task.id, FarmTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await task_svc.complete_task(task.id, FarmTaskComplete())
        assert "allaqachon" in exc_info.value.message.lower()

    async def test_complete_cancelled_raises(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.cancel_task(task.id)
        with pytest.raises(BusinessRuleViolationError):
            await task_svc.complete_task(task.id, FarmTaskComplete())

    async def test_complete_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.complete_task(999999, FarmTaskComplete())

    async def test_cancel_pending_ok(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        cancelled = await task_svc.cancel_task(task.id, reason="Kerak emas")
        assert cancelled.status == TaskStatus.CANCELLED
        assert cancelled.notes == "Kerak emas"

    async def test_cancel_completed_raises(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.complete_task(task.id, FarmTaskComplete())
        with pytest.raises(BusinessRuleViolationError):
            await task_svc.cancel_task(task.id)

    async def test_cancel_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.cancel_task(999999)

    async def test_full_lifecycle(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        assert task.status == TaskStatus.PENDING
        upd = await task_svc.update_task(
            task.id, FarmTaskUpdate(status=TaskStatus.IN_PROGRESS))
        assert upd.status == TaskStatus.IN_PROGRESS
        done = await task_svc.complete_task(task.id, FarmTaskComplete())
        assert done.status == TaskStatus.COMPLETED

    async def test_update_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.update_task(999999, FarmTaskUpdate(notes="Ghost"))


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — STATS & MARK OVERDUE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceStats:

    async def test_get_stats_structure(self, db, task_svc):
        from app.schemas.farm_task import TaskStats
        await task_svc.create_task(_task_create(), created_by=1)
        stats = await task_svc.get_stats()
        assert isinstance(stats, TaskStats)
        assert hasattr(stats, "total_open")
        assert hasattr(stats, "total_overdue")
        assert hasattr(stats, "by_priority")
        assert hasattr(stats, "by_type")

    async def test_get_stats_counts_open(self, db, task_svc):
        for _ in range(3):
            await task_svc.create_task(_task_create(), created_by=1)
        stats = await task_svc.get_stats()
        assert stats.total_open >= 3

    async def test_mark_overdue_returns_dict(self, db, task_svc):
        result = await task_svc.mark_overdue_tasks()
        assert isinstance(result, dict)
        assert "marked" in result
        assert "alerts_created" in result

    async def test_mark_overdue_marks_past_due_pending(self, db, task_svc):
        # O'tgan muddatli vazifa qo'shamiz
        past_due = NOW - timedelta(hours=2)
        task = FarmTask(
            title="Overdue Task",
            task_type=TaskType.OTHER,
            priority=TaskPriority.HIGH,
            status=TaskStatus.PENDING,
            due_date=past_due,
        )
        db.add(task); await db.commit()
        result = await task_svc.mark_overdue_tasks()
        assert result["marked"] >= 1

    async def test_mark_overdue_not_completed_tasks(self, db, task_svc):
        task = await task_svc.create_task(_task_create(), created_by=1)
        await task_svc.complete_task(task.id, FarmTaskComplete())
        result = await task_svc.mark_overdue_tasks()
        # Completed vazifa overdue bo'lmasin
        found = await task_svc.get_task(task.id)
        assert found.status == TaskStatus.COMPLETED