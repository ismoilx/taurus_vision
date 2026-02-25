"""Reports API Tests — /api/v1/reports/"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


class TestAnimalReport:
    async def test_report_animal_not_found(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/reports/animal/99999", headers=H(admin_token))
        assert r.status_code == 404

    async def test_report_animal_success(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(f"/api/v1/reports/animal/{sample_animal.id}", headers=H(admin_token))
        assert r.status_code in (200, 201)

    async def test_no_token(self, client: AsyncClient, sample_animal):
        r = await client.post(f"/api/v1/reports/animal/{sample_animal.id}")
        assert r.status_code == 401


class TestFarmReport:
    async def test_farm_report_empty(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/reports/farm", headers=H(admin_token))
        assert r.status_code in (200, 201)

    async def test_farm_report_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/reports/farm", headers=H(admin_token))
        assert r.status_code in (200, 201)

    async def test_farm_report_format_pdf(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/reports/farm", headers=H(admin_token), json={"format": "pdf"})
        assert r.status_code in (200, 201, 422)


class TestHealthReport:
    async def test_health_report_empty(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/reports/health", headers=H(admin_token))
        assert r.status_code in (200, 201)

    async def test_health_report_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/reports/health", headers=H(admin_token))
        assert r.status_code in (200, 201)


class TestReportPreview:
    async def test_preview_not_found(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/reports/preview/nonexistent-xyz", headers=H(admin_token))
        assert r.status_code == 404