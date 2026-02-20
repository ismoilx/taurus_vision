"""
Analytics API Tests — /api/v1/analytics/

Qamrovi:
  - GET /analytics/overview        umumiy statistika
  - GET /analytics/weight-trends   vazn trendi
  - GET /analytics/detection-patterns  aniqlash naqshlari
"""

import pytest
from httpx import AsyncClient


pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestAnalyticsOverview:
    """GET /api/v1/analytics/overview."""

    async def test_overview_empty_db(self, client: AsyncClient):
        """Bo'sh DB — nollar bilan qaytadi."""
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 200
        data = r.json()

        # Kerakli bo'limlar
        assert "animals"    in data
        assert "detections" in data
        assert "weights"    in data

    async def test_overview_animals_section(self, client: AsyncClient):
        """animals bo'limi to'g'ri tuzilmada."""
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 200
        animals = r.json()["animals"]
        assert "total"  in animals
        assert "active" in animals

    async def test_overview_detections_section(self, client: AsyncClient):
        """detections bo'limi total ni o'z ichiga oladi."""
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 200
        detections = r.json()["detections"]
        assert "total" in detections

    async def test_overview_with_data(
        self, client: AsyncClient, sample_animal, sample_detection, sample_weight
    ):
        """Ma'lumot bor — noldan katta."""
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 200
        data = r.json()
        assert data["animals"]["total"]    >= 1
        assert data["detections"]["total"] >= 1


class TestWeightTrends:
    """GET /api/v1/analytics/weight-trends."""

    async def test_trends_empty(self, client: AsyncClient):
        """Bo'sh DB — bo'sh yoki default javob."""
        r = await client.get("/api/v1/analytics/weight-trends")
        assert r.status_code == 200

    async def test_trends_with_data(
        self, client: AsyncClient, sample_animal, sample_weight
    ):
        """O'lchov bor — trend ma'lumotlari qaytadi."""
        r = await client.get("/api/v1/analytics/weight-trends")
        assert r.status_code == 200

    async def test_trends_days_param(self, client: AsyncClient):
        """days parametri qabul qilinadi."""
        r = await client.get("/api/v1/analytics/weight-trends?days=7")
        assert r.status_code == 200

        r2 = await client.get("/api/v1/analytics/weight-trends?days=30")
        assert r2.status_code == 200


class TestDetectionPatterns:
    """GET /api/v1/analytics/detection-patterns."""

    async def test_patterns_empty(self, client: AsyncClient):
        """Bo'sh DB — 200."""
        r = await client.get("/api/v1/analytics/detection-patterns")
        assert r.status_code == 200

    async def test_patterns_with_data(
        self, client: AsyncClient, sample_detection
    ):
        """Detection bor — natija qaytadi."""
        r = await client.get("/api/v1/analytics/detection-patterns")
        assert r.status_code == 200


class TestHealthEndpoint:
    """GET /health — backend health."""

    async def test_health_ok(self, client: AsyncClient):
        """Health endpoint 200 qaytaradi."""
        r = await client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") in ["healthy", "ok", "running"]

    async def test_health_live(self, client: AsyncClient):
        """Health live probe."""
        r = await client.get("/health/live")
        assert r.status_code == 200