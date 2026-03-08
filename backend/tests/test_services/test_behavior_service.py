"""
BehaviorService uchun unit testlar.

Test strategiyasi:
    - Scoring helper funksiyalar: DB talab etmaydi → to'g'ridan-to'g'ri test
    - BehaviorService metodlar: AsyncMock DB session bilan test

Ishga tushirish:
    cd backend
    pytest tests/test_services/test_behavior_service.py -v
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from app.services.behavior_service import (
    BehaviorService,
    _score_to_status,
    _compute_activity_score,
    _compute_feeding_score,
    _compute_movement_score,
    _compute_social_score,
    _compute_overall_score,
    _build_anomalies_and_recommendations,
    _detect_adi_trend,
    _classify_anomaly_type,
    _FEEDING_GAP_H,
    _HIGH_ACTIVITY,
    _MOVEMENT_ACTIVE,
)
from app.schemas.behavior import BehaviorScore


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
def mock_db() -> AsyncMock:
    """Asinxron DB session mockasi."""
    db = AsyncMock()
    db.execute = AsyncMock()
    db.scalar = AsyncMock(return_value=0)
    return db


@pytest.fixture
def service(mock_db: AsyncMock) -> BehaviorService:
    """BehaviorService misoli (mock DB bilan)."""
    return BehaviorService(mock_db)


def _make_score(percentage: float) -> BehaviorScore:
    """Test uchun BehaviorScore yaratuvchi yordamchi."""
    return BehaviorScore(
        value=percentage,
        max_value=100.0,
        percentage=percentage,
        status=_score_to_status(percentage),
        description="test",
    )


# =============================================================================
# _score_to_status
# =============================================================================


class TestScoreToStatus:
    def test_excellent_boundary(self):
        assert _score_to_status(90.0) == "excellent"
        assert _score_to_status(100.0) == "excellent"

    def test_good_boundary(self):
        assert _score_to_status(75.0) == "good"
        assert _score_to_status(89.9) == "good"

    def test_fair_boundary(self):
        assert _score_to_status(55.0) == "fair"
        assert _score_to_status(74.9) == "fair"

    def test_poor_boundary(self):
        assert _score_to_status(35.0) == "poor"
        assert _score_to_status(54.9) == "poor"

    def test_critical_boundary(self):
        assert _score_to_status(0.0) == "critical"
        assert _score_to_status(34.9) == "critical"


# =============================================================================
# _compute_activity_score
# =============================================================================


class TestComputeActivityScore:
    def test_zero_detections(self):
        score = _compute_activity_score(0, 24)
        assert score.percentage == 0.0
        assert score.status == "critical"
        assert "Hech qanday" in score.description

    def test_full_activity(self):
        # 24 soatda HIGH_ACTIVITY ta detection = 100%
        score = _compute_activity_score(_HIGH_ACTIVITY, 24)
        assert score.percentage == 100.0
        assert score.status == "excellent"

    def test_half_period(self):
        # 12 soatda HIGH_ACTIVITY/2 = 100%
        expected = _HIGH_ACTIVITY // 2
        score = _compute_activity_score(expected, 12)
        assert score.percentage == 100.0

    def test_percentage_cap_at_100(self):
        # Ortiqcha detection — maksimal 100%
        score = _compute_activity_score(_HIGH_ACTIVITY * 2, 24)
        assert score.percentage == 100.0

    def test_low_activity(self):
        score = _compute_activity_score(2, 24)
        assert score.percentage < 20.0
        assert score.status in ("poor", "critical")


# =============================================================================
# _compute_feeding_score
# =============================================================================


class TestComputeFeedingScore:
    def test_normal_feeding(self):
        # 24 soatda 4 ta tashrif (har 6 soatda 1) = 100%
        score = _compute_feeding_score(4, 24, None)
        assert score.percentage == 100.0
        assert score.status == "excellent"

    def test_zero_visits(self):
        score = _compute_feeding_score(0, 24, None)
        assert score.percentage == 0.0
        assert score.status == "critical"

    def test_feeding_gap_penalty(self):
        """So'nggi oziqlanishdan FEEDING_GAP_H dan ko'p o'tsa — jazo."""
        long_gap = float(_FEEDING_GAP_H + 6)  # 6 soat ortiqcha
        score_with_gap = _compute_feeding_score(4, 24, long_gap)
        score_without_gap = _compute_feeding_score(4, 24, None)
        assert score_with_gap.percentage < score_without_gap.percentage

    def test_recent_feeding_no_penalty(self):
        """Yaqinda oziqlanish bo'lsa — jazo yo'q."""
        recent = float(_FEEDING_GAP_H - 1)
        score = _compute_feeding_score(4, 24, recent)
        assert score.percentage == 100.0

    def test_description_contains_last_feeding(self):
        score = _compute_feeding_score(3, 24, 5.5)
        assert "5.5" in score.description


