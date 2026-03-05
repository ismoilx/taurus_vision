"""
Taurus Vision — Analytics API Tests (Sprint 21-24)
===================================================

Qamrov: /api/v1/analytics/ ostidagi 12 ta endpoint.

SPRINT 21  — ADI trends, Growth trends, Behavior trends
SPRINT 22  — Animal comparison, Period comparison
SPRINT 23  — Herd statistics (+ feed_efficiency_index)
SPRINT 24  — Automated insights
SPRINT 7-8 — Weight trends, Detection patterns (regression tests)
SPRINT 9-10 — Camera performance
SPRINT 11-12 — Health metrics
Dashboard   — Overview

TEST STRATEGIYASI:
    1. Happy path  — to'g'ri ma'lumot bilan to'g'ri javob
    2. Empty DB    — bo'sh bazada ham xato bermaydi (200 qaytaradi)
    3. Edge cases  — chegaraviy qiymatlar, noto'g'ri parametrlar
    4. Auth        — token yo'q -> 401
    5. Schema      — javob majburiy maydonlarga ega
    6. Data-driven — real DB ma'lumotlari javobga ta'sir qiladi

FIXTURE QARAMLIGI:
    sample_animal    — 1 ta sigir (TEST-001)           [conftest.py]
    sample_animals   — 3 ta jonivor                    [conftest.py]
    sample_detection — 1 ta deteksiya                  [conftest.py]
    sample_weight    — 1 ta vazn o'lchovi             [conftest.py]
    sample_adi_log   — 1 ta ADI yozuvi                 [bu fayl]
    rich_dataset     — To'liq 14-kunlik test to'plami [bu fayl]
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta, date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

AUTH = lambda t: {"Authorization": f"Bearer {t}"}

TODAY     = date.today().isoformat()
WEEK_AGO  = (date.today() - timedelta(days=7)).isoformat()
MONTH_AGO = (date.today() - timedelta(days=30)).isoformat()


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
async def sample_adi_log(db: AsyncSession, sample_animal):
    """Bitta ADI log — healthy kategoriyada."""
    from app.models.adi_log import ADILog
    log = ADILog(
        animal_id=sample_animal.id,
        calculated_at=datetime.now(timezone.utc),
        calculation_date=TODAY,
        adi_score=78.5,
        category="healthy",
        data_quality=0.9,
        activity_score=80.0,
        feeding_score=75.0,
        drinking_score=82.0,
        movement_score=70.0,
        growth_score=79.0,
        social_score=77.0,
        sensor_score=None,
        veterinary_score=None,
    )
    db.add(log)
    await db.commit()
    await db.refresh(log)
    return log


@pytest.fixture
async def rich_dataset(db: AsyncSession):
    """
    To'liq test ma'lumot to'plami:
      - 3 ta aktiv jonivor (2 sigir + 1 echki)
      - 14 kun ADI tarixi (A01 yaxshilanadi, A02 yomonlashadi, A03 barqaror)
      - 30 kun vazn o'lchovlari
      - 7 kun deteksiyalari (soatlik naqsh bilan)
    """
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
    from app.models.adi_log import ADILog
    from app.models.weight_measurement import WeightMeasurement
    from app.models.detection import Detection

    now = datetime.now(timezone.utc)

    animals = [
        Animal(tag_id="RICH-A01", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
               birth_date=datetime(2022, 1, 15, tzinfo=timezone.utc),
               acquisition_date=datetime(2023, 1, 1, tzinfo=timezone.utc)),
        Animal(tag_id="RICH-A02", species=AnimalSpecies.CATTLE,
               gender=AnimalGender.MALE, status=AnimalStatus.ACTIVE,
               birth_date=datetime(2021, 6, 10, tzinfo=timezone.utc),
               acquisition_date=datetime(2023, 1, 1, tzinfo=timezone.utc)),
        Animal(tag_id="RICH-A03", species=AnimalSpecies.GOAT,
               gender=AnimalGender.FEMALE, status=AnimalStatus.ACTIVE,
               acquisition_date=datetime(2023, 3, 1, tzinfo=timezone.utc)),
    ]
    for a in animals:
        db.add(a)
    await db.commit()
    for a in animals:
        await db.refresh(a)

    adi_scores = [
        [65, 68, 72, 70, 75, 78, 80, 77, 79, 82, 84, 80, 83, 85],
        [85, 82, 78, 75, 72, 68, 65, 63, 60, 58, 55, 52, 50, 48],
        [70, 70, 71, 69, 72, 70, 71, 70, 70, 72, 71, 70, 72, 71],
    ]
    for animal, scores in zip(animals, adi_scores):
        for i, score in enumerate(scores):
            log_date = date.today() - timedelta(days=13 - i)
            cat = (
                "healthy" if score >= 75 else
                "average" if score >= 50 else
                "warning" if score >= 25 else
                "critical"
            )
            db.add(ADILog(
                animal_id=animal.id,
                calculated_at=now - timedelta(days=13 - i),
                calculation_date=log_date.isoformat(),
                adi_score=float(score),
                category=cat,
                data_quality=0.85,
                activity_score=score * 0.9,
                feeding_score=score * 1.05,
                drinking_score=score * 0.95,
                movement_score=score * 0.88,
                growth_score=score * 1.02,
                social_score=score * 0.97,
            ))

    base_weights = [280.0, 450.0, 42.0]
    daily_gains  = [0.4, 0.2, 0.15]
    for animal, base_w, gain in zip(animals, base_weights, daily_gains):
        for i in range(30):
            db.add(WeightMeasurement(
                animal_id=animal.id,
                timestamp=now - timedelta(days=29 - i),
                estimated_weight_kg=base_w + gain * i,
                confidence_score=0.88,
                camera_id="CAM-RICH-001",
            ))

    for animal, base_w in zip(animals, base_weights):
        for day in range(7):
            for hour_offset in [7, 8, 17, 18]:
                db.add(Detection(
                    animal_id=animal.id,
                    camera_id="CAM-RICH-001",
                    timestamp=now - timedelta(days=day, hours=hour_offset),
                    confidence=0.90,
                    class_id=19,
                    class_name="cow",
                    bbox={"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
                    estimated_weight=base_w,
                ))

    await db.commit()
    return {"animals": animals}


# =============================================================================
# 1. DASHBOARD OVERVIEW
# =============================================================================

class TestDashboardOverview:
    """GET /api/v1/analytics/overview"""

    async def test_200_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_required_top_level_sections(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=AUTH(admin_token))
        data = r.json()
        assert "animals" in data
        assert "detections" in data

    async def test_animals_section_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=AUTH(admin_token))
        animals = r.json()["animals"]
        assert "total" in animals
        assert "active" in animals

    async def test_reflects_real_data(self, client: AsyncClient, admin_token: str, sample_animal, sample_detection):
        r = await client.get("/api/v1/analytics/overview", headers=AUTH(admin_token))
        data = r.json()
        assert data["animals"]["total"] >= 1
        assert data["detections"]["total"] >= 1

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 401

    async def test_invalid_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/overview",
                             headers={"Authorization": "Bearer garbage.token"})
        assert r.status_code == 401


# =============================================================================
# 2. WEIGHT TRENDS  (Sprint 7-8)
# =============================================================================

class TestWeightTrends:
    """GET /api/v1/analytics/trends/weight"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_has_data_list(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token))
        assert "data" in r.json()
        assert isinstance(r.json()["data"], list)

    async def test_with_data_returns_points(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token), params={"days": 30})
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    async def test_per_animal_filter(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 30})
        assert r.status_code == 200
        assert r.json().get("animal_id") == animal_id

    async def test_invalid_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token),
                             params={"animal_id": 999999})
        assert r.status_code == 404

    async def test_aggregation_weekly(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token),
                             params={"aggregation": "weekly"})
        assert r.status_code == 200

    async def test_invalid_aggregation_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=AUTH(admin_token),
                             params={"aggregation": "hourly"})
        assert r.status_code == 422

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/trends/weight")
        assert r.status_code == 401


