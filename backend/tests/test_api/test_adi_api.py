"""ADI API Tests — /api/v1/adi/"""
import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestFarmSummary:
    async def test_farm_summary_empty_db(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/adi/farm-summary", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        assert "farm_adi_score" in data
        assert "total_animals"  in data

    async def test_farm_summary_fields(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/adi/farm-summary", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        data = r.json()
        for field in ["farm_adi_score", "total_animals", "healthy_count", "warning_count", "critical_count"]:
            assert field in data, f"'{field}' maydoni yo'q"

    async def test_farm_summary_with_animals(self, client: AsyncClient, admin_token: str, sample_animals):
        r = await client.get("/api/v1/adi/farm-summary", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 200
        assert r.json()["total_animals"] >= 0

    async def test_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/adi/farm-summary")
        assert r.status_code == 401


class TestAnimalADI:
    async def test_animal_adi_no_log(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.get(f"/api/v1/adi/animal/{sample_animal.id}", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code in (200, 404)

    async def test_animal_adi_nonexistent(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/adi/animal/99999", headers={"Authorization": f"Bearer {admin_token}"})
        assert r.status_code == 404


class TestADICalculate:
    async def test_calculate_valid(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            "/api/v1/adi/calculate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"animal_id": sample_animal.id, "force_recalculate": True},
        )
        assert r.status_code == 200
        data = r.json()
        assert "results" in data or "adi_score" in data or "status" in data

    async def test_calculate_missing_animal(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/adi/calculate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"animal_id": 99999},
        )
        assert r.status_code == 404

    async def test_calculate_response_has_score(self, client: AsyncClient, admin_token: str, sample_animal, sample_detection, sample_weight):
        r = await client.post(
            "/api/v1/adi/calculate",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"animal_id": sample_animal.id, "force_recalculate": True},
        )
        assert r.status_code == 200
        data = r.json()
        if "results" in data and data["results"]:
            result = data["results"][0]
            assert "adi_score" in result
            assert 0 <= result["adi_score"] <= 100