# =============================================================================
# _compute_movement_score
# =============================================================================


class TestComputeMovementScore:
    def test_very_active(self):
        score = _compute_movement_score(_MOVEMENT_ACTIVE + 0.01)
        assert score.percentage == 90.0
        assert score.status == "excellent"

    def test_moderate_movement(self):
        score = _compute_movement_score(0.10)
        assert score.percentage == 75.0
        assert score.status == "good"

    def test_low_movement(self):
        score = _compute_movement_score(0.07)
        assert score.percentage == 40.0
        assert score.status == "poor"

    def test_almost_inactive(self):
        score = _compute_movement_score(0.02)
        assert score.percentage == 20.0
        assert score.status == "critical"

    def test_no_movement_data(self):
        score = _compute_movement_score(0.0)
        assert score.percentage == 0.0
        assert score.status == "critical"


# =============================================================================
# _compute_social_score
# =============================================================================


class TestComputeSocialScore:
    def test_highly_social(self):
        score = _compute_social_score(0.5)
        assert score.percentage == 90.0

    def test_moderate_social(self):
        score = _compute_social_score(0.2)
        assert score.percentage == 75.0

    def test_low_social(self):
        score = _compute_social_score(0.05)
        assert score.percentage == 35.0

    def test_isolated(self):
        score = _compute_social_score(0.0)
        assert score.percentage == 15.0
        assert "aniqlanmadi" in score.description


# =============================================================================
# _compute_overall_score
# =============================================================================


class TestComputeOverallScore:
    def test_all_excellent(self):
        s = _make_score(100.0)
        overall = _compute_overall_score(s, s, s, s)
        assert overall == 100.0

    def test_all_zero(self):
        s = _make_score(0.0)
        overall = _compute_overall_score(s, s, s, s)
        assert overall == 0.0

    def test_weights_sum_to_one(self):
        """Og'irliklar jumlasi 1.0 ga teng (35+35+20+10 = 100%)."""
        # 100% activity va feeding, 0% movement va social
        activity = _make_score(100.0)
        feeding = _make_score(100.0)
        movement = _make_score(0.0)
        social = _make_score(0.0)
        overall = _compute_overall_score(activity, feeding, movement, social)
        assert overall == pytest.approx(70.0, abs=0.1)  # 35% + 35%

    def test_weighted_average(self):
        """Aniq og'irliklar bilan tekshirish."""
        activity = _make_score(80.0)
        feeding = _make_score(60.0)
        movement = _make_score(40.0)
        social = _make_score(20.0)
        expected = 80 * 0.35 + 60 * 0.35 + 40 * 0.20 + 20 * 0.10
        overall = _compute_overall_score(activity, feeding, movement, social)
        assert overall == pytest.approx(expected, abs=0.1)


# =============================================================================
# _detect_adi_trend
# =============================================================================


class TestDetectAdiTrend:
    def test_improving(self):
        assert _detect_adi_trend([60.0, 62.0, 65.0, 67.0, 70.0]) == "improving"

    def test_declining(self):
        assert _detect_adi_trend([80.0, 75.0, 72.0, 68.0, 74.0]) == "declining"

    def test_stable(self):
        assert _detect_adi_trend([70.0, 71.0, 69.0, 70.5, 71.0]) == "stable"

    def test_insufficient_data(self):
        assert _detect_adi_trend([]) is None
        assert _detect_adi_trend([70.0]) is None

    def test_exactly_5_diff_improving(self):
        assert _detect_adi_trend([60.0, 65.0]) == "improving"

    def test_exactly_minus5_diff_declining(self):
        assert _detect_adi_trend([70.0, 65.0]) == "declining"