# =============================================================================
# 3. DETECTION PATTERNS  (Sprint 7-8)
# =============================================================================

class TestDetectionPatterns:
    """GET /api/v1/analytics/patterns/detection"""

    async def test_200_with_dates(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/patterns/detection",
                             headers=AUTH(admin_token),
                             params={"date_from": WEEK_AGO, "date_to": TODAY})
        assert r.status_code == 200

    async def test_missing_dates_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/patterns/detection", headers=AUTH(admin_token))
        assert r.status_code == 422

    async def test_date_to_before_from_400(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/patterns/detection",
                             headers=AUTH(admin_token),
                             params={"date_from": TODAY, "date_to": WEEK_AGO})
        assert r.status_code == 400

    async def test_range_over_365_days_400(self, client: AsyncClient, admin_token: str):
        far = (date.today() - timedelta(days=400)).isoformat()
        r = await client.get("/api/v1/analytics/patterns/detection",
                             headers=AUTH(admin_token),
                             params={"date_from": far, "date_to": TODAY})
        assert r.status_code == 400

    async def test_with_detections(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/patterns/detection",
                             headers=AUTH(admin_token),
                             params={"date_from": WEEK_AGO, "date_to": TODAY})
        assert r.status_code == 200

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/patterns/detection",
                             params={"date_from": WEEK_AGO, "date_to": TODAY})
        assert r.status_code == 401


