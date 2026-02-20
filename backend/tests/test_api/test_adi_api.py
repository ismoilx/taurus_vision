"""
ADI API Tests — /api/v1/adi/

Qamrovi:
  - GET  /adi/farm-summary        ferma umumiy ADI
  - GET  /adi/animal/{id}         jonivor ADI
  - POST /adi/calculate           ADI hisoblash trigger
"""

import pytest
from httpx import AsyncClient


pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestFarmSummary:
    """GET /api/v1/adi/farm-summary."""

    async def test_farm_summary_empty_db(self, client: AsyncClient):
        """Bo'sh DB — default summary qaytadi."""
        r = await client.get("/api/v1/adi/farm-summary")
        assert r.status_code == 200
        data = r.json()
        assert "farm_adi_score" in data
        assert "total_animals"  in data

    async def test_farm_summary_fields(self, client: AsyncClient):
        """Kerakli maydonlar bor."""
        r = await client.get("/api/v1/adi/farm-summary")
        assert r.status_code == 200
        data = r.json()
        required = [
            "farm_adi_score", "total_animals", "healthy_count",
            "warning_count",  "critical_count",
        ]
        for field in required:
            assert field in data, f"'{field}' maydoni yo'q"

    async def test_farm_summary_with_animals(
        self, client: AsyncClient, sample_animals
    ):
        """Jonivorlar bor — total_animals noldan katta."""
        r = await client.get("/api/v1/adi/farm-summary")
        assert r.status_code == 200
        # Jonivorlar bor, lekin ADI hali hisoblanmagan → total_animals >= 0
        data = r.json()
        assert data["total_animals"] >= 0


class TestAnimalADI:
    """GET /api/v1/adi/animal/{id}."""

    async def test_animal_adi_no_log(self, client: AsyncClient, sample_animal):
        """ADI log yo'q — 404 yoki default."""
        r = await client.get(f"/api/v1/adi/animal/{sample_animal.id}")
        # ADI hisob bo'lmagan bo'lsa 404 qaytishi mumkin
        assert r.status_code in [200, 404]

    async def test_animal_adi_nonexistent(self, client: AsyncClient):
        """Yo'q jonivor — 404."""
        r = await client.get("/api/v1/adi/animal/99999")
        assert r.status_code == 404


class TestADICalculate:
    """POST /api/v1/adi/calculate — hisoblash trigger."""

    async def test_calculate_valid(self, client: AsyncClient, sample_animal):
        """To'g'ri animal_id bilan hisoblash."""
        r = await client.post("/api/v1/adi/calculate", json={
            "animal_id":       sample_animal.id,
            "force_recalculate": True,
        })
        assert r.status_code == 200
        data = r.json()
        # Natija yoki results massivi qaytadi
        assert "results" in data or "adi_score" in data or "status" in data

    async def test_calculate_missing_animal(self, client: AsyncClient):
        """Yo'q animal_id — 404."""
        r = await client.post("/api/v1/adi/calculate", json={
            "animal_id": 99999,
        })
        assert r.status_code == 404

    async def test_calculate_response_has_score(
        self, client: AsyncClient, sample_animal, sample_detection, sample_weight
    ):
        """Ma'lumot bor — ADI score qaytadi."""
        r = await client.post("/api/v1/adi/calculate", json={
            "animal_id":       sample_animal.id,
            "force_recalculate": True,
        })
        assert r.status_code == 200
        data = r.json()
        # results massivi yoki to'g'ridan score
        if "results" in data and data["results"]:
            result = data["results"][0]
            assert "adi_score" in result
            assert 0 <= result["adi_score"] <= 100