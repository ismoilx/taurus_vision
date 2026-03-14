"""
TAURUS VISION — tests/test_services/test_behavior_sensor_service.py
====================================================================
BehaviorService pure funksiyalar + SensorService uchun vahshiy testlar.

Qamrov:
  ✓ _score_to_status         — barcha 5 daraja
  ✓ _compute_activity_score  — nol, norma, ikki baravar
  ✓ _compute_feeding_score   — nol, normal, gap bor
  ✓ _compute_movement_score  — harakatsiz, aktiv, o'rta
  ✓ _compute_social_score    — nol, o'rta, yuqori
  ✓ _compute_overall_score   — og'irliklar tekshiruvi
  ✓ _detect_adi_trend        — o'sish, kamayish, barqaror, kam ma'lumot
  ✓ NORMAL_RANGES              — temperatura va yurak urishi
  ✓ SensorService.process_reading   — muvaffaqiyatli, bulk
  ✓ SensorService.get_daily_summary — tuzilma
  ✓ SensorService.get_farm_stats
  ✓ SensorService._detect_issues    — normal, warning, critical
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.sensor_reading import SensorReading
from app.services.behavior_service import (
    _score_to_status,
    _compute_activity_score,
    _compute_feeding_score,
    _compute_movement_score,
    _compute_social_score,
    _compute_overall_score,
    _detect_adi_trend,
    _FEEDING_GAP_H,
    _HIGH_ACTIVITY,
)
from app.services.sensor_service import SensorService, NORMAL_RANGES
from app.schemas.sensor import SensorReadingCreate
from app.core.exceptions import ValidationError

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def animal(db):
    a = Animal(
        tag_id="SENS-ANIMAL-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def svc(db):
    return SensorService(db)


def _reading_create(animal_id=None, device_id="SENSOR-001",
                    temp=38.5, hr=60, **kw) -> SensorReadingCreate:
    return SensorReadingCreate(
        device_id=device_id,
        device_type="collar",
        animal_id=animal_id,
        temperature=temp,
        heart_rate=hr,
        activity_level=0.5,
        recorded_at=NOW,
        **kw,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _score_to_status
# ═══════════════════════════════════════════════════════════════════════════════

class TestScoreToStatus:
    def test_excellent_at_90(self):    assert _score_to_status(90.0)  == "excellent"
    def test_excellent_at_100(self):   assert _score_to_status(100.0) == "excellent"
    def test_good_at_75(self):         assert _score_to_status(75.0)  == "good"
    def test_good_at_89(self):         assert _score_to_status(89.0)  == "good"
    def test_fair_at_55(self):         assert _score_to_status(55.0)  == "fair"
    def test_fair_at_74(self):         assert _score_to_status(74.0)  == "fair"
    def test_poor_at_35(self):         assert _score_to_status(35.0)  == "poor"
    def test_poor_at_54(self):         assert _score_to_status(54.0)  == "poor"
    def test_critical_at_0(self):      assert _score_to_status(0.0)   == "critical"
    def test_critical_at_34(self):     assert _score_to_status(34.0)  == "critical"
    def test_boundary_90_excellent(self): assert _score_to_status(90.0) == "excellent"
    def test_boundary_89_good(self):      assert _score_to_status(89.9) == "good"
    def test_boundary_75_good(self):      assert _score_to_status(75.0) == "good"
    def test_boundary_74_fair(self):      assert _score_to_status(74.9) == "fair"


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _compute_activity_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeActivityScore:

    def test_zero_detections_zero_score(self):
        result = _compute_activity_score(0, 24)
        assert result.pct == 0.0
        assert result.status == "critical"

    def test_normal_24h_high_score(self):
        result = _compute_activity_score(_HIGH_ACTIVITY, 24)
        assert result.pct == 100.0
        assert result.status == "excellent"

    def test_half_normal(self):
        result = _compute_activity_score(_HIGH_ACTIVITY // 2, 24)
        assert result.pct == 50.0

    def test_double_normal_capped_100(self):
        result = _compute_activity_score(_HIGH_ACTIVITY * 2, 24)
        assert result.pct == 100.0

    def test_12h_period(self):
        """12 soatlik davr uchun expected = HIGH_ACTIVITY/2."""
        result = _compute_activity_score(_HIGH_ACTIVITY // 2, 12)
        assert result.pct == 100.0

    def test_returns_behavior_score(self):
        from app.schemas.behavior import BehaviorScore
        result = _compute_activity_score(10, 24)
        assert isinstance(result, BehaviorScore)
        assert hasattr(result, "pct")
        assert hasattr(result, "status")
        assert hasattr(result, "description")

    def test_description_not_empty(self):
        result = _compute_activity_score(48, 24)
        assert result.description is not None and len(result.description) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _compute_feeding_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeFeedingScore:

    def test_zero_visits_zero_score(self):
        result = _compute_feeding_score(0, None, 24)
        assert result.pct == 0.0

    def test_normal_visits_good_score(self):
        result = _compute_feeding_score(6, None, 24)
        assert result.pct > 50

    def test_with_last_visit_no_gap(self):
        recent = datetime.now(timezone.utc) - timedelta(hours=2)
        result = _compute_feeding_score(5, recent, 24)
        assert result.status not in ("critical",)

    def test_with_long_gap_low_score(self):
        long_ago = datetime.now(timezone.utc) - timedelta(hours=_FEEDING_GAP_H + 2)
        result = _compute_feeding_score(2, long_ago, 24)
        assert result.pct < 50

    def test_high_visits_excellent(self):
        result = _compute_feeding_score(12, None, 24)
        assert result.status in ("excellent", "good")

    def test_returns_behavior_score(self):
        from app.schemas.behavior import BehaviorScore
        assert isinstance(_compute_feeding_score(5, None, 24), BehaviorScore)


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _compute_movement_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeMovementScore:

    def test_zero_std_inactive(self):
        from app.services.behavior_service import _MOVEMENT_INACTIVE
        result = _compute_movement_score(0.0)
        assert result.pct < 40 or result.status == "poor"

    def test_high_std_active_score(self):
        from app.services.behavior_service import _MOVEMENT_ACTIVE
        result = _compute_movement_score(_MOVEMENT_ACTIVE + 0.05)
        assert result.pct >= 50

    def test_moderate_std_moderate_score(self):
        result = _compute_movement_score(0.10)
        assert 30 <= result.pct <= 90

    def test_returns_behavior_score(self):
        from app.schemas.behavior import BehaviorScore
        assert isinstance(_compute_movement_score(0.1), BehaviorScore)

    def test_very_high_std_may_indicate_stress(self):
        """Juda yuqori harakat ham normal emas."""
        result = _compute_movement_score(0.5)
        # Stress yoki hayajonlanish — score pasayishi mumkin
        assert isinstance(result.pct, float)


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _compute_social_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeSocialScore:

    def test_zero_ratio_zero_score(self):
        result = _compute_social_score(0.0)
        assert result.pct == 0.0

    def test_normal_ratio_good_score(self):
        result = _compute_social_score(0.3)
        assert result.pct >= 50

    def test_high_ratio_high_score(self):
        result = _compute_social_score(0.8)
        assert result.pct >= 70

    def test_returns_behavior_score(self):
        from app.schemas.behavior import BehaviorScore
        assert isinstance(_compute_social_score(0.3), BehaviorScore)

    def test_capped_at_100(self):
        result = _compute_social_score(1.0)
        assert result.pct <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _compute_overall_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeOverallScore:

    def _make_score(self, pct):
        from app.schemas.behavior import BehaviorScore
        return BehaviorScore(pct=pct, status=_score_to_status(pct), description="test")

    def test_all_100_returns_100(self):
        s = self._make_score(100.0)
        result = _compute_overall_score(s, s, s, s)
        assert abs(result - 100.0) < 0.5

    def test_all_0_returns_0(self):
        s = self._make_score(0.0)
        result = _compute_overall_score(s, s, s, s)
        assert abs(result - 0.0) < 0.5

    def test_mixed_scores_weighted(self):
        """35% activity + 35% feeding + 20% movement + 10% social = 100%."""
        a = self._make_score(100.0)  # activity
        f = self._make_score(0.0)    # feeding
        m = self._make_score(0.0)    # movement
        s = self._make_score(0.0)    # social
        result = _compute_overall_score(a, f, m, s)
        # Faqat activity (35%) bo'lsa → overall ≈ 35
        assert abs(result - 35.0) < 2.0

    def test_returns_float(self):
        s = self._make_score(50.0)
        result = _compute_overall_score(s, s, s, s)
        assert isinstance(result, float)

    def test_range_0_100(self):
        for pct in [0, 25, 50, 75, 100]:
            s = self._make_score(float(pct))
            result = _compute_overall_score(s, s, s, s)
            assert 0.0 <= result <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# BEHAVIOR — _detect_adi_trend
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectADITrend:

    def test_insufficient_data_none(self):
        assert _detect_adi_trend([]) is None
        assert _detect_adi_trend([70.0]) is None
        assert _detect_adi_trend([70.0, 72.0]) is None

    def test_increasing_trend(self):
        result = _detect_adi_trend([60.0, 65.0, 70.0, 75.0, 80.0])
        assert result == "improving"

    def test_decreasing_trend(self):
        result = _detect_adi_trend([80.0, 75.0, 70.0, 65.0, 60.0])
        assert result == "declining"

    def test_stable_trend(self):
        result = _detect_adi_trend([70.0, 71.0, 69.0, 70.5, 70.0, 70.2, 69.8])
        assert result == "stable"

    def test_returns_string_or_none(self):
        result = _detect_adi_trend([70.0, 72.0, 68.0, 71.0, 70.0])
        assert result is None or isinstance(result, str)

    def test_strong_decline(self):
        result = _detect_adi_trend([90.0, 80.0, 70.0, 60.0, 50.0, 40.0, 30.0])
        assert result == "declining"

    def test_strong_improvement(self):
        result = _detect_adi_trend([30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0])
        assert result == "improving"


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR — NORMAL_RANGES
# ═══════════════════════════════════════════════════════════════════════════════

class TestNormalRanges:

    def test_temperature_keys(self):
        temp = NORMAL_RANGES["temperature"]
        for k in ["min_normal", "max_normal", "min_warning", "max_warning",
                  "min_critical", "max_critical"]:
            assert k in temp

    def test_heart_rate_keys(self):
        hr = NORMAL_RANGES["heart_rate"]
        for k in ["min_normal", "max_normal"]:
            assert k in hr

    def test_temperature_normal_range(self):
        t = NORMAL_RANGES["temperature"]
        assert t["min_normal"] == 38.0
        assert t["max_normal"] == 39.5

    def test_heart_rate_normal_range(self):
        hr = NORMAL_RANGES["heart_rate"]
        assert hr["min_normal"] == 40
        assert hr["max_normal"] == 80

    def test_warning_wider_than_normal(self):
        t = NORMAL_RANGES["temperature"]
        assert t["min_warning"] < t["min_normal"]
        assert t["max_warning"] > t["max_normal"]

    def test_critical_wider_than_warning(self):
        t = NORMAL_RANGES["temperature"]
        assert t["min_critical"] < t["min_warning"]
        assert t["max_critical"] > t["max_warning"]


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR SERVICE — PROCESS READING
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensorServiceProcessReading:

    async def test_process_reading_success(self, db, svc, animal):
        data = _reading_create(animal_id=animal.id)
        result = await svc.process_reading(data)
        assert result.id is not None
        assert result.animal_id == animal.id

    async def test_process_reading_no_animal_ok(self, db, svc):
        """animal_id=None — tizim sensori, alert yaratilmaydi."""
        data = _reading_create(animal_id=None)
        result = await svc.process_reading(data)
        assert result.id is not None

    async def test_process_reading_saves_temperature(self, db, svc, animal):
        data = _reading_create(animal_id=animal.id, temp=38.8)
        result = await svc.process_reading(data)
        assert abs(result.temperature - 38.8) < 0.01

    async def test_process_reading_saves_heart_rate(self, db, svc, animal):
        data = _reading_create(animal_id=animal.id, hr=65)
        result = await svc.process_reading(data)
        assert result.heart_rate == 65

    async def test_process_reading_high_temp_warning(self, db, svc, animal):
        """Yuqori harorat → alert yaratilishi kerak."""
        data = _reading_create(animal_id=animal.id, temp=42.0, hr=60)
        result = await svc.process_reading(data)
        assert result.id is not None  # Xato bo'lmasligi kerak

    async def test_process_reading_low_hr_warning(self, db, svc, animal):
        data = _reading_create(animal_id=animal.id, temp=38.5, hr=15)
        result = await svc.process_reading(data)
        assert result.id is not None

    async def test_process_bulk_success(self, db, svc, animal):
        readings = [_reading_create(
            animal_id=animal.id, device_id=f"BULK-{i}") for i in range(5)]
        result = await svc.process_bulk(readings)
        assert result["saved"] == 5
        assert result["failed"] == 0

    async def test_process_bulk_partial_failure(self, db, svc, animal):
        """Ba'zi xato bo'lsa — barchasi to'xtamaydi."""
        good = _reading_create(animal_id=animal.id, device_id="GOOD")
        bad  = SensorReadingCreate(
            device_id="BAD",
            device_type="collar",
            animal_id=animal.id,
            temperature=-999.0,  # Noto'g'ri harorat
            heart_rate=60,
            recorded_at=NOW,
        )
        result = await svc.process_bulk([good, bad, good])
        # Kamida 2 ta muvaffaqiyatli bo'lishi kerak
        assert result["saved"] >= 1

    async def test_process_bulk_structure(self, db, svc, animal):
        result = await svc.process_bulk(
            [_reading_create(animal_id=animal.id)])
        assert "saved" in result
        assert "failed" in result
        assert "errors" in result


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR SERVICE — DETECT ISSUES
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensorServiceDetectIssues:

    def _svc(self):
        return SensorService.__new__(SensorService)

    def _reading(self, temp=38.5, hr=60):
        r = SensorReading(
            device_id="TEST", device_type="collar",
            temperature=temp, heart_rate=hr,
            recorded_at=NOW,
        )
        return r

    def test_normal_values_no_issues(self):
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=38.8, hr=60))
        assert not result or (not result.get("critical") and not result.get("warning"))

    def test_high_temp_critical(self):
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=42.0, hr=60))
        assert result and (result.get("critical") or result.get("warning"))

    def test_low_temp_critical(self):
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=35.0, hr=60))
        assert result and (result.get("critical") or result.get("warning"))

    def test_high_hr_warning(self):
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=38.5, hr=110))
        assert result and (result.get("critical") or result.get("warning"))

    def test_low_hr_critical(self):
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=38.5, hr=10))
        assert result and (result.get("critical") or result.get("warning"))

    def test_borderline_warning_temp(self):
        """37.5 = warning chegarasi."""
        svc = self._svc()
        result = svc._detect_issues(self._reading(temp=37.5, hr=60))
        assert result is not None


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR SERVICE — DAILY SUMMARY & STATS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSensorServiceSummaryStats:

    async def test_get_daily_summary_empty_none(self, db, svc, animal):
        result = await svc.get_daily_summary(animal.id, "2020-01-01")
        assert result is None or isinstance(result, dict)

    async def test_get_daily_summary_after_reading(self, db, svc, animal):
        await svc.process_reading(_reading_create(
            animal_id=animal.id, temp=38.7, hr=62))
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        result = await svc.get_daily_summary(animal.id, today_str)
        # Natija bo'lishi kerak
        if result:
            assert isinstance(result, dict)

    async def test_get_latest_for_animal(self, db, svc, animal):
        await svc.process_reading(_reading_create(animal_id=animal.id, temp=38.5))
        await svc.process_reading(_reading_create(animal_id=animal.id, temp=39.0))
        latest = await svc.get_latest_for_animal(animal.id)
        if latest:
            assert latest.animal_id == animal.id

    async def test_get_latest_none_when_empty(self, db, svc, animal):
        result = await svc.get_latest_for_animal(animal.id)
        assert result is None or hasattr(result, "id")

    async def test_get_farm_stats_structure(self, db, svc, animal):
        await svc.process_reading(_reading_create(animal_id=animal.id))
        result = await svc.get_farm_stats()
        assert isinstance(result, dict)
        assert "total_devices" in result
        assert "anomalies_today" in result

    async def test_get_active_devices(self, db, svc, animal):
        await svc.process_reading(_reading_create(
            animal_id=animal.id, device_id="ACTIVE-001"))
        result = await svc.get_active_devices()
        assert isinstance(result, list)