# =============================================================================
# 4. HEALTH METRICS  (Sprint 11-12)
# =============================================================================

class TestHealthMetrics:
    """GET /api/v1/analytics/health/metrics"""

    async def test_200(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/health/metrics", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_required_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/health/metrics", headers=AUTH(admin_token))
        data = r.json()
        for field in ("status_distribution", "risk_score", "alerts"):
            assert field in data, f"''{field}' yo'q health/metrics javobida"

    async def test_risk_score_in_range(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/health/metrics", headers=AUTH(admin_token))
        score = r.json().get("risk_score", 0)
        assert 0 <= score <= 100, f"risk_score={score} chegaradan tashqari"

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/health/metrics")
        assert r.status_code == 401


# =============================================================================
# 5. CAMERA PERFORMANCE  (Sprint 9-10)
# =============================================================================

class TestCameraPerformance:
    """GET /api/v1/analytics/cameras/performance"""

    async def test_200(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/cameras/performance", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_has_cameras_or_data(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/cameras/performance", headers=AUTH(admin_token))
        data = r.json()
        assert "cameras" in data or "data" in data or "performance" in data

    async def test_days_param_range(self, client: AsyncClient, admin_token: str):
        for days in (1, 7, 30, 90):
            r = await client.get("/api/v1/analytics/cameras/performance",
                                 headers=AUTH(admin_token), params={"days": days})
            assert r.status_code == 200, f"days={days} da {r.status_code}"

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/cameras/performance")
        assert r.status_code == 401


# =============================================================================
# 6. ADI TRENDS  (Sprint 21)
# =============================================================================

class TestADITrends:
    """GET /api/v1/analytics/trends/adi"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token))
        data = r.json()
        assert "data" in data
        assert "stats" in data
        assert "period_days" in data

    async def test_stats_subfields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token))
        stats = r.json()["stats"]
        for f in ("avg_adi", "min_adi", "max_adi", "trend_direction"):
            assert f in stats, f"stats.{f} yo'q"

    async def test_with_data_returns_points(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"days": 14})
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    async def test_individual_animal(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 14})
        assert r.status_code == 200
        assert r.json()["animal_id"] == animal_id

    async def test_trend_direction_valid_values(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"animal_id": rich_dataset["animals"][0].id, "days": 14})
        direction = r.json()["stats"]["trend_direction"]
        assert direction in ("improving", "declining", "stable", "insufficient_data")

    async def test_declining_animal_trend(self, client: AsyncClient, admin_token: str, rich_dataset):
        """A02 yomonlashayapti — declining yoki stable."""
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"animal_id": rich_dataset["animals"][1].id, "days": 14})
        assert r.status_code == 200
        direction = r.json()["stats"]["trend_direction"]
        assert direction in ("declining", "stable"), f"A02 trending: {direction}"

    async def test_invalid_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"animal_id": 999999})
        assert r.status_code == 404

    async def test_days_boundaries_valid(self, client: AsyncClient, admin_token: str):
        for days in (7, 30, 365):
            r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                                 params={"days": days})
            assert r.status_code == 200, f"days={days} da {r.status_code}"

    async def test_days_too_low_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/adi", headers=AUTH(admin_token),
                             params={"days": 3})
        assert r.status_code == 422

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/trends/adi")
        assert r.status_code == 401


# =============================================================================
# 7. GROWTH TRENDS  (Sprint 21)
# =============================================================================

class TestGrowthTrends:
    """GET /api/v1/analytics/trends/growth"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token))
        data = r.json()
        assert "data" in data
        assert "period_days" in data

    async def test_regression_present_with_data(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 90})
        assert r.status_code == 200
        assert "regression" in r.json()

    async def test_regression_fields_when_present(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 90})
        regression = r.json().get("regression")
        if regression is not None:
            assert "slope_kg_per_day" in regression
            assert "r_squared" in regression

    async def test_weight_increasing_for_growing_animal(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 30})
        points = r.json()["data"]
        if len(points) >= 2:
            w_key = next((k for k in points[0] if "weight" in k.lower()), None)
            if w_key and points[0].get(w_key) and points[-1].get(w_key):
                assert points[-1][w_key] >= points[0][w_key]

    async def test_invalid_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"animal_id": 999999})
        assert r.status_code == 404

    async def test_days_min_boundary(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"days": 14})
        assert r.status_code == 200

    async def test_days_too_low_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/growth", headers=AUTH(admin_token),
                             params={"days": 5})
        assert r.status_code == 422

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/trends/growth")
        assert r.status_code == 401


