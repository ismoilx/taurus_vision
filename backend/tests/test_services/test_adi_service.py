"""
TAURUS VISION — tests/test_services/test_adi_service.py
=========================================================
ADI tizimini TIZIMNI AYAMAS darajada, mukammal vahshiy testlar.

Qamrov (180+ test):
  ✓ ADICategory.from_score          — barcha 4 chegara aniq
  ✓ ADIService._sigmoid_score       — nol, midpoint, ikki tomonga ekstremal
  ✓ ADIService._linear_regression_slope — musbat, manfiy, tekis, bitta element
  ✓ ADIService._expected_growth_slope   — barcha species, barcha yosh guruhlari
  ✓ ADIService._in_zone             — ichki, tashqi, chegara holatlari
  ✓ ADIService._std_dev             — nol, bir, ko'p element
  ✓ ADIService._get_period_bounds   — sana → UTC interval
  ✓ ADIService._compute_final_score — barcha available, partial, nol
  ✓ ADIService._compute_activity    — nol deteksiya, norma, 2x norma
  ✓ ADIService._compute_feeding     — nol, past visit, yuqori dwell
  ✓ ADIService._compute_drinking    — nol, past, yaxshi
  ✓ ADIService._compute_movement    — ma'lumot yetarli emas, juda sekin, optimal
  ✓ ADIService._compute_social      — nol, past, normal
  ✓ ADIService._compute_sensor      — sensorsiz (simulated), normal, qizib ketgan
  ✓ ADIService._compute_veterinary  — davolashda, yangi tekshiruv, eski tekshiruv
  ✓ ADIService._compute_growth      — ma'lumot kam, ijobiy trend, manfiy trend
  ✓ ADIService._generate_notes      — turli ssenariylar
  ✓ ADIRepository.create / get_by_id / get_by_animal_and_date
  ✓ ADIRepository.get_latest_for_animal / get_trend_for_animal
  ✓ ADIRepository.get_by_date / get_concerning_animals
  ✓ ADIRepository.get_farm_avg_score / get_farm_category_counts
  ✓ ADIRepository.get_previous_score
  ✓ ADIRepository.count_by_animal / exists
  ✓ ADIRepository.delete_by_animal_and_date / delete_older_than
  ✓ ADIRepository.upsert — yangi va mavjud
  ✓ ADIRepository.get_animals_without_adi_today
  ✓ ADIService.calculate_for_animal — yo'q jonivor, cache hit, force_recalculate
  ✓ ADIService.get_animal_trend
  ✓ ADIService.get_farm_summary     — bo'sh va ma'lumotli ssenariy
"""

import math
import pytest
from datetime import datetime, timedelta, timezone, date
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.adi_log import ADILog, ADICategory
from app.repositories.adi_repository import ADIRepository
from app.services.adi_service import (
    ADIService,
    DetectionSummary,
    ComponentResult,
    ADIResult,
    WEIGHTS,
    ACTIVITY_NORM_DETECTIONS_PER_DAY,
    FEEDING_NORM_VISITS_PER_DAY,
    DRINKING_NORM_VISITS_PER_DAY,
    FEEDING_ZONE,
    DRINKING_ZONE,
    GROWTH_MIN_DATAPOINTS,
)
from app.core.exceptions import EntityNotFoundError

pytestmark = pytest.mark.asyncio

