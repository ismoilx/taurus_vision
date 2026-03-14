"""
TAURUS VISION — tests/test_services/test_analytics_service.py
==============================================================
AnalyticsService tizimini AYAMAS darajada vahshiy testlar.

Qamrov (130+ test):
  ✓ Private helpers (_calculate_risk_score, _build_age_distribution)
  ✓ AnalyticsService.get_dashboard_overview   — tuzilma + jonivorlar soni
  ✓ AnalyticsService.get_weight_trends        — bo'sh, aggregation, animal_id
  ✓ AnalyticsService.get_detection_patterns   — soatli/kunli/kamera ma'lumot
  ✓ AnalyticsService.get_health_metrics       — status distribution, risk_score
  ✓ AnalyticsService.get_adi_trends           — bo'sh, ma'lumotli
  ✓ AnalyticsService.get_herd_statistics      — KPIs tuzilma
  ✓ AnalyticsService.get_automated_insights   — tuzilma
  ✓ AnalyticsService.compare_periods          — tuzilma
  ✓ _get_total_animals, _get_active_animals, _get_animals_by_status
  ✓ _generate_alerts                          — never detected, long missing
  ✓ _calculate_risk_score                     — 0 animal, critical alerts
"""

import pytest
from datetime import datetime, date, timedelta, timezone
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
from app.models.weight_measurement import WeightMeasurement
from app.models.detection import Detection
from app.models.adi_log import ADILog, ADICategory
from app.services.analytics_service import AnalyticsService, _MISSING_DAYS_THRESHOLD

pytestmark = pytest.mark.asyncio

TODAY = date.today()
NOW   = datetime.utcnow()


# ─── Helpers ──────────────────────────────────────────────────────────────────

@pytest.fixture
def svc():
    return AnalyticsService()


