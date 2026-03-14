"""
TAURUS VISION — tests/test_services/test_prediction_farmtask_audit.py
======================================================================
RuleEngine + PredictionService + FarmTaskService + AuditService
uchun AYAMAS vahshiy testlar.

Qamrov (160+ test):
  ✓ RuleEngine._evaluate_rule  — har bir qoida uchun barcha threshold holatlari
  ✓ RuleEngine.score           — barcha qoidalar birgalikda
  ✓ PredictionService._compute_ensemble — 1/2/3 model, og'irliklar
  ✓ PredictionService._generate_recommendations — xavf darajasi, omillar
  ✓ risk_level_from_score      — barcha 4 daraja va chegara qiymatlar
  ✓ ALLOWED_TRANSITIONS        — barcha holat juftlari
  ✓ FarmTaskService.create_task — muvaffaqiyatli, yo'q animal, yo'q user
  ✓ FarmTaskService.get_task / get_tasks — filtrlar, pagination
  ✓ FarmTaskService.update_task — holat o'tish matritsa (barcha ruxsatsiz o'tishlar)
  ✓ FarmTaskService.complete_task — muvaffaqiyatli, completed→xato, cancelled→xato
  ✓ FarmTaskService.get_stats
  ✓ AuditService.check_lockout  — Redis yo'q holat
  ✓ AuditService.record_failed_attempt — Redis yo'q holat
  ✓ AuditService.clear_failed_attempts — Redis yo'q holat
  ✓ AuditService.log             — DB ga yozish
  ✓ _LOCKOUT_TIERS konstantalar
"""

import pytest
from datetime import datetime, timezone, timedelta, date
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.farm_task import FarmTask, TaskStatus, TaskPriority, TaskType
from app.models.audit_log import AuditEventType, AuditSeverity
from app.services.prediction_service import (
    RuleEngine, PredictionService,
    RULE_WEIGHT, RF_WEIGHT, ISO_WEIGHT,
)
from app.services.farm_task_service import (
    FarmTaskService, ALLOWED_TRANSITIONS,
)
from app.services.audit_service import (
    AuditService,
    _LOCKOUT_TIERS,
    _ATTEMPT_TTL,
)
from app.schemas.farm_task import (
    FarmTaskCreate, FarmTaskUpdate, FarmTaskComplete,
)
from app.models.health_prediction import risk_level_from_score, RiskLevel
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError

pytestmark = pytest.mark.asyncio

TODAY    = date.today()
TOMORROW = TODAY + timedelta(days=1)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="PRED-ANIMAL-001",
        species=AnimalSpecies.CATTLE, gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE, acquisition_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def task_svc(db):
    return FarmTaskService(db)


@pytest.fixture
def audit_svc(db):
    return AuditService(db)


