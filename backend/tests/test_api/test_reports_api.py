"""
Reports API Tests — /api/v1/reports/

Qamrovi:
  - POST /reports/animal/{id}   — jonivor hisoboti
  - POST /reports/farm          — ferma hisoboti
  - POST /reports/health        — sog'liq hisoboti
  - GET  /reports/preview/{id}  — preview
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestAnimalReport:
    """POST /api/v1/reports/animal/{animal_id}"""

    async def test_report_animal_not_found(self, client: AsyncClient):
        """Mavjud bo'lmagan jonivor — 404."""
        r = await client.post("/api/v1/reports/animal/99999")
        assert r.status_code == 404

    async def test_report_animal_success(self, client: AsyncClient, sample_animal):
        """Jonivor hisoboti yaratish."""
        r = await client.post(f"/api/v1/reports/animal/{sample_animal.id}")
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            data = r.json()
            assert "report" in data or "content" in data or "html" in data or "pdf_url" in data

    async def test_report_animal_with_period(self, client: AsyncClient, sample_animal):
        """Davr filtri bilan hisobot."""
        r = await client.post(
            f"/api/v1/reports/animal/{sample_animal.id}",
            json={"period_days": 30},
        )
        assert r.status_code in (200, 201, 422)


class TestFarmReport:
    """POST /api/v1/reports/farm"""

    async def test_farm_report_empty(self, client: AsyncClient):
        """Bo'sh ferma hisoboti."""
        r = await client.post("/api/v1/reports/farm")
        assert r.status_code in (200, 201)

    async def test_farm_report_with_animals(self, client: AsyncClient, sample_animals):
        """Jonivorlar bilan ferma hisoboti."""
        r = await client.post("/api/v1/reports/farm")
        assert r.status_code in (200, 201)
        if r.status_code in (200, 201):
            assert len(r.content) > 0

    async def test_farm_report_format_json(self, client: AsyncClient, sample_animals):
        """JSON formatda hisobot."""
        r = await client.post(
            "/api/v1/reports/farm",
            json={"format": "json"},
        )
        assert r.status_code in (200, 201, 422)

    async def test_farm_report_format_pdf(self, client: AsyncClient, sample_animals):
        """PDF formatda hisobot."""
        r = await client.post(
            "/api/v1/reports/farm",
            json={"format": "pdf"},
        )
        assert r.status_code in (200, 201, 422)


class TestHealthReport:
    """POST /api/v1/reports/health"""

    async def test_health_report_empty(self, client: AsyncClient):
        """Sog'liq yozuvlari yo'q bo'lganda."""
        r = await client.post("/api/v1/reports/health")
        assert r.status_code in (200, 201)

    async def test_health_report_with_animals(self, client: AsyncClient, sample_animals):
        """Jonivorlar bilan sog'liq hisoboti."""
        r = await client.post("/api/v1/reports/health")
        assert r.status_code in (200, 201)

    async def test_health_report_date_range(self, client: AsyncClient, sample_animals):
        """Sana oralig'i bilan."""
        r = await client.post(
            "/api/v1/reports/health",
            json={"date_from": "2024-01-01", "date_to": "2026-12-31"},
        )
        assert r.status_code in (200, 201, 422)


class TestReportPreview:
    """GET /api/v1/reports/preview/{report_id}"""

    async def test_preview_not_found(self, client: AsyncClient):
        """Mavjud bo'lmagan hisobot — 404."""
        r = await client.get("/api/v1/reports/preview/nonexistent-report-id-xyz")
        assert r.status_code == 404