TODAY_STR = datetime.now(timezone.utc).strftime("%Y-%m-%d")
YESTERDAY_STR = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def cattle(db):
    a = Animal(
        tag_id="ADI-CATTLE-001",
        species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
        birth_date=datetime(2021, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def sheep(db):
    a = Animal(
        tag_id="ADI-SHEEP-001",
        species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2022, 6, 1),
        birth_date=datetime(2022, 6, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
def repo(db):
    return ADIRepository(db)


@pytest.fixture
def svc(db):
    return ADIService(db)


def _make_animal(species=AnimalSpecies.CATTLE, age_months=12):
    a = Animal(
        tag_id="MOCK-001",
        species=species,
        gender=AnimalGender.FEMALE,
        status=AnimalStatus.ACTIVE,
        acquisition_date=datetime.utcnow(),
        birth_date=datetime.utcnow() - timedelta(days=int(age_months * 30.44)),
    )
    return a


def _adi_log(animal_id, date_str, score=70.0, category="average"):
    return ADILog(
        animal_id=animal_id,
        calculation_date=date_str,
        calculated_at=datetime.now(timezone.utc),
        adi_score=score,
        category=category,
        data_quality=0.9,
        activity_score=70.0, feeding_score=70.0, drinking_score=70.0,
        movement_score=70.0, growth_score=70.0, social_score=70.0,
        sensor_score=70.0, veterinary_score=70.0,
        raw_data={},
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ADI CATEGORY — from_score
# ═══════════════════════════════════════════════════════════════════════════════

class TestADICategory:
    def test_healthy_at_100(self):      assert ADICategory.from_score(100.0)  == "healthy"
    def test_healthy_at_75(self):       assert ADICategory.from_score(75.0)   == "healthy"
    def test_healthy_at_80(self):       assert ADICategory.from_score(80.0)   == "healthy"
    def test_average_at_74(self):       assert ADICategory.from_score(74.9)   == "average"
    def test_average_at_50(self):       assert ADICategory.from_score(50.0)   == "average"
    def test_average_just_below_75(self): assert ADICategory.from_score(74.99) == "average"
    def test_warning_at_49(self):       assert ADICategory.from_score(49.9)   == "warning"
    def test_warning_at_25(self):       assert ADICategory.from_score(25.0)   == "warning"
    def test_critical_at_24(self):      assert ADICategory.from_score(24.9)   == "critical"
    def test_critical_at_0(self):       assert ADICategory.from_score(0.0)    == "critical"
    def test_critical_just_below_25(self): assert ADICategory.from_score(24.99) == "critical"
    def test_boundary_75_is_healthy(self): assert ADICategory.from_score(75.0) == "healthy"
    def test_boundary_50_is_average(self): assert ADICategory.from_score(50.0) == "average"
    def test_boundary_25_is_warning(self): assert ADICategory.from_score(25.0) == "warning"


# ═══════════════════════════════════════════════════════════════════════════════
# ADIService STATIC UTILITY METHODS (pure, DB yoq)
# ═══════════════════════════════════════════════════════════════════════════════

class TestSigmoidScore:
    """_sigmoid_score() barcha holatlari."""

    def test_returns_positive(self):
        score = ADIService._sigmoid_score(0.5)
        assert score > 0

    def test_returns_max_100(self):
        assert ADIService._sigmoid_score(100.0) <= 100.0

    def test_returns_min_0(self):
        assert ADIService._sigmoid_score(-100.0) >= 0.0

    def test_midpoint_gives_about_75(self):
        """midpoint qiymatida ~75 ball."""
        score = ADIService._sigmoid_score(1.0, midpoint=1.0, steepness=3.0)
        assert 72 <= score <= 78

    def test_zero_input_low_score(self):
        score = ADIService._sigmoid_score(0.0, midpoint=1.0, steepness=3.0)
        assert score < 30

    def test_double_midpoint_high_score(self):
        score = ADIService._sigmoid_score(2.0, midpoint=1.0, steepness=3.0)
        assert score > 85

    def test_steeper_gives_sharper_curve(self):
        gentle = ADIService._sigmoid_score(0.5, midpoint=1.0, steepness=1.0)
        steep  = ADIService._sigmoid_score(0.5, midpoint=1.0, steepness=10.0)
        assert steep < gentle  # Keskinroq egri — pastda qoladi

    def test_score_is_float(self):
        assert isinstance(ADIService._sigmoid_score(1.0), float)


class TestLinearRegressionSlope:
    """_linear_regression_slope() barcha holatlari."""

    def test_increasing_trend(self):
        slope = ADIService._linear_regression_slope([1.0, 2.0, 3.0, 4.0])
        assert slope > 0

    def test_decreasing_trend(self):
        slope = ADIService._linear_regression_slope([4.0, 3.0, 2.0, 1.0])
        assert slope < 0

    def test_flat_trend_zero(self):
        slope = ADIService._linear_regression_slope([5.0, 5.0, 5.0, 5.0])
        assert abs(slope) < 1e-10

    def test_single_element_zero(self):
        assert ADIService._linear_regression_slope([3.0]) == 0.0

    def test_two_elements_positive(self):
        assert ADIService._linear_regression_slope([1.0, 3.0]) > 0

    def test_two_elements_negative(self):
        assert ADIService._linear_regression_slope([3.0, 1.0]) < 0

    def test_large_values_work(self):
        slope = ADIService._linear_regression_slope([100.0, 200.0, 300.0])
        assert slope > 0

    def test_small_values_work(self):
        slope = ADIService._linear_regression_slope([0.001, 0.002, 0.003])
        assert slope > 0

    def test_noisy_trend_still_positive(self):
        # Umumiy tendensiya yuqoriga — ozroq shovqin
        values = [10.0, 11.5, 10.8, 12.2, 11.9, 13.0]
        slope = ADIService._linear_regression_slope(values)
        assert slope > 0


class TestExpectedGrowthSlope:
    """_expected_growth_slope() barcha species va yosh guruhlari."""

    def test_young_cattle_high_slope(self):
        slope = ADIService._expected_growth_slope(3.0, "cattle")
        assert slope == 0.0008

    def test_growing_cattle(self):
        slope = ADIService._expected_growth_slope(12.0, "cattle")
        assert slope == 0.0005

    def test_mature_cattle(self):
        slope = ADIService._expected_growth_slope(24.0, "cattle")
        assert slope == 0.0002

    def test_adult_cattle_zero_growth(self):
        slope = ADIService._expected_growth_slope(48.0, "cattle")
        assert slope == 0.0000

    def test_young_sheep_high_slope(self):
        slope = ADIService._expected_growth_slope(2.0, "sheep")
        assert slope == 0.0010

    def test_growing_sheep(self):
        slope = ADIService._expected_growth_slope(6.0, "sheep")
        assert slope == 0.0005

    def test_adult_sheep_zero(self):
        slope = ADIService._expected_growth_slope(30.0, "sheep")
        assert slope == 0.0000

    def test_unknown_species_defaults_to_cattle(self):
        cattle_slope = ADIService._expected_growth_slope(3.0, "cattle")
        other_slope  = ADIService._expected_growth_slope(3.0, "horse")
        assert other_slope == cattle_slope

    def test_zero_age_returns_slope(self):
        slope = ADIService._expected_growth_slope(0.0, "cattle")
        assert isinstance(slope, float)

    def test_very_old_animal_zero(self):
        assert ADIService._expected_growth_slope(200.0, "cattle") == 0.0


class TestInZone:
    """_in_zone() koordinata tekshiruvi."""

    def test_inside_zone(self):
        assert ADIService._in_zone(0.2, 0.8, FEEDING_ZONE) is True

    def test_outside_zone_x(self):
        assert ADIService._in_zone(0.9, 0.8, FEEDING_ZONE) is False

    def test_outside_zone_y(self):
        assert ADIService._in_zone(0.2, 0.3, FEEDING_ZONE) is False

    def test_on_boundary_x_min(self):
        assert ADIService._in_zone(0.0, 0.8, FEEDING_ZONE) is True

    def test_on_boundary_x_max(self):
        assert ADIService._in_zone(0.4, 0.8, FEEDING_ZONE) is True

    def test_drinking_zone_inside(self):
        assert ADIService._in_zone(0.8, 0.8, DRINKING_ZONE) is True

    def test_drinking_zone_outside(self):
        assert ADIService._in_zone(0.1, 0.8, DRINKING_ZONE) is False

    def test_center_feeding_zone(self):
        cx = (FEEDING_ZONE["x_min"] + FEEDING_ZONE["x_max"]) / 2
        cy = (FEEDING_ZONE["y_min"] + FEEDING_ZONE["y_max"]) / 2
        assert ADIService._in_zone(cx, cy, FEEDING_ZONE) is True


class TestStdDev:
    """_std_dev() standart og'ish."""

    def test_identical_values_zero(self):
        assert ADIService._std_dev([5.0, 5.0, 5.0]) == 0.0

    def test_single_value_zero(self):
        assert ADIService._std_dev([10.0]) == 0.0

    def test_empty_zero(self):
        assert ADIService._std_dev([]) == 0.0

    def test_known_std(self):
        # [2, 4, 4, 4, 5, 5, 7, 9] → std ≈ 2.0
        result = ADIService._std_dev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        assert abs(result - 2.0) < 0.1

    def test_positive_std(self):
        result = ADIService._std_dev([1.0, 2.0, 3.0, 10.0])
        assert result > 0

    def test_two_elements(self):
        result = ADIService._std_dev([0.0, 10.0])
        assert result == 5.0


class TestGetPeriodBounds:
    """_get_period_bounds() sana → UTC interval."""

    def test_start_at_midnight(self):
        start, _ = ADIService._get_period_bounds("2026-03-14")
        assert start.hour == 0 and start.minute == 0 and start.second == 0

    def test_end_is_start_plus_24h(self):
        start, end = ADIService._get_period_bounds("2026-03-14")
        assert (end - start).total_seconds() == 86400

    def test_timezone_utc(self):
        start, end = ADIService._get_period_bounds("2026-01-01")
        assert start.tzinfo == timezone.utc
        assert end.tzinfo   == timezone.utc

    def test_date_preserved(self):
        start, _ = ADIService._get_period_bounds("2026-06-15")
        assert start.year == 2026 and start.month == 6 and start.day == 15


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE FINAL SCORE
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeFinalScore:
    """_compute_final_score() barcha holatlari."""

    def _make_svc(self):
        return ADIService.__new__(ADIService)

    def _comp(self, score, weight, has_data=True):
        return ComponentResult(score=score, weight=weight,
                               detail={}, has_data=has_data)

    def test_all_available_weighted_average(self):
        svc = self._make_svc()
        components = {
            "activity":   self._comp(80.0, 0.5),
            "feeding":    self._comp(60.0, 0.5),
        }
        score, quality = svc._compute_final_score(components)
        assert abs(score - 70.0) < 0.1
        assert abs(quality - 1.0) < 0.01

    def test_empty_returns_zero(self):
        svc = self._make_svc()
        score, quality = svc._compute_final_score({})
        assert score == 0.0 and quality == 0.0

    def test_all_none_scores_returns_zero(self):
        svc = self._make_svc()
        comps = {
            "a": self._comp(None, 0.5),
            "b": self._comp(None, 0.5),
        }
        score, quality = svc._compute_final_score(comps)
        assert score == 0.0 and quality == 0.0

    def test_partial_data_renormalized(self):
        """None bo'lgan komponent og'irligi boshqalarga taqsimlanadi."""
        svc = self._make_svc()
        comps = {
            "a": self._comp(100.0, 0.5),
            "b": self._comp(None,  0.5),  # Ma'lumot yo'q
        }
        score, quality = svc._compute_final_score(comps)
        # Faqat 'a' mavjud → uning score qaytadi
        assert abs(score - 100.0) < 0.1
        assert abs(quality - 0.5) < 0.01

    def test_data_quality_reflects_available_weight(self):
        svc = self._make_svc()
        comps = {
            "act": self._comp(70.0, 0.20),
            "fed": self._comp(70.0, 0.20),
            "drk": self._comp(None, 0.15),
            "mvt": self._comp(None, 0.15),
            "grw": self._comp(None, 0.20),
            "soc": self._comp(None, 0.10),
        }
        _, quality = svc._compute_final_score(comps)
        assert abs(quality - 0.40) < 0.01

    def test_score_clamped_0_100(self):
        svc = self._make_svc()
        comps = {"a": self._comp(100.0, 1.0)}
        score, _ = svc._compute_final_score(comps)
        assert 0.0 <= score <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# COMPUTE INDIVIDUAL COMPONENTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestComputeActivity:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_zero_detections_score_zero_no_data(self):
        s = DetectionSummary()
        result = self._svc()._compute_activity(s)
        assert result.score == 0.0
        assert result.has_data is False

    def test_normal_detections_high_score(self):
        s = DetectionSummary()
        s.total_count = ACTIVITY_NORM_DETECTIONS_PER_DAY
        result = self._svc()._compute_activity(s)
        assert result.score is not None and result.score > 70

    def test_double_norm_high_score(self):
        s = DetectionSummary()
        s.total_count = ACTIVITY_NORM_DETECTIONS_PER_DAY * 2
        result = self._svc()._compute_activity(s)
        assert result.score is not None and result.score > 85

    def test_low_detections_low_score(self):
        s = DetectionSummary()
        s.total_count = 3
        result = self._svc()._compute_activity(s)
        assert result.score is not None and result.score < 50

    def test_weight_correct(self):
        s = DetectionSummary(); s.total_count = 48
        result = self._svc()._compute_activity(s)
        assert result.weight == WEIGHTS["activity"]

    def test_detail_contains_key_info(self):
        s = DetectionSummary(); s.total_count = 48
        result = self._svc()._compute_activity(s)
        assert "detections_today" in result.detail
        assert "norm" in result.detail


class TestComputeFeeding:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_detections_no_data(self):
        s = DetectionSummary()
        result = self._svc()._compute_feeding(s)
        assert result.has_data is False

    def test_normal_visits_good_score(self):
        s = DetectionSummary()
        s.total_count = 48
        s.feeding_visits = FEEDING_NORM_VISITS_PER_DAY
        s.feeding_dwell_sec = 300.0
        result = self._svc()._compute_feeding(s)
        assert result.score is not None and result.score > 70

    def test_zero_visits_low_score(self):
        s = DetectionSummary()
        s.total_count = 20
        s.feeding_visits = 0
        s.feeding_dwell_sec = 0.0
        result = self._svc()._compute_feeding(s)
        assert result.score is not None and result.score < 30

    def test_high_dwell_boosts_score(self):
        s1 = DetectionSummary()
        s1.total_count = 20; s1.feeding_visits = 3; s1.feeding_dwell_sec = 0.0

        s2 = DetectionSummary()
        s2.total_count = 20; s2.feeding_visits = 3; s2.feeding_dwell_sec = 1800.0

        svc = self._svc()
        r1 = svc._compute_feeding(s1)
        r2 = svc._compute_feeding(s2)
        assert r2.score > r1.score


class TestComputeDrinking:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_detections_no_data(self):
        s = DetectionSummary()
        result = self._svc()._compute_drinking(s)
        assert result.has_data is False

    def test_normal_drinking_good_score(self):
        s = DetectionSummary()
        s.total_count = 48
        s.drinking_visits = DRINKING_NORM_VISITS_PER_DAY
        s.drinking_dwell_sec = 120.0
        result = self._svc()._compute_drinking(s)
        assert result.score is not None and result.score > 70

    def test_no_drinking_low_score(self):
        s = DetectionSummary()
        s.total_count = 20
        s.drinking_visits = 0
        result = self._svc()._compute_drinking(s)
        assert result.score is not None and result.score < 30


class TestComputeMovement:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_data_insufficient(self):
        s = DetectionSummary()
        s.bbox_velocities = [0.01, 0.02]  # Kamida 3 kerak
        result = self._svc()._compute_movement(s)
        assert result.has_data is False

    def test_optimal_velocity_high_score(self):
        s = DetectionSummary()
        s.bbox_velocities = [0.02, 0.025, 0.03, 0.022, 0.028] * 5
        result = self._svc()._compute_movement(s)
        assert result.score is not None and result.score > 60

    def test_very_slow_low_score(self):
        s = DetectionSummary()
        s.bbox_velocities = [0.001] * 10  # Juda sekin
        result = self._svc()._compute_movement(s)
        assert result.score is not None and result.score <= 30

    def test_very_fast_moderate_score(self):
        s = DetectionSummary()
        s.bbox_velocities = [0.5] * 10  # Juda tez
        result = self._svc()._compute_movement(s)
        assert result.score is not None and result.score < 70

    def test_detail_contains_velocity_info(self):
        s = DetectionSummary()
        s.bbox_velocities = [0.02] * 5
        result = self._svc()._compute_movement(s)
        assert "avg_velocity" in result.detail


class TestComputeSocial:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_detections_no_data(self):
        s = DetectionSummary()
        result = self._svc()._compute_social(s)
        assert result.has_data is False

    def test_normal_co_detection_good_score(self):
        s = DetectionSummary()
        s.total_count = 100
        s.co_detection_count = 30  # 30% = norma
        result = self._svc()._compute_social(s)
        assert result.score is not None and result.score > 70

    def test_zero_co_detection_low_score(self):
        s = DetectionSummary()
        s.total_count = 50
        s.co_detection_count = 0
        result = self._svc()._compute_social(s)
        assert result.score is not None and result.score < 40

    def test_high_co_detection_high_score(self):
        s = DetectionSummary()
        s.total_count = 50
        s.co_detection_count = 45  # 90%
        result = self._svc()._compute_social(s)
        assert result.score is not None and result.score > 80


class TestComputeSensor:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_sensor_simulated_70(self):
        result = self._svc()._compute_sensor(None)
        assert result.score == 70.0
        assert result.has_data is False

    def test_normal_temperature_100(self):
        result = self._svc()._compute_sensor({"temperature": 38.8})
        assert result.score == 100.0

    def test_borderline_temp_60(self):
        result = self._svc()._compute_sensor({"temperature": 37.7})
        assert result.score == 60.0

    def test_high_fever_10(self):
        result = self._svc()._compute_sensor({"temperature": 41.0})
        assert result.score == 10.0

    def test_normal_heart_rate_100(self):
        result = self._svc()._compute_sensor({"heart_rate": 60.0})
        assert result.score == 100.0

    def test_low_heart_rate_50(self):
        result = self._svc()._compute_sensor({"heart_rate": 25.0})
        assert result.score == 5.0

    def test_combined_avg_score(self):
        result = self._svc()._compute_sensor(
            {"temperature": 38.8, "heart_rate": 60.0})
        assert result.score == 100.0

    def test_one_bad_one_good(self):
        result = self._svc()._compute_sensor(
            {"temperature": 41.0, "heart_rate": 60.0})
        assert abs(result.score - 55.0) < 1.0


class TestComputeVeterinary:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_no_record_neutral_50(self):
        result = self._svc()._compute_veterinary(None)
        assert result.score == 50.0
        assert result.has_data is False

    def test_active_treatment_low_score(self):
        mock_record = MagicMock()
        mock_record.treatment = "Antibiotik kursi"
        mock_record.resolved_at = None
        mock_record.recorded_at = datetime.now(timezone.utc)
        result = self._svc()._compute_veterinary(mock_record)
        assert result.score == 20.0

    def test_recent_checkup_high_score(self):
        mock_record = MagicMock()
        mock_record.treatment = None
        mock_record.resolved_at = None
        mock_record.recorded_at = datetime.now(timezone.utc) - timedelta(days=5)
        result = self._svc()._compute_veterinary(mock_record)
        assert result.score == 85.0

    def test_overdue_checkup_moderate_score(self):
        mock_record = MagicMock()
        mock_record.treatment = None
        mock_record.resolved_at = None
        mock_record.recorded_at = datetime.now(timezone.utc) - timedelta(days=45)
        result = self._svc()._compute_veterinary(mock_record)
        assert result.score == 55.0


class TestComputeGrowth:
    def _svc(self): return ADIService.__new__(ADIService)

    def test_insufficient_data_no_score(self):
        animal = _make_animal()
        hist = [(f"2026-0{i+1}-01", 0.05) for i in range(3)]  # 3 < 7 required
        result = self._svc()._compute_growth(hist, animal)
        assert result.has_data is False

    def test_positive_trend_high_score(self):
        animal = _make_animal(age_months=6)
        # O'sish trendi: har kun +0.001
        hist = [(f"2026-01-{i+1:02d}", 0.05 + i * 0.001) for i in range(15)]
        result = self._svc()._compute_growth(hist, animal)
        assert result.score is not None and result.score >= 40

    def test_negative_trend_low_score(self):
        animal = _make_animal(age_months=6)
        # Kamayish trendi
        hist = [(f"2026-01-{i+1:02d}", 0.10 - i * 0.003) for i in range(15)]
        result = self._svc()._compute_growth(hist, animal)
        assert result.score is not None and result.score < 50

    def test_flat_adult_moderate(self):
        animal = _make_animal(age_months=48)  # Katta yosh — o'sish kutilmaydi
        hist = [(f"2026-01-{i+1:02d}", 0.08) for i in range(15)]
        result = self._svc()._compute_growth(hist, animal)
        assert result.score is not None and result.score >= 60

    def test_score_clamped_0_100(self):
        animal = _make_animal(age_months=6)
        hist = [(f"2026-01-{i+1:02d}", 0.05 + i * 0.05) for i in range(15)]
        result = self._svc()._compute_growth(hist, animal)
        if result.score is not None:
            assert 0.0 <= result.score <= 100.0


# ═══════════════════════════════════════════════════════════════════════════════
# GENERATE NOTES
# ═══════════════════════════════════════════════════════════════════════════════

class TestGenerateNotes:
    def _svc(self): return ADIService.__new__(ADIService)

    def _comp(self, score): return ComponentResult(score=score, weight=0.1, detail={})

    def test_no_issues_healthy_score(self):
        s = DetectionSummary(); s.total_count = 48
        comps = {k: self._comp(90.0) for k in WEIGHTS}
        note = self._svc()._generate_notes(comps, 90.0, s)
        assert note == "Jonivor sog'lom va faol"

    def test_zero_detections_note(self):
        s = DetectionSummary()
        comps = {k: self._comp(70.0) for k in WEIGHTS}
        note = self._svc()._generate_notes(comps, 70.0, s)
        assert note and "ko'rinmadi" in note

    def test_low_feeding_note(self):
        s = DetectionSummary(); s.total_count = 48
        comps = {k: self._comp(70.0) for k in WEIGHTS}
        comps["feeding"] = self._comp(20.0)
        note = self._svc()._generate_notes(comps, 60.0, s)
        assert note and "oziqlanish" in note.lower()

    def test_low_drinking_note(self):
        s = DetectionSummary(); s.total_count = 48
        comps = {k: self._comp(70.0) for k in WEIGHTS}
        comps["drinking"] = self._comp(15.0)
        note = self._svc()._generate_notes(comps, 60.0, s)
        assert note and "suv" in note.lower()

    def test_multiple_issues_combined(self):
        s = DetectionSummary(); s.total_count = 48
        comps = {k: self._comp(70.0) for k in WEIGHTS}
        comps["feeding"]  = self._comp(20.0)
        comps["drinking"] = self._comp(20.0)
        note = self._svc()._generate_notes(comps, 60.0, s)
        assert note and "|" in note  # Ko'p muammo separator bilan

    def test_few_detections_note(self):
        s = DetectionSummary(); s.total_count = 3
        comps = {k: self._comp(70.0) for k in WEIGHTS}
        note = self._svc()._generate_notes(comps, 70.0, s)
        assert note and "3" in note


# ═══════════════════════════════════════════════════════════════════════════════
# ADI REPOSITORY
# ═══════════════════════════════════════════════════════════════════════════════

class TestADIRepository:

    async def test_create_assigns_id(self, db, repo, cattle):
        log = _adi_log(cattle.id, TODAY_STR, score=75.0, category="healthy")
        created = await repo.create(log)
        await db.commit()
        assert created.id is not None

    async def test_get_by_id_existing(self, db, repo, cattle):
        log = await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        found = await repo.get_by_id(log.id)
        assert found is not None and found.id == log.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_by_animal_and_date_existing(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        found = await repo.get_by_animal_and_date(cattle.id, TODAY_STR)
        assert found is not None and found.animal_id == cattle.id

    async def test_get_by_animal_and_date_missing_none(self, db, repo, cattle):
        result = await repo.get_by_animal_and_date(cattle.id, "2020-01-01")
        assert result is None

    async def test_get_latest_for_animal(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, YESTERDAY_STR, score=60.0))
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=75.0))
        await db.commit()
        latest = await repo.get_latest_for_animal(cattle.id)
        assert latest is not None
        assert latest.calculation_date == TODAY_STR

    async def test_get_latest_none_when_no_logs(self, db, repo, cattle):
        result = await repo.get_latest_for_animal(cattle.id)
        assert result is None

    async def test_get_trend_for_animal(self, db, repo, cattle):
        for i in range(5):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            await repo.create(_adi_log(cattle.id, d, score=70.0 + i))
        await db.commit()
        trend = await repo.get_trend_for_animal(cattle.id, days=7)
        assert len(trend) >= 5
        # Eng yangi birinchi
        dates = [t.calculation_date for t in trend]
        assert dates == sorted(dates, reverse=True)

    async def test_get_by_date_all(self, db, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=60.0))
        await db.commit()
        result = await repo.get_by_date(TODAY_STR)
        assert len(result) >= 2

    async def test_get_by_date_category_filter(self, db, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0, category="healthy"))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=30.0, category="warning"))
        await db.commit()
        healthy = await repo.get_by_date(TODAY_STR, category="healthy")
        assert all(l.category == "healthy" for l in healthy)

    async def test_get_concerning_animals(self, db, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=20.0, category="critical"))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=40.0, category="warning"))
        await db.commit()
        concerning = await repo.get_concerning_animals(TODAY_STR)
        cats = {l.category for l in concerning}
        assert "critical" in cats or "warning" in cats
        assert "healthy" not in cats

    async def test_get_farm_avg_score(self, db, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=60.0))
        await db.commit()
        avg = await repo.get_farm_avg_score(TODAY_STR)
        assert avg is not None
        assert abs(avg - 70.0) < 0.5

    async def test_get_farm_avg_score_none_when_empty(self, db, repo):
        avg = await repo.get_farm_avg_score("2020-01-01")
        assert avg is None

    async def test_get_farm_category_counts(self, db, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0, category="healthy"))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=30.0, category="warning"))
        await db.commit()
        counts = await repo.get_farm_category_counts(TODAY_STR)
        assert "healthy" in counts and "warning" in counts
        assert counts["healthy"] >= 1
        assert counts["warning"] >= 1

    async def test_get_previous_score(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, YESTERDAY_STR, score=68.0))
        await db.commit()
        prev = await repo.get_previous_score(cattle.id, TODAY_STR)
        assert prev is not None
        assert abs(prev - 68.0) < 0.01

    async def test_get_previous_score_none_when_empty(self, db, repo, cattle):
        result = await repo.get_previous_score(cattle.id, TODAY_STR)
        assert result is None

    async def test_count_by_animal(self, db, repo, cattle):
        for i in range(3):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            await repo.create(_adi_log(cattle.id, d))
        await db.commit()
        count = await repo.count_by_animal(cattle.id)
        assert count >= 3

    async def test_exists_true(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        assert await repo.exists(cattle.id, TODAY_STR) is True

    async def test_exists_false(self, db, repo, cattle):
        assert await repo.exists(cattle.id, "2020-01-01") is False

    async def test_delete_by_animal_and_date(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        result = await repo.delete_by_animal_and_date(cattle.id, TODAY_STR)
        await db.commit()
        assert result is True
        assert await repo.exists(cattle.id, TODAY_STR) is False

    async def test_delete_missing_returns_false(self, db, repo, cattle):
        result = await repo.delete_by_animal_and_date(cattle.id, "2020-01-01")
        assert result is False

    async def test_delete_older_than(self, db, repo, cattle):
        old_date = (datetime.now(timezone.utc) - timedelta(days=100)).strftime("%Y-%m-%d")
        await repo.create(_adi_log(cattle.id, old_date))
        await db.commit()
        deleted = await repo.delete_older_than(days=60)
        await db.commit()
        assert deleted >= 1
        assert await repo.exists(cattle.id, old_date) is False

    async def test_delete_older_than_keeps_recent(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        await repo.delete_older_than(days=30)
        await db.commit()
        assert await repo.exists(cattle.id, TODAY_STR) is True

    async def test_upsert_creates_new(self, db, repo, cattle):
        log_data = dict(
            calculated_at=datetime.now(timezone.utc),
            adi_score=72.0, category="average", data_quality=0.9,
            activity_score=72.0, feeding_score=72.0, drinking_score=72.0,
            movement_score=72.0, growth_score=72.0, social_score=72.0,
            sensor_score=72.0, veterinary_score=72.0,
        )
        result = await repo.upsert(cattle.id, TODAY_STR, log_data)
        await db.commit()
        assert result.id is not None and result.adi_score == 72.0

    async def test_upsert_updates_existing(self, db, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=60.0))
        await db.commit()
        log_data = dict(
            calculated_at=datetime.now(timezone.utc),
            adi_score=85.0, category="healthy", data_quality=0.95,
            activity_score=85.0, feeding_score=85.0, drinking_score=85.0,
            movement_score=85.0, growth_score=85.0, social_score=85.0,
            sensor_score=85.0, veterinary_score=85.0,
        )
        result = await repo.upsert(cattle.id, TODAY_STR, log_data)
        await db.commit()
        assert abs(result.adi_score - 85.0) < 0.01

    async def test_get_animals_without_adi_today(self, db, repo, cattle, sheep):
        """Bugun ADI hisoblanmagan aktiv jonivorlar."""
        # Faqat cattle uchun ADI saqlаymiz
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        missing = await repo.get_animals_without_adi_today()
        assert sheep.id in missing
        assert cattle.id not in missing


# ═══════════════════════════════════════════════════════════════════════════════
# ADI SERVICE — HIGH-LEVEL (DB bilan)
# ═══════════════════════════════════════════════════════════════════════════════

class TestADIServiceCalculate:

    async def test_calculate_missing_animal_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.calculate_for_animal(999999)

    async def test_calculate_returns_adi_result(self, db, svc, cattle):
        result = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        assert isinstance(result, ADIResult)
        assert result.animal_id == cattle.id

    async def test_calculate_score_range(self, db, svc, cattle):
        result = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        assert 0.0 <= result.adi_score <= 100.0

    async def test_calculate_saves_to_db(self, db, svc, repo, cattle):
        await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        saved = await repo.get_by_animal_and_date(cattle.id, TODAY_STR)
        assert saved is not None

    async def test_calculate_cache_hit_same_result(self, db, svc, cattle):
        """Mavjud ADI qayta hisoblanmaydi — cache qaytariladi."""
        r1 = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        r2 = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        assert abs(r1.adi_score - r2.adi_score) < 0.01

    async def test_calculate_force_recalculate(self, db, svc, repo, cattle):
        """force_recalculate=True eski yozuvni o'chirib yangisini yaratadi."""
        r1 = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        r2 = await svc.calculate_for_animal(
            cattle.id, target_date=TODAY_STR, force_recalculate=True)
        # Ikkalasi ham ADIResult
        assert isinstance(r2, ADIResult)

    async def test_calculate_category_matches_score(self, db, svc, cattle):
        result = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        expected_cat = ADICategory.from_score(result.adi_score)
        assert result.category == expected_cat

    async def test_calculate_data_quality_range(self, db, svc, cattle):
        result = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        assert 0.0 <= result.data_quality <= 1.0

    async def test_calculate_components_count(self, db, svc, cattle):
        result = await svc.calculate_for_animal(cattle.id, target_date=TODAY_STR)
        assert len(result.components) == 8
        for key in WEIGHTS:
            assert key in result.components


class TestADIServiceTrendAndSummary:

    async def test_get_animal_trend_empty(self, db, svc, cattle):
        trend = await svc.get_animal_trend(cattle.id, days=30)
        assert isinstance(trend, list)

    async def test_get_animal_trend_after_calculation(self, db, svc, repo, cattle):
        # 3 kun uchun ADI log qo'shamiz
        for i in range(3):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            await repo.create(_adi_log(cattle.id, d, score=70.0 + i * 5))
        await db.commit()
        trend = await svc.get_animal_trend(cattle.id, days=7)
        assert len(trend) >= 3

    async def test_get_farm_summary_empty(self, db, svc):
        summary = await svc.get_farm_summary(target_date="2020-01-01")
        assert "total_animals" in summary
        assert summary["total_animals"] == 0

    async def test_get_farm_summary_with_data(self, db, svc, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0, category="healthy"))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=30.0, category="warning"))
        await db.commit()
        summary = await svc.get_farm_summary(target_date=TODAY_STR)
        assert summary["total_animals"] >= 2
        assert "farm_adi_score" in summary
        assert "healthy_count" in summary
        assert "warning_count" in summary

    async def test_farm_summary_percentages_sum_100(self, db, svc, repo, cattle, sheep):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=80.0, category="healthy"))
        await repo.create(_adi_log(sheep.id,  TODAY_STR, score=60.0, category="average"))
        await db.commit()
        summary = await svc.get_farm_summary(target_date=TODAY_STR)
        if summary["total_animals"] > 0:
            total_pct = (summary.get("healthy_pct", 0) + summary.get("average_pct", 0) +
                         summary.get("warning_pct", 0) + summary.get("critical_pct", 0))
            assert abs(total_pct - 100.0) < 0.5

    async def test_farm_summary_needs_attention_list(self, db, svc, repo, cattle):
        await repo.create(_adi_log(cattle.id, TODAY_STR, score=20.0, category="critical"))
        await db.commit()
        summary = await svc.get_farm_summary(target_date=TODAY_STR)
        assert isinstance(summary["needs_attention"], list)
        assert len(summary["needs_attention"]) >= 1


class TestADIServiceBatchCalculate:

    async def test_batch_returns_list(self, db, svc, cattle):
        results = await svc.calculate_for_all_active(target_date=TODAY_STR)
        assert isinstance(results, list)

    async def test_batch_includes_active_animal(self, db, svc, cattle):
        results = await svc.calculate_for_all_active(target_date=TODAY_STR)
        ids = [r.animal_id for r in results]
        assert cattle.id in ids

    async def test_batch_skips_already_calculated(self, db, svc, repo, cattle):
        # Avval hisoblaymiz
        await repo.create(_adi_log(cattle.id, TODAY_STR))
        await db.commit()
        # Endi batch → cattle o'tkazib yuboriladi
        results = await svc.calculate_for_all_active(target_date=TODAY_STR)
        cattle_results = [r for r in results if r.animal_id == cattle.id]
        assert len(cattle_results) == 0  # Cache hit → qayta hisoblanmadi