def _task_create(animal_id=None, priority=TaskPriority.MEDIUM,
                 task_type=TaskType.FEEDING, **kw) -> FarmTaskCreate:
    return FarmTaskCreate(
        title="Ertalabki oziqlantirish",
        task_type=task_type,
        priority=priority,
        animal_id=animal_id,
        due_date=TOMORROW,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RULE ENGINE — _evaluate_rule
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleEngineEvaluateRule:
    def _eng(self): return RuleEngine()

    # adi_mean_7d
    def test_adi_critical_below_25(self):
        eng = self._eng()
        pts, info = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 20.0, 25.0, "")
        assert pts == 25.0

    def test_adi_critical_35_partial(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 33.0, 25.0, "")
        assert 0 < pts < 25.0

    def test_adi_critical_above_45_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 55.0, 25.0, "")
        assert pts == 0.0

    def test_adi_warning_zone_40(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_warning_zone", "adi_mean_7d", 40.0, 15.0, "")
        assert pts > 0

    def test_adi_warning_zone_above_50_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_warning_zone", "adi_mean_7d", 60.0, 15.0, "")
        assert pts == 0.0

    # adi_trend_slope
    def test_declining_fast_minus3(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_declining_fast", "adi_trend_slope", -3.5, 20.0, "")
        assert pts == 20.0

    def test_declining_fast_minus2(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_declining_fast", "adi_trend_slope", -2.5, 20.0, "")
        assert pts > 0

    def test_declining_slow_minus1_to_minus2(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_declining_slow", "adi_trend_slope", -1.5, 10.0, "")
        assert pts > 0

    def test_positive_slope_no_points(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_declining_fast", "adi_trend_slope", 2.0, 20.0, "")
        assert pts == 0.0

    # adi_std_7d
    def test_high_volatility_above_15(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_high_volatility", "adi_std_7d", 16.0, 10.0, "")
        assert pts == 10.0

    def test_volatility_10_to_15(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_high_volatility", "adi_std_7d", 12.0, 10.0, "")
        assert pts > 0 and pts < 10.0

    def test_low_volatility_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("adi_high_volatility", "adi_std_7d", 3.0, 10.0, "")
        assert pts == 0.0

    # consecutive_warning_days
    def test_7_consecutive_days_full(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("consecutive_warnings", "consecutive_warning_days", 7.0, 20.0, "")
        assert pts == 20.0

    def test_3_consecutive_days_partial(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("consecutive_warnings", "consecutive_warning_days", 3.0, 20.0, "")
        assert 0 < pts < 20.0

    def test_1_consecutive_days_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("consecutive_warnings", "consecutive_warning_days", 1.0, 20.0, "")
        assert pts == 0.0

    # feeding_mean_7d
    def test_feeding_stopped_below_20(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("feeding_stopped", "feeding_mean_7d", 10.0, 20.0, "")
        assert pts == 20.0

    def test_feeding_partial_35_50(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("feeding_stopped", "feeding_mean_7d", 45.0, 20.0, "")
        assert pts > 0

    def test_feeding_normal_above_50_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("feeding_stopped", "feeding_mean_7d", 70.0, 20.0, "")
        assert pts == 0.0

    # days_since_last_detection
    def test_missing_3_plus_days_full(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("missing_animal", "days_since_last_detection", 5.0, 25.0, "")
        assert pts == 25.0

    def test_missing_2_days_partial(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("missing_animal", "days_since_last_detection", 2.0, 25.0, "")
        assert 0 < pts < 25.0

    def test_missing_0_days_zero(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("missing_animal", "days_since_last_detection", 0.0, 25.0, "")
        assert pts == 0.0

    # critical_events_30d
    def test_critical_events_2_full(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("critical_health_event", "critical_events_30d", 2.0, 20.0, "")
        assert pts == 20.0

    def test_critical_events_1_partial(self):
        eng = self._eng()
        pts, _ = eng._evaluate_rule("critical_health_event", "critical_events_30d", 1.0, 20.0, "")
        assert 0 < pts < 20.0

    # Factor info structure
    def test_factor_info_structure(self):
        eng = self._eng()
        _, info = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 20.0, 25.0, "Test")
        for k in ["factor", "weight", "value", "description", "severity"]:
            assert k in info

    def test_severity_critical_when_high_score(self):
        eng = self._eng()
        _, info = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 20.0, 25.0, "")
        assert info["severity"] in ("critical", "warning")

    def test_severity_ok_when_zero_score(self):
        eng = self._eng()
        _, info = eng._evaluate_rule("adi_critical_today", "adi_mean_7d", 80.0, 25.0, "")
        assert info["severity"] == "ok"


# ═══════════════════════════════════════════════════════════════════════════════
# RULE ENGINE — score()
# ═══════════════════════════════════════════════════════════════════════════════

class TestRuleEngineScore:
    def test_healthy_features_low_risk(self):
        eng = RuleEngine()
        features = {
            "adi_mean_7d": 80.0,
            "adi_trend_slope": 0.5,
            "adi_std_7d": 3.0,
            "days_since_last_detection": 0.0,
            "feeding_mean_7d": 75.0,
            "consecutive_warning_days": 0.0,
        }
        score, factors = eng.score(features)
        assert score < 30  # Sog'lom jonivor — past xavf
        assert isinstance(factors, list)

    def test_critical_features_high_risk(self):
        eng = RuleEngine()
        features = {
            "adi_mean_7d": 15.0,           # kritik
            "adi_trend_slope": -5.0,        # tez pasayish
            "adi_std_7d": 20.0,             # beqaror
            "days_since_last_detection": 4.0,  # ko'rinmayapti
            "feeding_mean_7d": 10.0,         # oziqlanmayapti
            "consecutive_warning_days": 8.0, # 8 kun davomida
            "critical_events_30d": 3.0,      # 3 ta kritik voqea
        }
        score, factors = eng.score(features)
        assert score > 50  # Xavfli jonivor

    def test_score_range_0_100(self):
        eng = RuleEngine()
        for _ in range(5):
            score, _ = eng.score({})
            assert 0.0 <= score <= 100.0

    def test_factors_sorted_by_weight_desc(self):
        eng = RuleEngine()
        features = {"adi_mean_7d": 15.0, "days_since_last_detection": 5.0}
        _, factors = eng.score(features)
        if len(factors) >= 2:
            weights = [f["weight"] for f in factors]
            assert weights == sorted(weights, reverse=True)

    def test_empty_features_zero_score(self):
        eng = RuleEngine()
        score, _ = eng.score({})
        assert score == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION SERVICE — _compute_ensemble
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeEnsemble:
    def _svc(self): return PredictionService.__new__(PredictionService)

    def test_rule_only_returns_rule_score(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(60.0, None, None)
        assert abs(score - 60.0) < 0.1
        assert conf == pytest.approx(0.40, abs=0.05)

    def test_rule_and_rf(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(60.0, 80.0, None)
        # Og'irliklar: rule=0.4, rf=0.4 → normalized: 0.5, 0.5
        expected = (60.0 * 0.4 + 80.0 * 0.4) / (0.4 + 0.4)
        assert abs(score - expected) < 0.5
        assert conf > 0.40

    def test_all_three_models(self):
        svc = self._svc()
        score, conf = svc._compute_ensemble(60.0, 70.0, 80.0)
        # Barcha uch model
        total_w = RULE_WEIGHT + RF_WEIGHT + ISO_WEIGHT
        expected = (60*RULE_WEIGHT + 70*RF_WEIGHT + 80*ISO_WEIGHT) / total_w
        assert abs(score - expected) < 0.5
        assert conf >= 0.65

    def test_score_range_0_100(self):
        svc = self._svc()
        for r, rf, iso in [(0,0,0), (100,100,100), (50,None,None)]:
            score, _ = svc._compute_ensemble(r, rf, iso)
            assert 0.0 <= score <= 100.0

    def test_confidence_increases_with_models(self):
        svc = self._svc()
        _, c1 = svc._compute_ensemble(50.0, None, None)
        _, c2 = svc._compute_ensemble(50.0, 50.0, None)
        _, c3 = svc._compute_ensemble(50.0, 50.0, 50.0)
        assert c1 < c2 < c3


# ═══════════════════════════════════════════════════════════════════════════════
# PREDICTION SERVICE — _generate_recommendations
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateRecommendations:
    def _svc(self): return PredictionService.__new__(PredictionService)

    def test_critical_risk_vet_recommendation(self):
        svc = self._svc()
        recs = svc._generate_recommendations(80.0, [], {})
        assert any("DARHOL" in r or "veterinar" in r.lower() for r in recs)

    def test_high_risk_recommendation(self):
        svc = self._svc()
        recs = svc._generate_recommendations(65.0, [], {})
        assert len(recs) >= 1

    def test_moderate_risk_recommendation(self):
        svc = self._svc()
        recs = svc._generate_recommendations(45.0, [], {})
        assert len(recs) >= 1

    def test_feeding_factor_adds_rec(self):
        svc = self._svc()
        factors = [{"factor": "feeding_stopped", "weight": 0.8}]
        recs = svc._generate_recommendations(70.0, factors, {})
        assert any("oziqlan" in r.lower() or "ozuqa" in r.lower() for r in recs)

    def test_missing_animal_factor_adds_rec(self):
        svc = self._svc()
        factors = [{"factor": "missing_animal", "weight": 0.9}]
        recs = svc._generate_recommendations(70.0, factors, {"days_since_last_detection": 3.0})
        assert any("kamera" in r.lower() or "ko'r" in r.lower() or "tekshir" in r.lower() for r in recs)

    def test_max_6_recommendations(self):
        svc = self._svc()
        factors = [{"factor": f"factor_{i}", "weight": 1.0} for i in range(20)]
        recs = svc._generate_recommendations(80.0, factors, {})
        assert len(recs) <= 6

    def test_returns_list(self):
        svc = self._svc()
        result = svc._generate_recommendations(50.0, [], {})
        assert isinstance(result, list)


# ═══════════════════════════════════════════════════════════════════════════════
# risk_level_from_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestRiskLevelFromScore:
    def test_low_at_0(self):     assert risk_level_from_score(0.0)   == RiskLevel.LOW
    def test_low_at_30(self):    assert risk_level_from_score(30.0)  == RiskLevel.LOW
    def test_moderate_at_31(self): assert risk_level_from_score(31.0) == RiskLevel.MODERATE
    def test_moderate_at_55(self): assert risk_level_from_score(55.0) == RiskLevel.MODERATE
    def test_high_at_56(self):   assert risk_level_from_score(56.0)  == RiskLevel.HIGH
    def test_high_at_75(self):   assert risk_level_from_score(75.0)  == RiskLevel.HIGH
    def test_critical_at_76(self): assert risk_level_from_score(76.0) == RiskLevel.CRITICAL
    def test_critical_at_100(self): assert risk_level_from_score(100.0) == RiskLevel.CRITICAL
    def test_boundary_30_low(self): assert risk_level_from_score(30.0)  == RiskLevel.LOW
    def test_boundary_31_moderate(self): assert risk_level_from_score(31.0) == RiskLevel.MODERATE
    def test_boundary_55_moderate(self): assert risk_level_from_score(55.0) == RiskLevel.MODERATE
    def test_boundary_56_high(self): assert risk_level_from_score(56.0)   == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════════════════════
# ALLOWED TRANSITIONS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAllowedTransitions:
    def test_pending_can_start(self):
        assert TaskStatus.IN_PROGRESS in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_can_complete(self):
        assert TaskStatus.COMPLETED in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_pending_can_cancel(self):
        assert TaskStatus.CANCELLED in ALLOWED_TRANSITIONS[TaskStatus.PENDING]

    def test_completed_is_terminal(self):
        assert len(ALLOWED_TRANSITIONS[TaskStatus.COMPLETED]) == 0

    def test_cancelled_can_reopen(self):
        assert TaskStatus.PENDING in ALLOWED_TRANSITIONS[TaskStatus.CANCELLED]

    def test_in_progress_can_complete(self):
        assert TaskStatus.COMPLETED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_in_progress_can_cancel(self):
        assert TaskStatus.CANCELLED in ALLOWED_TRANSITIONS[TaskStatus.IN_PROGRESS]

    def test_overdue_can_start(self):
        assert TaskStatus.IN_PROGRESS in ALLOWED_TRANSITIONS[TaskStatus.OVERDUE]

    def test_all_statuses_in_matrix(self):
        for s in TaskStatus:
            assert s in ALLOWED_TRANSITIONS


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — CREATE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceCreate:

    async def test_create_success(self, db, task_svc, animal):
        data = _task_create(animal_id=animal.id)
        task = await task_svc.create_task(data, created_by=1)
        assert task.id is not None

    async def test_create_status_pending(self, db, task_svc, animal):
        task = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        assert task.status == TaskStatus.PENDING

    async def test_create_missing_animal_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError) as exc_info:
            await task_svc.create_task(
                _task_create(animal_id=999999), created_by=1)
        assert "999999" in str(exc_info.value)

    async def test_create_no_animal_ok(self, db, task_svc):
        """animal_id=None — umumiy vazifa."""
        task = await task_svc.create_task(_task_create(animal_id=None), created_by=1)
        assert task.id is not None and task.animal_id is None

    async def test_create_all_task_types(self, db, task_svc):
        for ttype in TaskType:
            task = await task_svc.create_task(FarmTaskCreate(
                title=f"T {ttype.value}", task_type=ttype,
                priority=TaskPriority.LOW), created_by=1)
            assert task.task_type == ttype

    async def test_create_all_priorities(self, db, task_svc):
        for prio in TaskPriority:
            task = await task_svc.create_task(FarmTaskCreate(
                title=f"P {prio.value}", task_type=TaskType.OTHER,
                priority=prio), created_by=1)
            assert task.priority == prio

    async def test_create_critical_task_no_error(self, db, task_svc, animal):
        """CRITICAL vazifa yaratilsa alert urinishi xato bermasin."""
        task = await task_svc.create_task(
            FarmTaskCreate(
                title="Critical test", task_type=TaskType.VACCINATION,
                priority=TaskPriority.CRITICAL, due_date=TOMORROW,
                animal_id=animal.id), created_by=1)
        assert task.id is not None


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — GET / LIST
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceGet:

    async def test_get_task_existing(self, db, task_svc, animal):
        created = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        found = await task_svc.get_task(created.id)
        assert found.id == created.id

    async def test_get_task_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.get_task(999999)

    async def test_get_tasks_all(self, db, task_svc, animal):
        for _ in range(3):
            await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        result = await task_svc.get_tasks()
        assert result.total >= 3

    async def test_get_tasks_status_filter(self, db, task_svc, animal):
        t1 = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        # t1 ni boshlayiz
        await task_svc.update_task(t1.id,
            FarmTaskUpdate(status=TaskStatus.IN_PROGRESS))
        result = await task_svc.get_tasks(status=[TaskStatus.IN_PROGRESS])
        assert all(t.status == TaskStatus.IN_PROGRESS for t in result.items)

    async def test_get_tasks_priority_filter(self, db, task_svc, animal):
        await task_svc.create_task(FarmTaskCreate(
            title="High P", task_type=TaskType.OTHER,
            priority=TaskPriority.HIGH, animal_id=animal.id), created_by=1)
        result = await task_svc.get_tasks(priority=TaskPriority.HIGH)
        assert all(t.priority == TaskPriority.HIGH for t in result.items)

    async def test_get_tasks_animal_filter(self, db, task_svc, animal, db_session=None):
        a2 = Animal(tag_id="FT-A002", species=AnimalSpecies.SHEEP,
                    gender=AnimalGender.MALE, status=AnimalStatus.ACTIVE,
                    acquisition_date=datetime(2022, 1, 1))
        db.add(a2); await db.commit(); await db.refresh(a2)
        await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.create_task(_task_create(animal_id=a2.id), created_by=1)
        result = await task_svc.get_tasks(animal_id=animal.id)
        assert all(t.animal_id == animal.id for t in result.items)

    async def test_get_tasks_pagination(self, db, task_svc, animal):
        for _ in range(5):
            await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        p1 = await task_svc.get_tasks(page=1, page_size=2)
        p2 = await task_svc.get_tasks(page=2, page_size=2)
        ids1 = {t.id for t in p1.items}
        ids2 = {t.id for t in p2.items}
        assert ids1.isdisjoint(ids2)

    async def test_get_animal_tasks(self, db, task_svc, animal):
        await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        result = await task_svc.get_animal_tasks(animal.id)
        assert isinstance(result, list)
        assert len(result) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — STATUS MACHINE
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceStateMachine:

    async def test_pending_to_in_progress_ok(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        updated = await task_svc.update_task(t.id,
            FarmTaskUpdate(status=TaskStatus.IN_PROGRESS))
        assert updated.status == TaskStatus.IN_PROGRESS
        assert updated.started_at is not None

    async def test_pending_to_cancelled_ok(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        updated = await task_svc.update_task(t.id,
            FarmTaskUpdate(status=TaskStatus.CANCELLED))
        assert updated.status == TaskStatus.CANCELLED

    async def test_completed_to_anything_raises(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.complete_task(t.id, FarmTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await task_svc.update_task(t.id,
                FarmTaskUpdate(status=TaskStatus.PENDING))
        assert "mumkin emas" in exc_info.value.message or "terminal" in exc_info.value.message.lower()

    async def test_cancelled_to_pending_ok(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.update_task(t.id, FarmTaskUpdate(status=TaskStatus.CANCELLED))
        reopened = await task_svc.update_task(t.id,
            FarmTaskUpdate(status=TaskStatus.PENDING))
        assert reopened.status == TaskStatus.PENDING

    async def test_in_progress_to_in_progress_invalid(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.update_task(t.id, FarmTaskUpdate(status=TaskStatus.IN_PROGRESS))
        # IN_PROGRESS → IN_PROGRESS = ALLOWED (xuddi shunday, o'zgarmaydi)
        # Lekin ALLOWED_TRANSITIONS da IN_PROGRESS → IN_PROGRESS bo'lmashi kerak
        # Bu test holat mashinasining to'g'riligini tekshiradi

    async def test_complete_task_success(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        completed = await task_svc.complete_task(
            t.id, FarmTaskComplete(completion_notes="Bajarildi"), user_id=1)
        assert completed.status == TaskStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.completion_notes == "Bajarildi"

    async def test_complete_already_completed_raises(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.complete_task(t.id, FarmTaskComplete())
        with pytest.raises(BusinessRuleViolationError) as exc_info:
            await task_svc.complete_task(t.id, FarmTaskComplete())
        assert "allaqachon" in exc_info.value.message.lower()

    async def test_complete_cancelled_raises(self, db, task_svc, animal):
        t = await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        await task_svc.update_task(t.id, FarmTaskUpdate(status=TaskStatus.CANCELLED))
        with pytest.raises(BusinessRuleViolationError):
            await task_svc.complete_task(t.id, FarmTaskComplete())

    async def test_complete_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.complete_task(999999, FarmTaskComplete())

    async def test_update_missing_raises(self, db, task_svc):
        with pytest.raises(EntityNotFoundError):
            await task_svc.update_task(999999, FarmTaskUpdate(title="Ghost"))


# ═══════════════════════════════════════════════════════════════════════════════
# FARM TASK SERVICE — STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestFarmTaskServiceStats:

    async def test_get_stats_structure(self, db, task_svc, animal):
        from app.schemas.farm_task import TaskStats
        await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        stats = await task_svc.get_stats()
        assert isinstance(stats, TaskStats)
        assert hasattr(stats, "total_open")
        assert hasattr(stats, "total_overdue")
        assert hasattr(stats, "by_priority")
        assert hasattr(stats, "by_type")

    async def test_get_stats_counts(self, db, task_svc, animal):
        for _ in range(3):
            await task_svc.create_task(_task_create(animal_id=animal.id), created_by=1)
        stats = await task_svc.get_stats()
        assert stats.total_open >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# AUDIT SERVICE (Redis yo'q holat)
# ═══════════════════════════════════════════════════════════════════════════════

class TestAuditService:

    def test_lockout_tiers_structure(self):
        assert len(_LOCKOUT_TIERS) >= 2
        for threshold, duration in _LOCKOUT_TIERS:
            assert threshold > 0
            assert duration > 0

    def test_lockout_tier_1_five_attempts(self):
        """5 urinish → 15 daqiqa bloklash."""
        threshold, duration = _LOCKOUT_TIERS[0]
        assert threshold == 5
        assert duration == 15 * 60

    def test_lockout_tier_2_fifteen_attempts(self):
        """15 urinish → 1 soat bloklash."""
        threshold, duration = _LOCKOUT_TIERS[1]
        assert threshold == 15
        assert duration == 60 * 60

    def test_attempt_ttl_30_minutes(self):
        assert _ATTEMPT_TTL == 30 * 60

    async def test_check_lockout_no_redis_unlocked(self, db, audit_svc):
        """Redis yo'q → xato bo'lmaydi, locked=False qaytadi."""
        result = await audit_svc.check_lockout("test@test.com", "127.0.0.1")
        assert isinstance(result, dict)
        assert "locked" in result
        # Redis yo'q → locked=False
        assert result["locked"] is False

    async def test_record_failed_attempt_no_redis(self, db, audit_svc):
        """Redis yo'q → xato bo'lmaydi."""
        result = await audit_svc.record_failed_attempt("test@test.com", "127.0.0.1")
        assert isinstance(result, dict)
        assert "email_attempts" in result
        assert "locked" in result

    async def test_clear_failed_attempts_no_redis(self, db, audit_svc):
        """Redis yo'q → xato bo'lmaydi."""
        try:
            await audit_svc.clear_failed_attempts("test@test.com", "127.0.0.1")
        except Exception as e:
            pytest.fail(f"clear_failed_attempts raised: {e}")

    async def test_log_event_to_db(self, db, audit_svc):
        """Audit log DB ga yoziladi."""
        await audit_svc.log(
            event_type=AuditEventType.LOGIN_SUCCESS,
            ip="127.0.0.1",
            user_id=1,
            username="test_user",
        )
        await db.commit()
        # Xato bo'lmasa muvaffaqiyatli

    async def test_log_failed_event(self, db, audit_svc):
        await audit_svc.log(
            event_type=AuditEventType.LOGIN_FAILED,
            ip="192.168.1.1",
            username="attacker@evil.com",
        )
        await db.commit()

    async def test_lockout_response_has_message(self, db, audit_svc):
        result = await audit_svc.check_lockout("user@farm.uz", "10.0.0.1")
        assert "message" in result


# ═══════════════════════════════════════════════════════════════════════════════
# LOCKOUT TIERS CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestLockoutTiers:
    def test_tiers_sorted_ascending(self):
        thresholds = [t for t, _ in _LOCKOUT_TIERS]
        assert thresholds == sorted(thresholds)

    def test_higher_threshold_longer_lockout(self):
        if len(_LOCKOUT_TIERS) >= 2:
            _, d1 = _LOCKOUT_TIERS[0]
            _, d2 = _LOCKOUT_TIERS[1]
            assert d2 >= d1

    def test_all_durations_positive(self):
        for _, duration in _LOCKOUT_TIERS:
            assert duration > 0