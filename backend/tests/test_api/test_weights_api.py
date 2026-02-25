"""Weights API Tests — /api/v1/weights/"""
import pytest
from httpx import AsyncClient
from datetime import datetime, timezone

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

H = lambda t: {"Authorization": f"Bearer {t}"}
NOW = lambda: datetime.now(timezone.utc).isoformat()


class TestWeightCreate:
    async def test_create_valid(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            "/api/v1/weights/",
            headers=H(admin_token),
            json={"animal_id": sample_animal.id, "estimated_weight_kg": 285.5, "confidence_score": 0.92, "camera_id": "CAM-001", "timestamp": NOW()},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["animal_id"] == sample_animal.id
        assert data["estimated_weight_kg"] == pytest.approx(285.5)

    async def test_create_missing_animal(self, client: AsyncClient, admin_token: str):
        r = await client.post(
            "/api/v1/weights/",
            headers=H(admin_token),
            json={"animal_id": 99999, "estimated_weight_kg": 250.0, "confidence_score": 0.85, "camera_id": "CAM-001", "timestamp": NOW()},
        )
        assert r.status_code == 404

    async def test_create_invalid_confidence(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            "/api/v1/weights/",
            headers=H(admin_token),
            json={"animal_id": sample_animal.id, "estimated_weight_kg": 250.0, "confidence_score": 1.5, "camera_id": "CAM-001", "timestamp": NOW()},
        )
        assert r.status_code == 422

    async def test_create_zero_weight(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.post(
            "/api/v1/weights/",
            headers=H(admin_token),
            json={"animal_id": sample_animal.id, "estimated_weight_kg": 0.0, "confidence_score": 0.85, "camera_id": "CAM-001", "timestamp": NOW()},
        )
        assert r.status_code == 422

    async def test_no_token(self, client: AsyncClient, sample_animal):
        r = await client.post("/api/v1/weights/", json={"animal_id": sample_animal.id, "estimated_weight_kg": 285.5, "confidence_score": 0.9, "camera_id": "CAM-001", "timestamp": NOW()})
        assert r.status_code == 401


class TestWeightList:
    async def test_list_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/weights/", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_data(self, client: AsyncClient, admin_token: str, sample_weight):
        r = await client.get("/api/v1/weights/", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["total"] == 1

    async def test_list_pagination(self, client: AsyncClient, admin_token: str, db, sample_animal):
        from app.models.weight_measurement import WeightMeasurement
        for i in range(5):
            db.add(WeightMeasurement(animal_id=sample_animal.id, timestamp=datetime.now(timezone.utc), estimated_weight_kg=200.0 + i * 10, confidence_score=0.90, camera_id="CAM-001"))
        await db.commit()
        r = await client.get("/api/v1/weights/?limit=3", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 3
        assert data["total"] == 5


class TestWeightRecent:
    async def test_recent_empty(self, client: AsyncClient, admin_token: str):
        r = await client.get("/api/v1/weights/recent", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json() == []

    async def test_recent_with_data(self, client: AsyncClient, admin_token: str, sample_weight):
        r = await client.get("/api/v1/weights/recent?min_confidence=0.0", headers=H(admin_token))
        assert r.status_code == 200
        assert len(r.json()) >= 1


class TestWeightAnimal:
    async def test_animal_weights_empty(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["total"] == 0

    async def test_animal_weights_with_data(self, client: AsyncClient, admin_token: str, sample_animal, sample_weight):
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["total"] == 1


class TestWeightStats:
    async def test_stats_no_data(self, client: AsyncClient, admin_token: str, sample_animal):
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}/stats", headers=H(admin_token))
        assert r.status_code in (200, 404)

    async def test_stats_with_data(self, client: AsyncClient, admin_token: str, sample_animal, sample_weight):
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}/stats", headers=H(admin_token))
        assert r.status_code == 200
        data = r.json()
        assert "total_measurements" in data or "count" in data or len(data) > 0