# =============================================================================
# 8. BEHAVIOR TRENDS  (Sprint 21)
# =============================================================================

class TestBehaviorTrends:
    """GET /api/v1/analytics/trends/behavior"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/behavior", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/behavior", headers=AUTH(admin_token))
        data = r.json()
        assert "data" in data
        assert "period_days" in data

    async def test_with_adi_data_returns_points(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/trends/behavior", headers=AUTH(admin_token),
                             params={"days": 14})
        assert r.status_code == 200
        assert len(r.json()["data"]) > 0

    async def test_individual_animal(self, client: AsyncClient, admin_token: str, rich_dataset):
        animal_id = rich_dataset["animals"][0].id
        r = await client.get("/api/v1/analytics/trends/behavior", headers=AUTH(admin_token),
                             params={"animal_id": animal_id, "days": 14})
        assert r.status_code == 200

    async def test_invalid_animal_404(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/behavior", headers=AUTH(admin_token),
                             params={"animal_id": 999999})
        assert r.status_code == 404

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/trends/behavior")
        assert r.status_code == 401


# =============================================================================
# 9. ANIMAL COMPARISON  (Sprint 22)
# =============================================================================

class TestAnimalComparison:
    """GET /api/v1/analytics/compare/animals"""

    async def test_200_two_animals(self, client: AsyncClient, admin_token: str, rich_dataset):
        ids = ",".join(str(a.id) for a in rich_dataset["animals"][:2])
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids})
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str, rich_dataset):
        ids = ",".join(str(a.id) for a in rich_dataset["animals"][:2])
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids})
        data = r.json()
        assert "animals" in data
        assert "period_days" in data
        assert len(data["animals"]) == 2

    async def test_all_three_animals(self, client: AsyncClient, admin_token: str, rich_dataset):
        ids = ",".join(str(a.id) for a in rich_dataset["animals"])
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids})
        assert r.status_code == 200
        assert len(r.json()["animals"]) == 3

    async def test_missing_param_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token))
        assert r.status_code == 422

    async def test_empty_ids_400(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ""})
        assert r.status_code in (400, 422)

    async def test_over_10_animals_400(self, client: AsyncClient, admin_token: str):
        ids = ",".join(str(i) for i in range(1, 12))
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids})
        assert r.status_code == 400

    async def test_non_integer_ids_400(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": "1,abc,3"})
        assert r.status_code in (400, 422)

    async def test_nonexistent_id_error(self, client: AsyncClient, admin_token: str, rich_dataset):
        ids = f"{rich_dataset['animals'][0].id},999999"
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids})
        assert r.status_code in (400, 404)

    async def test_days_reflected_in_response(self, client: AsyncClient, admin_token: str, rich_dataset):
        ids = ",".join(str(a.id) for a in rich_dataset["animals"][:2])
        r = await client.get("/api/v1/analytics/compare/animals", headers=AUTH(admin_token),
                             params={"animal_ids": ids, "days": 14})
        assert r.status_code == 200
        assert r.json()["period_days"] == 14

    async def test_no_token_401(self, client: AsyncClient, rich_dataset):
        ids = str(rich_dataset["animals"][0].id)
        r = await client.get("/api/v1/analytics/compare/animals", params={"animal_ids": ids})
        assert r.status_code == 401


# =============================================================================
# 10. PERIOD COMPARISON  (Sprint 22)
# =============================================================================

class TestPeriodComparison:
    """GET /api/v1/analytics/compare/periods"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token))
        data = r.json()
        assert "current_period" in data
        assert "previous_period" in data
        assert "deltas" in data
        assert "overall_assessment" in data

    async def test_deltas_is_list(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token))
        assert isinstance(r.json()["deltas"], list)

    async def test_overall_assessment_valid_value(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token))
        assessment = r.json()["overall_assessment"]
        valid = {"improving", "declining", "stable", "insufficient_data", "mixed", "no_data"}
        assert assessment in valid, f"Noto'g'ri assessment: '{assessment}'"

    async def test_days_7_and_90(self, client: AsyncClient, admin_token: str):
        for days in (7, 90):
            r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token),
                                 params={"days": days})
            assert r.status_code == 200

    async def test_days_too_low_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/compare/periods", headers=AUTH(admin_token),
                             params={"days": 3})
        assert r.status_code == 422

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/compare/periods")
        assert r.status_code == 401


