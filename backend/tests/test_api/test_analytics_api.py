"""Analytics API Tests — /api/v1/analytics/"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


class TestAnalyticsOverview:
    async def test_overview_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "animals" in data
        assert "detections" in data

    async def test_overview_animals_section(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        animals = r.json()["animals"]
        assert "total" in animals
        assert "active" in animals

    async def test_overview_detections_section(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/overview", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        assert "total" in r.json()["detections"]

    async def test_overview_with_data(self, client: AsyncClient, admin_token: str, sample_animal, sample_detection, sample_weight):
        r = await client.get("/api/v1/analytics/overview", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/dashboard", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["animals"]["total"] >= 1
        assert data["detections"]["total"] >= 1

    async def test_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/analytics/overview")
        assert r.status_code == 401


class TestWeightTrends:
    async def test_trends_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/weight-trends", headers=H(admin_token))
        assert r.status_code == 200

    async def test_trends_days_param(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/trends/weight?days=7", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/weight-trends?days=7", headers=H(admin_token))
        assert r.status_code == 200


class TestDetectionPatterns:
    async def test_patterns_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/analytics/patterns/detections", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/detection-patterns", headers=H(admin_token))
        assert r.status_code == 200

    async def test_patterns_with_data(self, client: AsyncClient, admin_token: str, sample_detection):
        r = await client.get("/api/v1/analytics/patterns/detections", headers=H(admin_token))
        if r.status_code == 404:
            r = await client.get("/api/v1/analytics/detection-patterns", headers=H(admin_token))
        assert r.status_code == 200


class TestHealthEndpoint:
    async def test_health_ok(self, client: AsyncClient):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json().get("status") in ["healthy", "ok", "running", "degraded"]

    async def test_health_live(self, client: AsyncClient):
        r = await client.get("/health/live")
        assert r.status_code == 200