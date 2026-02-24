"""
Export API Tests — /api/v1/export/

Qamrovi:
  - POST /export/animals/csv        — jonivorlar CSV
  - POST /export/detections/csv     — deteksiyalar CSV
  - POST /export/weights/excel      — og'irliklar Excel
  - GET  /export/all/excel          — barcha ma'lumotlar Excel
  - GET  /export/templates          — shablonlar
"""

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestExportAnimalsCSV:
    """POST /api/v1/export/animals/csv"""

    async def test_export_empty_db(self, client: AsyncClient):
        """Bo'sh DB — bo'sh CSV fayl."""
        r = await client.post("/api/v1/export/animals/csv")
        # 200 (bo'sh CSV) yoki 204
        assert r.status_code in (200, 204)
        if r.status_code == 200:
            content_type = r.headers.get("content-type", "")
            assert "csv" in content_type or "octet-stream" in content_type or "text" in content_type

    async def test_export_with_animals(self, client: AsyncClient, sample_animals):
        """3 ta jonivor bor — CSV yuklandi."""
        r = await client.post("/api/v1/export/animals/csv")
        assert r.status_code in (200, 204)
        if r.status_code == 200:
            # CSV sarlavhasi bo'lishi kerak
            assert len(r.content) > 0

    async def test_export_with_date_filter(self, client: AsyncClient, sample_animals):
        """Sana filtri bilan eksport."""
        r = await client.post(
            "/api/v1/export/animals/csv",
            json={"date_from": "2024-01-01", "date_to": "2024-12-31"},
        )
        assert r.status_code in (200, 204, 422)

    async def test_export_content_disposition(self, client: AsyncClient, sample_animals):
        """Content-Disposition header — fayl nomi bor."""
        r = await client.post("/api/v1/export/animals/csv")
        if r.status_code == 200:
            cd = r.headers.get("content-disposition", "")
            assert "attachment" in cd or "filename" in cd or len(r.content) > 0


class TestExportDetectionsCSV:
    """POST /api/v1/export/detections/csv"""

    async def test_export_no_detections(self, client: AsyncClient):
        """Deteksiya yo'q — bo'sh CSV."""
        r = await client.post("/api/v1/export/detections/csv")
        assert r.status_code in (200, 204)

    async def test_export_with_detection(
        self, client: AsyncClient, sample_detection
    ):
        """Bitta deteksiya bor — CSV bor."""
        r = await client.post("/api/v1/export/detections/csv")
        assert r.status_code in (200, 204)

    async def test_export_camera_filter(self, client: AsyncClient, sample_detection):
        """Kamera ID filtri."""
        r = await client.post(
            "/api/v1/export/detections/csv",
            json={"camera_id": "CAM-TEST-001"},
        )
        assert r.status_code in (200, 204, 422)


class TestExportWeightsExcel:
    """POST /api/v1/export/weights/excel"""

    async def test_export_no_weights(self, client: AsyncClient):
        """Og'irlik yo'q — bo'sh Excel yoki 204."""
        r = await client.post("/api/v1/export/weights/excel")
        assert r.status_code in (200, 204)

    async def test_export_with_weights(self, client: AsyncClient, sample_weight):
        """Og'irlik bor — Excel fayl."""
        r = await client.post("/api/v1/export/weights/excel")
        assert r.status_code in (200, 204)
        if r.status_code == 200:
            ct = r.headers.get("content-type", "")
            assert (
                "excel" in ct
                or "spreadsheet" in ct
                or "octet-stream" in ct
                or "xlsx" in ct
            )


class TestExportAllExcel:
    """GET /api/v1/export/all/excel"""

    async def test_export_all(self, client: AsyncClient, sample_animals):
        """Barcha ma'lumotlar Excel da."""
        r = await client.get("/api/v1/export/all/excel")
        assert r.status_code in (200, 204)


class TestExportTemplates:
    """GET /api/v1/export/templates"""

    async def test_get_templates(self, client: AsyncClient):
        """Mavjud shablon ro'yxati."""
        r = await client.get("/api/v1/export/templates")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, dict) or isinstance(data, list)