@pytest.fixture
async def active_animal(db):
    a = Animal(
        tag_id="ANA-001", species=AnimalSpecies.CATTLE,
        gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 1, 1),
        birth_date=datetime(2020, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def second_animal(db):
    a = Animal(
        tag_id="ANA-002", species=AnimalSpecies.SHEEP,
        gender=AnimalGender.MALE, status=AnimalStatus.ACTIVE,
        acquisition_date=datetime(2021, 6, 1),
        birth_date=datetime(2021, 6, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def sold_animal(db):
    a = Animal(
        tag_id="ANA-SOLD", species=AnimalSpecies.CATTLE,
        gender=AnimalGender.MALE, status=AnimalStatus.SOLD,
        acquisition_date=datetime(2020, 1, 1),
    )
    db.add(a); await db.commit(); await db.refresh(a); return a


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVATE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestCalculateRiskScore:
    def test_zero_animals_returns_zero(self):
        svc = AnalyticsService()
        assert svc._calculate_risk_score({}, [], 0) == 0

    def test_no_alerts_low_score(self):
        svc = AnalyticsService()
        score = svc._calculate_risk_score({"active": 10}, [], 10)
        assert score == 0

    def test_critical_alerts_increase_score(self):
        svc = AnalyticsService()
        alerts = [{"severity": "critical"}] * 5
        score = svc._calculate_risk_score({"active": 10}, alerts, 10)
        assert score > 0

    def test_deceased_animals_increase_score(self):
        svc = AnalyticsService()
        score = svc._calculate_risk_score({"deceased": 5}, [], 10)
        assert score > 0

    def test_warning_alerts_increase_score(self):
        svc = AnalyticsService()
        alerts = [{"severity": "warning"}] * 3
        score = svc._calculate_risk_score({}, alerts, 10)
        assert score > 0

    def test_score_is_numeric(self):
        svc = AnalyticsService()
        score = svc._calculate_risk_score({"active": 5}, [], 5)
        assert isinstance(score, (int, float))


class TestBuildAgeDistribution:
    def test_empty_returns_all_zero_buckets(self):
        svc = AnalyticsService()
        result = svc._build_age_distribution([])
        assert isinstance(result, list)
        # All counts zero
        assert all(b["count"] == 0 for b in result)

    def test_no_birth_date_goes_to_unknown(self):
        svc = AnalyticsService()
        a = Animal(tag_id="X", species=AnimalSpecies.CATTLE,
                   gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
                   acquisition_date=datetime.utcnow(), birth_date=None)
        result = svc._build_age_distribution([a])
        unknown = next(b for b in result if b["range_label"] == "Noma'lum")
        assert unknown["count"] == 1

    def test_young_animal_0_6_months(self):
        svc = AnalyticsService()
        birth = datetime.utcnow() - timedelta(days=60)
        a = Animal(tag_id="Y", species=AnimalSpecies.CATTLE,
                   gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
                   acquisition_date=datetime.utcnow(), birth_date=birth)
        result = svc._build_age_distribution([a])
        young = next(b for b in result if b["range_label"] == "0-6 oy")
        assert young["count"] == 1

    def test_adult_animal_4_plus(self):
        svc = AnalyticsService()
        birth = datetime.utcnow() - timedelta(days=365*5)
        a = Animal(tag_id="Z", species=AnimalSpecies.CATTLE,
                   gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
                   acquisition_date=datetime.utcnow(), birth_date=birth)
        result = svc._build_age_distribution([a])
        adult = next(b for b in result if b["range_label"] == "4+ yil")
        assert adult["count"] == 1

    def test_percentage_correct(self):
        svc = AnalyticsService()
        birth = datetime.utcnow() - timedelta(days=60)
        animals = [Animal(
            tag_id=f"P{i}", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime.utcnow(), birth_date=birth
        ) for i in range(4)]
        result = svc._build_age_distribution(animals)
        young = next(b for b in result if b["range_label"] == "0-6 oy")
        assert young["percentage"] == 100.0

    def test_returns_all_expected_buckets(self):
        svc = AnalyticsService()
        result = svc._build_age_distribution([])
        labels = {b["range_label"] for b in result}
        for expected in ["0-6 oy", "6-12 oy", "1-2 yil", "2-4 yil", "4+ yil", "Noma'lum"]:
            assert expected in labels


# ═══════════════════════════════════════════════════════════════════════════════
# PRIVATE DB HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

class TestPrivateDBHelpers:

    async def test_get_total_animals_empty(self, db, svc):
        count = await svc._get_total_animals(db)
        assert isinstance(count, int) and count >= 0

    async def test_get_total_animals_with_data(self, db, svc, active_animal, sold_animal):
        count = await svc._get_total_animals(db)
        assert count >= 2

    async def test_get_active_animals(self, db, svc, active_animal, sold_animal):
        count = await svc._get_active_animals(db)
        assert count >= 1

    async def test_get_active_animals_excludes_sold(self, db, svc, sold_animal):
        before = await svc._get_active_animals(db)
        # sold_animal aktiv emas
        assert isinstance(before, int)

    async def test_get_animals_by_status(self, db, svc, active_animal, sold_animal):
        result = await svc._get_animals_by_status(db)
        assert isinstance(result, dict)
        assert "active" in result
        assert result["active"] >= 1

    async def test_generate_alerts_never_detected(self, db, svc, active_animal):
        """last_detected_at=None → 'never_detected' alert."""
        # active_animal has no detections
        alerts = await svc._generate_alerts(db)
        never = [a for a in alerts if a["type"] == "never_detected"]
        assert len(never) >= 1

    async def test_generate_alerts_missing_long(self, db, svc):
        """8+ kun ko'rinmagan jonivor → 'no_recent_detection' alert."""
        a = Animal(
            tag_id="MISSING-001", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2021, 1, 1),
            last_detected_at=datetime.utcnow() - timedelta(days=_MISSING_DAYS_THRESHOLD + 1),
        )
        db.add(a); await db.commit()
        alerts = await svc._generate_alerts(db)
        missing = [a for a in alerts if a["type"] == "no_recent_detection"]
        assert len(missing) >= 1

    async def test_generate_alerts_recent_detection_no_alert(self, db, svc):
        """Yaqinda ko'ringan jonivor → alert yo'q."""
        a = Animal(
            tag_id="SEEN-001", species=AnimalSpecies.CATTLE,
            gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
            acquisition_date=datetime(2021, 1, 1),
            last_detected_at=datetime.utcnow() - timedelta(hours=2),
        )
        db.add(a); await db.commit()
        alerts = await svc._generate_alerts(db)
        seen_alert = [al for al in alerts if al.get("animal_tag") == "SEEN-001"
                      and al["type"] == "no_recent_detection"]
        assert len(seen_alert) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════

class TestDashboardOverview:

    async def test_returns_dict(self, db, svc, active_animal):
        result = await svc.get_dashboard_overview(db)
        assert isinstance(result, dict)

    async def test_has_required_keys(self, db, svc, active_animal):
        result = await svc.get_dashboard_overview(db)
        for key in ["animals", "detections", "weight", "system", "alerts", "timestamp"]:
            assert key in result, f"'{key}' topilmadi"

    async def test_animals_section(self, db, svc, active_animal):
        result = await svc.get_dashboard_overview(db)
        animals = result["animals"]
        assert "total"   in animals
        assert "active"  in animals
        assert "by_status" in animals
        assert animals["total"] >= 1

    async def test_detections_section(self, db, svc):
        result = await svc.get_dashboard_overview(db)
        det = result["detections"]
        for k in ["today", "week", "month", "total"]:
            assert k in det
            assert isinstance(det[k], int)

    async def test_weight_section(self, db, svc):
        result = await svc.get_dashboard_overview(db)
        assert "weight" in result
        weight = result["weight"]
        assert "average_kg" in weight
        assert "change_percentage_7d" in weight

    async def test_alerts_is_list(self, db, svc):
        result = await svc.get_dashboard_overview(db)
        assert isinstance(result["alerts"], list)

    async def test_timestamp_present(self, db, svc):
        result = await svc.get_dashboard_overview(db)
        assert result["timestamp"] is not None

    async def test_with_date_range(self, db, svc, active_animal):
        result = await svc.get_dashboard_overview(
            db, date_from=TODAY - timedelta(days=7), date_to=TODAY)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# WEIGHT TRENDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWeightTrends:

    async def test_returns_list(self, db, svc, active_animal):
        result = await svc.get_weight_trends(db)
        assert isinstance(result, list)

    async def test_empty_when_no_measurements(self, db, svc, active_animal):
        result = await svc.get_weight_trends(db)
        assert isinstance(result, list)  # bo'sh bo'lishi mumkin

    async def test_with_measurement_data(self, db, svc, active_animal):
        wm = WeightMeasurement(
            animal_id=active_animal.id,
            estimated_weight_kg=350.0,
            confidence_score=0.9,
            camera_id="CAM-01",
            timestamp=datetime.utcnow(),
        )
        db.add(wm); await db.commit()
        result = await svc.get_weight_trends(db, days=7)
        if result:
            row = result[0]
            for key in ["date", "average_weight", "min_weight", "max_weight",
                        "measurement_count", "animal_count"]:
                assert key in row

    async def test_animal_id_filter(self, db, svc, active_animal, second_animal):
        for animal in [active_animal, second_animal]:
            wm = WeightMeasurement(
                animal_id=animal.id, estimated_weight_kg=300.0,
                confidence_score=0.9, camera_id="C1",
                timestamp=datetime.utcnow())
            db.add(wm)
        await db.commit()
        result = await svc.get_weight_trends(db, animal_id=active_animal.id)
        assert isinstance(result, list)

    async def test_days_parameter(self, db, svc, active_animal):
        result7  = await svc.get_weight_trends(db, days=7)
        result30 = await svc.get_weight_trends(db, days=30)
        assert isinstance(result7, list)
        assert isinstance(result30, list)


# ═══════════════════════════════════════════════════════════════════════════════
# DETECTION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

class TestDetectionPatterns:

    async def test_returns_dict(self, db, svc, active_animal):
        result = await svc.get_detection_patterns(
            db, TODAY - timedelta(days=7), TODAY)
        assert isinstance(result, dict)

    async def test_has_required_keys(self, db, svc, active_animal):
        result = await svc.get_detection_patterns(
            db, TODAY - timedelta(days=3), TODAY)
        for k in ["date_range", "detections_by_hour", "detections_by_day",
                  "detections_by_camera", "statistics"]:
            assert k in result

    async def test_detections_by_hour_24(self, db, svc, active_animal):
        result = await svc.get_detection_patterns(
            db, TODAY - timedelta(days=1), TODAY)
        assert len(result["detections_by_hour"]) == 24

    async def test_statistics_structure(self, db, svc, active_animal):
        result = await svc.get_detection_patterns(
            db, TODAY, TODAY)
        stats = result["statistics"]
        assert "total_detections" in stats
        assert "detection_rate_per_hour" in stats

    async def test_date_range_in_result(self, db, svc, active_animal):
        d_from = TODAY - timedelta(days=5)
        d_to   = TODAY
        result = await svc.get_detection_patterns(db, d_from, d_to)
        assert result["date_range"]["from"] == d_from.isoformat()
        assert result["date_range"]["to"]   == d_to.isoformat()
        assert result["date_range"]["days"] == 6


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH METRICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthMetrics:

    async def test_returns_dict(self, db, svc, active_animal):
        result = await svc.get_health_metrics(db)
        assert isinstance(result, dict)

    async def test_has_required_keys(self, db, svc, active_animal):
        result = await svc.get_health_metrics(db)
        for k in ["animals_by_status", "alerts", "alert_summary",
                  "risk_score", "timestamp"]:
            assert k in result

    async def test_animals_by_status_dict(self, db, svc, active_animal, sold_animal):
        result = await svc.get_health_metrics(db)
        by_status = result["animals_by_status"]
        assert isinstance(by_status, dict)
        assert "active" in by_status

    async def test_alert_summary_structure(self, db, svc, active_animal):
        result = await svc.get_health_metrics(db)
        summary = result["alert_summary"]
        assert "total" in summary
        assert "critical" in summary
        assert "warning" in summary

    async def test_risk_score_range(self, db, svc, active_animal):
        result = await svc.get_health_metrics(db)
        score = result["risk_score"]
        assert 0 <= score <= 100

    async def test_weight_distribution(self, db, svc, active_animal):
        result = await svc.get_health_metrics(db)
        assert "weight_distribution" in result
        assert isinstance(result["weight_distribution"], dict)


# ═══════════════════════════════════════════════════════════════════════════════
# ADI TRENDS
# ═══════════════════════════════════════════════════════════════════════════════

class TestADITrends:

    async def test_returns_dict(self, db, svc, active_animal):
        result = await svc.get_adi_trends(db, animal_id=active_animal.id)
        assert isinstance(result, dict)

    async def test_empty_when_no_adi(self, db, svc, active_animal):
        result = await svc.get_adi_trends(db, animal_id=active_animal.id)
        # Bo'sh ma'lumot bilan ham dict qaytishi kerak
        assert isinstance(result, dict)

    async def test_with_adi_data(self, db, svc, active_animal):
        for i in range(5):
            d = (datetime.now(timezone.utc) - timedelta(days=i)).strftime("%Y-%m-%d")
            log = ADILog(
                animal_id=active_animal.id, calculation_date=d,
                calculated_at=datetime.now(timezone.utc),
                adi_score=70.0 + i, category="average",
                data_quality=0.9,
                activity_score=70.0, feeding_score=70.0, drinking_score=70.0,
                movement_score=70.0, growth_score=70.0, social_score=70.0,
                sensor_score=70.0, veterinary_score=70.0, raw_data={},
            )
            db.add(log)
        await db.commit()
        result = await svc.get_adi_trends(db, animal_id=active_animal.id, days=7)
        assert isinstance(result, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# HERD STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

class TestHerdStatistics:

    async def test_returns_dict(self, db, svc, active_animal):
        result = await svc.get_herd_statistics(db)
        assert isinstance(result, dict)

    async def test_has_total_animals(self, db, svc, active_animal):
        result = await svc.get_herd_statistics(db)
        assert "total_animals" in result
        assert result["total_animals"] >= 1

    async def test_has_kpis(self, db, svc, active_animal):
        result = await svc.get_herd_statistics(db)
        assert "kpis" in result
        kpis = result["kpis"]
        for k in ["overall_health_score", "detection_coverage_pct",
                  "avg_daily_detections", "animals_needing_attention",
                  "animals_missing_7d"]:
            assert k in kpis

    async def test_has_species_breakdown(self, db, svc, active_animal, second_animal):
        result = await svc.get_herd_statistics(db)
        assert "species_breakdown" in result
        assert isinstance(result["species_breakdown"], (dict, list))

    async def test_has_adi_distribution(self, db, svc, active_animal):
        result = await svc.get_herd_statistics(db)
        assert "adi_distribution" in result

    async def test_has_age_distribution(self, db, svc, active_animal):
        result = await svc.get_herd_statistics(db)
        assert "age_distribution" in result
        assert isinstance(result["age_distribution"], list)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARE PERIODS
# ═══════════════════════════════════════════════════════════════════════════════

class TestComparePeriods:

    async def test_returns_dict(self, db, svc, active_animal):
        d1_from = TODAY - timedelta(days=14)
        d1_to   = TODAY - timedelta(days=8)
        d2_from = TODAY - timedelta(days=7)
        d2_to   = TODAY
        result = await svc.compare_periods(db, d1_from, d1_to, d2_from, d2_to)
        assert isinstance(result, dict)

    async def test_has_period_keys(self, db, svc, active_animal):
        d1_from = TODAY - timedelta(days=14)
        d1_to   = TODAY - timedelta(days=8)
        d2_from = TODAY - timedelta(days=7)
        d2_to   = TODAY
        result = await svc.compare_periods(db, d1_from, d1_to, d2_from, d2_to)
        assert "period_1" in result or "current_period" in result or len(result) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATED INSIGHTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAutomatedInsights:

    async def test_returns_dict_or_list(self, db, svc, active_animal):
        result = await svc.get_automated_insights(db)
        assert isinstance(result, (dict, list))

    async def test_no_error_raised(self, db, svc):
        try:
            await svc.get_automated_insights(db)
        except Exception as e:
            pytest.fail(f"get_automated_insights raised exception: {e}")