# =============================================================================
# 11. HERD STATISTICS  (Sprint 23)
# =============================================================================

class TestHerdStatistics:
    """GET /api/v1/analytics/herd/statistics"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_top_level_schema(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        data = r.json()
        for field in (
            "timestamp", "total_animals", "active_animals",
            "species_breakdown", "adi_distribution",
            "weight_distribution", "age_distribution", "kpis",
        ):
            assert field in data, f"'{field}' yo'q herd/statistics javobida"

    async def test_kpi_fields_present(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        kpis = r.json()["kpis"]
        for kpi in (
            "overall_health_score", "detection_coverage_pct",
            "avg_daily_detections", "animals_needing_attention",
            "animals_missing_7d", "feed_efficiency_index",
        ):
            assert kpi in kpis, f"kpis.{kpi} yo'q"

    async def test_feed_efficiency_none_without_feed_data(self, client: AsyncClient, admin_token: str, sample_animal):
        """Feed yozuvlari yo'q — FEI None bo'lishi kerak."""
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        fei = r.json()["kpis"]["feed_efficiency_index"]
        assert fei is None, f"Feed yo'q holda FEI=None kerak, {fei} keldi"

    async def test_adi_distribution_categories(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        dist = r.json()["adi_distribution"]
        for cat in ("healthy", "average", "warning", "critical"):
            assert cat in dist

    async def test_active_animals_count(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        data = r.json()
        assert data["active_animals"] == 3
        assert data["total_animals"] >= 3

    async def test_species_breakdown_correct(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        breakdown = r.json()["species_breakdown"]
        assert len(breakdown) >= 2
        names = [b["species"].lower() for b in breakdown]
        assert any("cattle" in s for s in names)
        assert any("goat" in s for s in names)

    async def test_health_score_in_range(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        score = r.json()["kpis"]["overall_health_score"]
        assert 0 <= score <= 100, f"overall_health_score={score}"

    async def test_coverage_pct_in_range(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        cov = r.json()["kpis"]["detection_coverage_pct"]
        assert 0 <= cov <= 100

    async def test_age_distribution_is_list(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        age_dist = r.json()["age_distribution"]
        assert isinstance(age_dist, list) and len(age_dist) > 0

    async def test_adi_distribution_totals_match_animals(self, client: AsyncClient, admin_token: str, rich_dataset):
        """ADI taqsimot umumiy soni active_animals ga teng."""
        r = await client.get("/api/v1/analytics/herd/statistics", headers=AUTH(admin_token))
        dist = r.json()["adi_distribution"]
        total = sum(v for k, v in dist.items()
                    if k in ("healthy", "average", "warning", "critical", "no_data"))
        assert total == 3, f"ADI taqsimot jami {total} != 3"

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/herd/statistics")
        assert r.status_code == 401


# =============================================================================
# 12. AUTOMATED INSIGHTS  (Sprint 24)
# =============================================================================

class TestAutomatedInsights:
    """GET /api/v1/analytics/insights"""

    async def test_200_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token))
        assert r.status_code == 200

    async def test_schema_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token))
        data = r.json()
        assert "insights" in data
        assert "summary" in data
        assert "generated_at" in data

    async def test_summary_subfields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token))
        summary = r.json()["summary"]
        for f in ("total", "critical", "warning", "positive"):
            assert f in summary

    async def test_summary_total_equals_list_length(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token))
        data = r.json()
        assert data["summary"]["total"] == len(data["insights"])

    async def test_with_data_generates_insights(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                             params={"days": 14})
        assert r.status_code == 200

    async def test_insight_item_required_fields(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                             params={"days": 14})
        for insight in r.json()["insights"]:
            for f in ("insight_id", "category", "severity", "title", "description"):
                assert f in insight, f"insight.{f} yo'q"

    async def test_insight_severity_valid_values(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                             params={"days": 14})
        valid = {"info", "warning", "critical", "positive"}
        for insight in r.json()["insights"]:
            assert insight["severity"] in valid, f"severity='{insight['severity']}'"

    async def test_action_required_is_bool(self, client: AsyncClient, admin_token: str, rich_dataset):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                             params={"days": 14})
        for insight in r.json()["insights"]:
            if "action_required" in insight:
                assert isinstance(insight["action_required"], bool)

    async def test_days_param_valid_range(self, client: AsyncClient, admin_token: str):
        for days in (7, 14, 30, 90):
            r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                                 params={"days": days})
            assert r.status_code == 200, f"days={days} da {r.status_code}"

    async def test_days_too_low_422(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/insights", headers=AUTH(admin_token),
                             params={"days": 3})
        assert r.status_code == 422

    async def test_no_token_401(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/insights")
        assert r.status_code == 401


# =============================================================================
# 13. ROLE ACCESS — Manager va Viewer ham o'qiy oladi
# =============================================================================

class TestAnalyticsRoleAccess:
    """
    Analytics — faqat o'qish endpointlari.
    Admin, Manager, Viewer barchasi 200 olishi kerak.
    """

    READ_ENDPOINTS = [
        "/api/v1/analytics/overview",
        "/api/v1/analytics/trends/weight",
        "/api/v1/analytics/health/metrics",
        "/api/v1/analytics/cameras/performance",
        "/api/v1/analytics/trends/adi",
        "/api/v1/analytics/trends/growth",
        "/api/v1/analytics/trends/behavior",
        "/api/v1/analytics/compare/periods",
        "/api/v1/analytics/herd/statistics",
        "/api/v1/analytics/insights",
    ]

    async def test_manager_reads_all(self, client: AsyncClient, manager_token: str):
        for ep in self.READ_ENDPOINTS:
            r = await client.get(ep, headers=AUTH(manager_token))
            assert r.status_code == 200, f"Manager {ep}: {r.status_code}"

    async def test_viewer_reads_all(self, client: AsyncClient, viewer_token: str):
        for ep in self.READ_ENDPOINTS:
            r = await client.get(ep, headers=AUTH(viewer_token))
            assert r.status_code == 200, f"Viewer {ep}: {r.status_code}"