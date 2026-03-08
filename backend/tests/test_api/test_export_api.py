"""
Taurus Vision — Export API Tests (TO'LIQ VERSIYA)
/api/v1/export/ barcha endpointlarini to'liq test qiladi.

TUZATILDI: POST so'rovlarda to'g'ri body berildi (oldingi versiya body bermay 422 olardi).
"""
import pytest
from datetime import date, timedelta
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}
TODAY      = date.today().isoformat()
LAST_WEEK  = (date.today() - timedelta(days=7)).isoformat()
FAR_PAST   = (date.today() - timedelta(days=400)).isoformat()


class TestExportAuthGuard:
    async def test_animals_csv_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/export/animals/csv", json={})
        assert r.status_code == 401

    async def test_animals_excel_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/export/animals/excel")
        assert r.status_code == 401

    async def test_detections_csv_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/export/detections/csv", json={"date_from": LAST_WEEK, "date_to": TODAY})
        assert r.status_code == 401

    async def test_weights_excel_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/export/weights/excel", json={})
        assert r.status_code == 401

    async def test_all_excel_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/export/all/excel")
        assert r.status_code == 401


class TestExportTemplates:
    async def test_get_templates(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/export/templates", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "templates" in data
        assert len(data["templates"]) >= 4

    async def test_templates_have_required_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/export/templates", headers=H(admin_token))
        for tpl in r.json()["templates"]:
            assert "name" in tpl
            assert "endpoint" in tpl
            assert "method" in tpl


class TestExportAnimalsCSV:
    async def test_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token), json={})
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")

    async def test_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token), json={})
        assert r.status_code == 200
        assert len(r.text) > 0

    async def test_filter_status(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token), json={"status": "active"})
        assert r.status_code == 200

    async def test_filter_species(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token), json={"species": "cattle"})
        assert r.status_code == 200

    async def test_filter_combined(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token),
                              json={"status": "active", "species": "cattle", "gender": "female"})
        assert r.status_code == 200

    async def test_content_disposition(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/animals/csv", headers=H(admin_token), json={})
        assert "attachment" in r.headers.get("content-disposition", "")
        assert ".csv" in r.headers.get("content-disposition", "")

    async def test_viewer_can_export(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/export/animals/csv", headers=H(viewer_token), json={})
        assert r.status_code == 200


class TestExportAnimalsExcel:
    async def test_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/export/animals/excel", headers=H(admin_token))
        assert r.status_code == 200
        assert len(r.content) > 0

    async def test_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.get("/api/v1/export/animals/excel", headers=H(admin_token))
        assert r.status_code == 200

    async def test_filter_status_query(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.get("/api/v1/export/animals/excel?status=active", headers=H(admin_token))
        assert r.status_code == 200

    async def test_filter_combined_query(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.get("/api/v1/export/animals/excel?status=active&species=cattle", headers=H(admin_token))
        assert r.status_code == 200

    async def test_content_disposition_xlsx(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/export/animals/excel", headers=H(admin_token))
        assert "attachment" in r.headers.get("content-disposition", "")
        assert ".xlsx" in r.headers.get("content-disposition", "")


class TestExportDetectionsCSV:
    async def test_valid_range(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": LAST_WEEK, "date_to": TODAY})
        assert r.status_code == 200

    async def test_missing_date_from(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_to": TODAY})
        assert r.status_code == 422

    async def test_missing_date_to(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": LAST_WEEK})
        assert r.status_code == 422

    async def test_inverted_date_range(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": TODAY, "date_to": LAST_WEEK})
        assert r.status_code == 422

    async def test_over_365_days(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": FAR_PAST, "date_to": TODAY})
        assert r.status_code == 400

    async def test_with_animal_filter(self, client: AsyncClient, admin_token: str, sample_detection):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": LAST_WEEK, "date_to": TODAY,
                                    "animal_id": sample_detection.animal_id})
        assert r.status_code == 200

    async def test_with_detection_data(self, client: AsyncClient, admin_token: str, sample_detection):
        r = await client.post("/api/v1/export/detections/csv", headers=H(admin_token),
                              json={"date_from": LAST_WEEK, "date_to": TODAY})
        assert r.status_code == 200


class TestExportWeightsExcel:
    async def test_all_animals(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token), json={})
        assert r.status_code == 200

    async def test_specific_animal(self, client: AsyncClient, admin_token: str, sample_weight):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token),
                              json={"animal_ids": [sample_weight.animal_id]})
        assert r.status_code == 200

    async def test_empty_list_rejected(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token),
                              json={"animal_ids": []})
        assert r.status_code == 422

    async def test_negative_id_rejected(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/export/weights/excel", headers=H(admin_token),
                              json={"animal_ids": [-1]})
        assert r.status_code == 422


class TestExportAllExcel:
    async def test_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/export/all/excel", headers=H(admin_token))
        assert r.status_code == 200

    async def test_with_data(self, client: AsyncClient, admin_token: str, sample_animals, sample_weight):
        r = await client.get("/api/v1/export/all/excel", headers=H(admin_token))
        assert r.status_code == 200
        assert len(r.content) > 0

    async def test_viewer_allowed(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/export/all/excel", headers=H(viewer_token))
        assert r.status_code == 200
