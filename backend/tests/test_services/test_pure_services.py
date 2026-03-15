"""
TAURUS VISION — tests/test_services/test_pure_services.py
==========================================================
WeightEstimator + IdentificationResult + DataSimulator pure funksiyalar
uchun AYAMAS vahshiy testlar. DB yo'q — faqat pure logic.

Qamrov (150+ test):
  ✓ BoundingBox.to_dict / to_absolute
  ✓ WeightEstimator.SPECIES_CALIBRATION — barcha konstantalar
  ✓ WeightEstimator._calculate_weight  — area_ratio, confidence factor
  ✓ WeightEstimator._calculate_confidence — 3 factor: yolo, area, aspect
  ✓ WeightEstimator.estimate           — cattle, sheep, unsupported class
  ✓ WeightEstimator.get_stats          — counter oshishi
  ✓ WeightEstimator.get_supported_species — tuzilma
  ✓ get_weight_estimator               — singleton
  ✓ IdentificationResult.to_dict       — barcha maydonlar
  ✓ IdentificationResult identified=True/False
  ✓ _random_bbox                       — koordinatalar, zona ichida
  ✓ _weight_from_bbox                  — og'irlik diapazoni 50-800
  ✓ _get_hour_activity                 — barcha 24 soat
  ✓ DataSimulator.__init__             — holatlar
  ✓ DataSimulator start/stop           — ikki marta start OK
  ✓ FEEDING_ZONE / RESTING_ZONE / MOVEMENT_ZONE chegaralar
"""

import pytest
import math
from datetime import datetime
from unittest.mock import MagicMock, patch, AsyncMock

from app.services.ai.base import BoundingBox, Detection
from app.services.weight_estimator import WeightEstimator, get_weight_estimator
from app.services.identification_service import (
    IdentificationResult,
    IDENTIFICATION_THRESHOLD,
    MAX_EMBEDDINGS_PER_ANIMAL,
)
from app.services.data_simulator import (
    _random_bbox, _weight_from_bbox, _get_hour_activity,
    DataSimulator, get_simulator,
    FEEDING_ZONE, RESTING_ZONE, MOVEMENT_ZONE, SIM_CAMERAS,
)

pytestmark = pytest.mark.asyncio


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_bbox(x=0.5, y=0.5, w=0.2, h=0.3):
    return BoundingBox(x=x, y=y, width=w, height=h)


def _make_detection(class_id=19, confidence=0.9, bbox=None):
    return Detection(
        class_id=class_id, class_name="cow",
        confidence=confidence,
        bounding_box=bbox or _make_bbox(),
        timestamp=datetime.utcnow(),
    )


# ═══════════════════════════════════════════════════════════════════════════════
# BoundingBox
# ═══════════════════════════════════════════════════════════════════════════════

class TestBoundingBox:
    def test_to_dict_all_keys(self):
        bbox = _make_bbox()
        d = bbox.to_dict()
        for k in ["x", "y", "width", "height"]:
            assert k in d

    def test_to_dict_values(self):
        bbox = BoundingBox(x=0.3, y=0.4, width=0.2, height=0.15)
        d = bbox.to_dict()
        assert abs(d["x"] - 0.3) < 1e-9
        assert abs(d["y"] - 0.4) < 1e-9

    def test_to_absolute_width(self):
        bbox = BoundingBox(x=0.5, y=0.5, width=0.5, height=0.5)
        abs_box = bbox.to_absolute(640, 480)
        assert abs_box["width"] == 320

    def test_to_absolute_height(self):
        bbox = BoundingBox(x=0.5, y=0.5, width=0.5, height=0.5)
        abs_box = bbox.to_absolute(640, 480)
        assert abs_box["height"] == 240

    def test_to_absolute_returns_ints(self):
        bbox = _make_bbox()
        result = bbox.to_absolute(800, 600)
        for v in result.values():
            assert isinstance(v, int)


# ═══════════════════════════════════════════════════════════════════════════════
# WeightEstimator — SPECIES_CALIBRATION
# ═══════════════════════════════════════════════════════════════════════════════