# =============================================================================
# _classify_anomaly_type
# =============================================================================


class TestClassifyAnomalyType:
    def test_feeding_gap_warning(self):
        atype, sev = _classify_anomaly_type("So'nggi oziqlanishdan 14 soat o'tdi")
        assert atype == "feeding_gap"
        assert sev == "warning"

    def test_feeding_stopped_critical(self):
        atype, sev = _classify_anomaly_type("Oziqlanish juda kam yoki to'xtagan")
        assert atype == "feeding_gap"
        assert sev == "critical"

    def test_inactivity(self):
        atype, sev = _classify_anomaly_type("24 soat davomida hech qanday detection yo'q")
        assert atype == "inactivity"
        assert sev == "critical"

    def test_low_movement(self):
        atype, sev = _classify_anomaly_type("Juda kam harakat aniqlandi")
        assert atype == "low_movement"
        assert sev == "warning"

    def test_social_isolation(self):
        atype, sev = _classify_anomaly_type("Izolyatsiya belgilari aniqlandi")
        assert atype == "social_isolation"
        assert sev == "warning"

    def test_unknown(self):
        atype, sev = _classify_anomaly_type("Noma'lum xato")
        assert atype == "other"
        assert sev == "warning"


# =============================================================================
# _build_anomalies_and_recommendations
# =============================================================================


class TestBuildAnomaliesAndRecommendations:
    def test_no_detections_triggers_anomaly(self):
        s = _make_score(0.0)
        anomalies, recs = _build_anomalies_and_recommendations(
            s, s, s, s, None, 0
        )
        assert len(anomalies) > 0
        assert len(recs) > 0
        assert any("detection" in a for a in anomalies)

    def test_feeding_gap_anomaly(self):
        good = _make_score(80.0)
        bad_feeding = _make_score(20.0)
        long_gap = float(_FEEDING_GAP_H + 5)
        anomalies, recs = _build_anomalies_and_recommendations(
            good, bad_feeding, good, good, long_gap, 10
        )
        assert any("oziqlanish" in a.lower() or "soat" in a for a in anomalies)

    def test_healthy_animal_no_anomalies(self):
        s = _make_score(95.0)
        anomalies, recs = _build_anomalies_and_recommendations(
            s, s, s, s, 3.0, 50
        )
        assert len(anomalies) == 0
        assert len(recs) == 0


# =============================================================================
# BehaviorService — analyze_animal (integration-style with mocks)
# =============================================================================


class TestBehaviorServiceAnalyzeAnimal:
    @pytest.mark.asyncio
    async def test_animal_not_found_raises_value_error(self, service: BehaviorService, mock_db: AsyncMock):
        """Jonivor topilmasa ValueError ko'tarilishi kerak."""
        mock_db.get = AsyncMock(return_value=None)

        with pytest.raises(ValueError, match="topilmadi"):
            await service.analyze_animal(animal_id=999, period_hours=24)

    @pytest.mark.asyncio
    async def test_no_detections_returns_zero_scores(
        self, service: BehaviorService, mock_db: AsyncMock
    ):
        """Detection yo'q bo'lganda nol ballar qaytarilishi kerak."""
        # Mock: animal mavjud
        mock_animal = MagicMock()
        mock_animal.tag_id = "JNV-001"
        mock_db.get = AsyncMock(return_value=mock_animal)

        # Mock: hech qanday detection yo'q
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.analyze_animal(animal_id=1, period_hours=24)

        assert result.detection_count == 0
        assert result.overall_score == 0.0
        assert result.overall_status == "critical"
        assert len(result.anomalies) > 0

    @pytest.mark.asyncio
    async def test_result_has_correct_animal_id(
        self, service: BehaviorService, mock_db: AsyncMock
    ):
        """Natijada to'g'ri animal_id bo'lishi kerak."""
        mock_animal = MagicMock()
        mock_animal.tag_id = "JNV-042"
        mock_db.get = AsyncMock(return_value=mock_animal)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.analyze_animal(animal_id=42, period_hours=24)

        assert result.animal_id == 42
        assert result.animal_tag == "JNV-042"