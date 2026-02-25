"""Export API Tests — /api/v1/export/"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}


class TestExportAnimalsCSV:
    async def test_export_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_export_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/export/animals/csv")
        assert r.status_code == 401


class TestExportDetectionsCSV:
    async def test_export_no_detections(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_export_with_detection(self, client: AsyncClient, admin_token: str, sample_detection):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token))
        assert r.status_code in (200, 204)


class TestExportWeightsExcel:
    async def test_export_no_weights(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_export_with_weights(self, client: AsyncClient, admin_token: str, sample_weight):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token))
        assert r.status_code in (200, 204)


class TestExportAllExcel:
    async def test_export_all(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.get("/api/v1/export/all/excel", headers=H(admin_token))
        assert r.status_code in (200, 204)


class TestExportTemplates:
    async def test_get_templates(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/export/templates", headers=H(admin_token))
        assert r.status_code == 200
        assert isinstance(r.json(), (dict, list))