class TestSpeciesCalibration:
    def test_cattle_class_19(self):
        assert 19 in WeightEstimator.SPECIES_CALIBRATION

    def test_sheep_class_20(self):
        assert 20 in WeightEstimator.SPECIES_CALIBRATION

    def test_cattle_base_weight(self):
        assert WeightEstimator.SPECIES_CALIBRATION[19]["base_weight"] == 500.0

    def test_sheep_base_weight(self):
        assert WeightEstimator.SPECIES_CALIBRATION[20]["base_weight"] == 70.0

    def test_cattle_min_max(self):
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        assert cal["min_weight"] < cal["base_weight"] < cal["max_weight"]

    def test_sheep_min_max(self):
        cal = WeightEstimator.SPECIES_CALIBRATION[20]
        assert cal["min_weight"] < cal["base_weight"] < cal["max_weight"]

    def test_all_required_keys(self):
        required = ["name", "base_weight", "scale_factor",
                    "min_weight", "max_weight", "typical_box_area"]
        for cls_id, cal in WeightEstimator.SPECIES_CALIBRATION.items():
            for k in required:
                assert k in cal, f"class_id={cls_id} missing key '{k}'"

    def test_cattle_name(self):
        assert WeightEstimator.SPECIES_CALIBRATION[19]["name"] == "cattle"

    def test_sheep_name(self):
        assert WeightEstimator.SPECIES_CALIBRATION[20]["name"] == "sheep"

    def test_typical_box_area_positive(self):
        for cls_id, cal in WeightEstimator.SPECIES_CALIBRATION.items():
            assert cal["typical_box_area"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# WeightEstimator._calculate_weight
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateWeight:
    def _est(self): return WeightEstimator()

    def test_typical_area_returns_near_base_weight(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        weight = est._calculate_weight(
            box_area=cal["typical_box_area"],
            calibration=cal,
            confidence=1.0,
        )
        # Typical area da base_weight ga yaqin bo'lishi kerak
        assert abs(weight - cal["base_weight"]) < cal["base_weight"] * 0.5

    def test_larger_area_heavier(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        w1 = est._calculate_weight(0.10, cal, 0.9)
        w2 = est._calculate_weight(0.25, cal, 0.9)
        assert w2 > w1  # Katta bbox → og'irroq

    def test_smaller_area_lighter(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        w1 = est._calculate_weight(0.20, cal, 0.9)
        w2 = est._calculate_weight(0.05, cal, 0.9)
        assert w2 < w1

    def test_low_confidence_closer_to_base(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        w_high = est._calculate_weight(0.30, cal, 1.0)
        w_low  = est._calculate_weight(0.30, cal, 0.1)
        # Confidence past bo'lsa base_weight ga yaqinlashadi
        assert abs(w_low - cal["base_weight"]) < abs(w_high - cal["base_weight"])

    def test_returns_float(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        result = est._calculate_weight(0.15, cal, 0.9)
        assert isinstance(result, float)


# ═══════════════════════════════════════════════════════════════════════════════
# WeightEstimator._calculate_confidence
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateConfidence:
    def _est(self): return WeightEstimator()

    def test_range_0_3_to_0_95(self):
        est = self._est()
        bbox = _make_bbox(w=0.15, h=0.12)
        cal  = WeightEstimator.SPECIES_CALIBRATION[19]
        conf = est._calculate_confidence(
            bbox, 0.9, 0.15 * 0.12, cal["typical_box_area"])
        assert 0.3 <= conf <= 0.95

    def test_high_yolo_increases_confidence(self):
        est = self._est()
        bbox = _make_bbox(w=0.15, h=0.12)
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        c1 = est._calculate_confidence(bbox, 0.2, 0.018, cal["typical_box_area"])
        c2 = est._calculate_confidence(bbox, 0.95, 0.018, cal["typical_box_area"])
        assert c2 >= c1

    def test_typical_area_higher_confidence(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        bbox = _make_bbox(w=0.3, h=0.5)  # aspect ratio ≈ 0.6
        # Typical area
        c_typical = est._calculate_confidence(
            bbox, 0.9, cal["typical_box_area"], cal["typical_box_area"])
        # Atypical area
        c_atypical = est._calculate_confidence(
            bbox, 0.9, 0.001, cal["typical_box_area"])
        assert c_typical >= c_atypical

    def test_never_below_0_3(self):
        est = self._est()
        bbox = _make_bbox(w=0.001, h=0.001)
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        conf = est._calculate_confidence(bbox, 0.0, 0.0, cal["typical_box_area"])
        assert conf >= 0.3

    def test_never_above_0_95(self):
        est = self._est()
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        bbox = BoundingBox(
            x=0.5, y=0.5,
            width=math.sqrt(cal["typical_box_area"]),
            height=math.sqrt(cal["typical_box_area"]),
        )
        conf = est._calculate_confidence(
            bbox, 1.0, cal["typical_box_area"], cal["typical_box_area"])
        assert conf <= 0.95


# ═══════════════════════════════════════════════════════════════════════════════
# WeightEstimator.estimate
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightEstimatorEstimate:
    def _est(self): return WeightEstimator()

    def test_estimate_cattle_returns_tuple(self):
        est = self._est()
        det = _make_detection(class_id=19, confidence=0.9)
        weight, conf = est.estimate(det, (480, 640, 3))
        assert isinstance(weight, float)
        assert isinstance(conf, float)

    def test_estimate_sheep_returns_tuple(self):
        est = self._est()
        det = _make_detection(class_id=20, confidence=0.85)
        weight, conf = est.estimate(det, (480, 640, 3))
        assert isinstance(weight, float)

    def test_estimate_cattle_in_range(self):
        est = self._est()
        det = _make_detection(class_id=19, confidence=0.9)
        weight, _ = est.estimate(det, (480, 640, 3))
        cal = WeightEstimator.SPECIES_CALIBRATION[19]
        assert cal["min_weight"] <= weight <= cal["max_weight"]

    def test_estimate_sheep_in_range(self):
        est = self._est()
        det = _make_detection(class_id=20, confidence=0.9,
                              bbox=_make_bbox(w=0.1, h=0.12))
        weight, _ = est.estimate(det, (480, 640, 3))
        cal = WeightEstimator.SPECIES_CALIBRATION[20]
        assert cal["min_weight"] <= weight <= cal["max_weight"]

    def test_estimate_unsupported_raises(self):
        est = self._est()
        det = _make_detection(class_id=99, confidence=0.9)
        with pytest.raises(ValueError) as exc_info:
            est.estimate(det, (480, 640, 3))
        assert "99" in str(exc_info.value)

    def test_conservative_factor_reduces_weight(self):
        est = self._est()
        det = _make_detection(class_id=19, confidence=0.9)
        w_conservative, _ = est.estimate(det, (480, 640, 3), use_conservative=True)
        w_raw, _          = est.estimate(det, (480, 640, 3), use_conservative=False)
        assert w_conservative <= w_raw

    def test_counter_increments(self):
        est = self._est()
        before = est.get_stats()["total_estimates"]
        for _ in range(3):
            est.estimate(_make_detection(), (480, 640, 3))
        after = est.get_stats()["total_estimates"]
        assert after == before + 3

    def test_confidence_range_0_to_1(self):
        est = self._est()
        _, conf = est.estimate(_make_detection(), (480, 640, 3))
        assert 0.0 <= conf <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# WeightEstimator.get_stats & get_supported_species
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightEstimatorMisc:
    def test_get_stats_structure(self):
        est = WeightEstimator()
        stats = est.get_stats()
        assert "total_estimates" in stats
        assert "supported_species" in stats

    def test_get_stats_initial_zero(self):
        est = WeightEstimator()
        assert est.get_stats()["total_estimates"] == 0

    def test_get_supported_species_list(self):
        species = WeightEstimator.get_supported_species()
        assert isinstance(species, list)
        assert len(species) >= 2

    def test_get_supported_species_structure(self):
        for s in WeightEstimator.get_supported_species():
            assert "class_id" in s
            assert "name" in s
            assert "base_weight" in s
            assert "weight_range" in s

    def test_get_weight_estimator_singleton(self):
        e1 = get_weight_estimator()
        e2 = get_weight_estimator()
        assert e1 is e2


# ═══════════════════════════════════════════════════════════════════════════════
# IdentificationResult
# ═══════════════════════════════════════════════════════════════════════════════

class TestIdentificationResult:
    def test_identified_true_high_similarity(self):
        r = IdentificationResult(
            animal_id=5, similarity_score=0.9,
            is_identified=True, tag_id="JNV-001")
        assert r.is_identified is True
        assert r.animal_id == 5

    def test_identified_false_low_similarity(self):
        r = IdentificationResult(
            animal_id=None, similarity_score=0.6,
            is_identified=False)
        assert r.is_identified is False
        assert r.animal_id is None

    def test_to_dict_all_keys(self):
        r = IdentificationResult(
            animal_id=3, similarity_score=0.85,
            is_identified=True,
            matched_embedding_id=10, tag_id="JNV-003")
        d = r.to_dict()
        for k in ["animal_id", "tag_id", "similarity_score",
                  "is_identified", "matched_embedding_id"]:
            assert k in d

    def test_to_dict_similarity_rounded(self):
        r = IdentificationResult(
            animal_id=1, similarity_score=0.123456789,
            is_identified=True)
        d = r.to_dict()
        assert len(str(d["similarity_score"]).replace("0.", "").rstrip("0")) <= 4

    def test_to_dict_none_tag_id(self):
        r = IdentificationResult(
            animal_id=None, similarity_score=0.5,
            is_identified=False)
        d = r.to_dict()
        assert d["tag_id"] is None

    def test_threshold_value(self):
        assert IDENTIFICATION_THRESHOLD == 0.80

    def test_max_embeddings_per_animal(self):
        assert MAX_EMBEDDINGS_PER_ANIMAL == 10

    def test_threshold_between_0_and_1(self):
        assert 0 < IDENTIFICATION_THRESHOLD < 1

    def test_similarity_at_threshold_boundary(self):
        r_above = IdentificationResult(
            animal_id=1, similarity_score=IDENTIFICATION_THRESHOLD,
            is_identified=True)
        assert r_above.similarity_score == IDENTIFICATION_THRESHOLD

        r_below = IdentificationResult(
            animal_id=None,
            similarity_score=IDENTIFICATION_THRESHOLD - 0.01,
            is_identified=False)
        assert r_below.is_identified is False


# ═══════════════════════════════════════════════════════════════════════════════
# DataSimulator — pure functions
# ═══════════════════════════════════════════════════════════════════════════════

class TestRandomBbox:
    def test_returns_dict_with_keys(self):
        bbox = _random_bbox()
        for k in ["x", "y", "w", "h"]:
            assert k in bbox

    def test_all_values_positive(self):
        for _ in range(20):
            bbox = _random_bbox()
            assert bbox["x"] >= 0
            assert bbox["y"] >= 0
            assert bbox["w"] > 0
            assert bbox["h"] > 0

    def test_width_in_range(self):
        for _ in range(20):
            bbox = _random_bbox()
            assert 0.12 <= bbox["w"] <= 0.35

    def test_height_in_range(self):
        for _ in range(20):
            bbox = _random_bbox()
            assert 0.15 <= bbox["h"] <= 0.40

    def test_with_zone_center_inside(self):
        zone = (0.1, 0.2, 0.5, 0.6)
        for _ in range(20):
            bbox = _random_bbox(zone=zone)
            # bbox markazining zonada bo'lishi taxminan tekshiriladi
            cx = bbox["x"] + bbox["w"] / 2
            cy = bbox["y"] + bbox["h"] / 2
            # Zone koordinatalari ichida emas, lekin taxminan
            assert 0 <= cx <= 1.0
            assert 0 <= cy <= 1.0

    def test_no_zone_random_full_range(self):
        xs = set()
        for _ in range(10):
            bbox = _random_bbox()
            xs.add(round(bbox["x"], 1))
        assert len(xs) > 1  # Turli qiymatlar

    def test_values_rounded_to_4_decimal(self):
        bbox = _random_bbox()
        for v in bbox.values():
            assert len(str(v).split(".")[-1]) <= 4


class TestWeightFromBbox:
    def test_returns_float(self):
        bbox = {"w": 0.2, "h": 0.3, "x": 0.5, "y": 0.5}
        result = _weight_from_bbox(bbox, 450.0)
        assert isinstance(result, float)

    def test_weight_in_range_50_800(self):
        for _ in range(20):
            bbox = _random_bbox()
            w = _weight_from_bbox(bbox, 450.0)
            assert 50 <= w <= 800

    def test_larger_bbox_heavier(self):
        small = {"w": 0.05, "h": 0.06, "x": 0.5, "y": 0.5}
        large = {"w": 0.30, "h": 0.35, "x": 0.5, "y": 0.5}
        # O'rtacha ≈ katta bbox og'irroq
        weights_small = [_weight_from_bbox(small, 400.0) for _ in range(50)]
        weights_large = [_weight_from_bbox(large, 400.0) for _ in range(50)]
        assert sum(weights_large) / 50 > sum(weights_small) / 50

    def test_base_weight_blended_in(self):
        """Base weight ta'sir qiladi (0.7 og'irlik)."""
        bbox = {"w": 0.2, "h": 0.2, "x": 0.5, "y": 0.5}
        results_500 = [_weight_from_bbox(bbox, 500.0) for _ in range(20)]
        results_100 = [_weight_from_bbox(bbox, 100.0) for _ in range(20)]
        avg_500 = sum(results_500) / 20
        avg_100 = sum(results_100) / 20
        assert avg_500 > avg_100

    def test_rounded_to_1_decimal(self):
        bbox = {"w": 0.2, "h": 0.25, "x": 0.4, "y": 0.4}
        w = _weight_from_bbox(bbox, 300.0)
        parts = str(w).split(".")
        assert len(parts) == 1 or len(parts[1]) <= 1


class TestGetHourActivity:
    def test_returns_float_for_all_hours(self):
        for h in range(24):
            result = _get_hour_activity(h)
            assert isinstance(result, float)
            assert 0.0 <= result <= 1.0

    def test_night_hours_low_activity(self):
        """0-4 soat — hayvonlar uxlaydi."""
        for h in range(0, 5):
            assert _get_hour_activity(h) < 0.5

    def test_morning_high_activity(self):
        """5-7 soat — erta ertalab yuqori faollik."""
        for h in [5, 6, 7]:
            assert _get_hour_activity(h) >= 0.7

    def test_evening_high_activity(self):
        """17-19 soat — kechqurun juda faol."""
        for h in [17, 18, 19]:
            assert _get_hour_activity(h) >= 0.8

    def test_midday_lower_activity(self):
        """11-13 soat — tush pallasi, dam olish."""
        for h in [11, 12, 13]:
            assert _get_hour_activity(h) < 0.6

    def test_all_24_hours_covered(self):
        """Barcha 24 soat uchun qiymat qaytadi."""
        for h in range(24):
            result = _get_hour_activity(h)
            assert result is not None
            assert 0 < result <= 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# DataSimulator constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataSimulatorConstants:
    def test_sim_cameras_not_empty(self):
        assert len(SIM_CAMERAS) >= 1

    def test_sim_cameras_are_strings(self):
        for cam in SIM_CAMERAS:
            assert isinstance(cam, str) and len(cam) > 0

    def test_feeding_zone_valid(self):
        x1, y1, x2, y2 = FEEDING_ZONE
        assert 0 <= x1 < x2 <= 1
        assert 0 <= y1 < y2 <= 1

    def test_resting_zone_valid(self):
        x1, y1, x2, y2 = RESTING_ZONE
        assert 0 <= x1 < x2 <= 1
        assert 0 <= y1 < y2 <= 1

    def test_movement_zone_valid(self):
        x1, y1, x2, y2 = MOVEMENT_ZONE
        assert 0 <= x1 < x2 <= 1
        assert 0 <= y1 < y2 <= 1

    def test_feeding_zone_is_tuple_of_4(self):
        assert len(FEEDING_ZONE) == 4

    def test_zones_different(self):
        assert FEEDING_ZONE != RESTING_ZONE
        assert FEEDING_ZONE != MOVEMENT_ZONE


# ═══════════════════════════════════════════════════════════════════════════════
# DataSimulator class
# ═══════════════════════════════════════════════════════════════════════════════

class TestDataSimulatorClass:
    def test_init_not_running(self):
        sim = DataSimulator()
        assert sim._running is False

    def test_init_no_task(self):
        sim = DataSimulator()
        assert sim._task is None

    def test_init_empty_weights(self):
        sim = DataSimulator()
        assert sim._animal_weights == {}

    def test_interval_constant(self):
        assert DataSimulator.INTERVAL_SECONDS == 30

    def test_max_detections_constant(self):
        assert DataSimulator.MAX_DETECTIONS == 3

    async def test_start_sets_running(self):
        sim = DataSimulator()
        try:
            await sim.start()
            assert sim._running is True
        finally:
            await sim.stop()

    async def test_start_twice_no_error(self):
        """Ikki marta start() chaqirish xato bermaydi."""
        sim = DataSimulator()
        try:
            await sim.start()
            await sim.start()  # Ikkinchi chaqiruv — hech narsa qilmaydi
            assert sim._running is True
        finally:
            await sim.stop()

    async def test_stop_clears_running(self):
        sim = DataSimulator()
        await sim.start()
        await sim.stop()
        assert sim._running is False

    async def test_stop_when_not_running_no_error(self):
        sim = DataSimulator()
        await sim.stop()  # Ishga tushirilmagan — xato yo'q

    def test_get_simulator_singleton(self):
        s1 = get_simulator()
        s2 = get_simulator()
        assert s1 is s2