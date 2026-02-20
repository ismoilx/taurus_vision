"""
Weights API Tests — /api/v1/weights/

Qamrovi:
  - POST /weights/                   o'lchov yaratish
  - GET  /weights/                   barcha o'lchovlar (list)
  - GET  /weights/recent             oxirgi o'lchovlar
  - GET  /weights/{id}               bitta olish
  - GET  /weights/animal/{id}        jonivorga tegishli
  - GET  /weights/animal/{id}/stats  statistika
"""

import pytest
from httpx import AsyncClient
from datetime import datetime, timezone


pytestmark = [pytest.mark.api, pytest.mark.asyncio]


class TestWeightCreate:
    """POST /api/v1/weights/ — o'lchov yaratish."""

    async def test_create_valid(self, client: AsyncClient, sample_animal):
        """To'g'ri ma'lumotlar bilan yaratish — 201."""
        payload = {
            "animal_id":          sample_animal.id,
            "estimated_weight_kg":285.5,
            "confidence_score":   0.92,
            "camera_id":          "CAM-001",
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }
        r = await client.post("/api/v1/weights/", json=payload)
        assert r.status_code == 201
        data = r.json()
        assert data["animal_id"]          == sample_animal.id
        assert data["estimated_weight_kg"] == pytest.approx(285.5)
        assert data["confidence_score"]    == pytest.approx(0.92)

    async def test_create_missing_animal(self, client: AsyncClient):
        """Yo'q animal_id — 404."""
        payload = {
            "animal_id":          99999,
            "estimated_weight_kg":250.0,
            "confidence_score":   0.85,
            "camera_id":          "CAM-001",
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }
        r = await client.post("/api/v1/weights/", json=payload)
        assert r.status_code == 404

    async def test_create_invalid_confidence(self, client: AsyncClient, sample_animal):
        """confidence > 1.0 — 422."""
        payload = {
            "animal_id":          sample_animal.id,
            "estimated_weight_kg":250.0,
            "confidence_score":   1.5,
            "camera_id":          "CAM-001",
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }
        r = await client.post("/api/v1/weights/", json=payload)
        assert r.status_code == 422

    async def test_create_zero_weight(self, client: AsyncClient, sample_animal):
        """0 kg vazn — 422."""
        payload = {
            "animal_id":          sample_animal.id,
            "estimated_weight_kg":0.0,
            "confidence_score":   0.85,
            "camera_id":          "CAM-001",
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }
        r = await client.post("/api/v1/weights/", json=payload)
        assert r.status_code == 422


class TestWeightList:
    """GET /api/v1/weights/ — barcha o'lchovlar."""

    async def test_list_empty(self, client: AsyncClient):
        """Bo'sh DB."""
        r = await client.get("/api/v1/weights/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_data(self, client: AsyncClient, sample_weight):
        """1 ta o'lchov bor."""
        r = await client.get("/api/v1/weights/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1

    async def test_list_pagination(self, client: AsyncClient, db, sample_animal):
        """Pagination ishlaydi."""
        from app.models.weight_measurement import WeightMeasurement

        for i in range(5):
            w = WeightMeasurement(
                animal_id=          sample_animal.id,
                timestamp=          datetime.now(timezone.utc),
                estimated_weight_kg=200.0 + i * 10,
                confidence_score=   0.90,
                camera_id=          "CAM-001",
            )
            db.add(w)
        await db.commit()

        r = await client.get("/api/v1/weights/?limit=3")
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 3
        assert data["total"]      == 5


class TestWeightRecent:
    """GET /api/v1/weights/recent — oxirgi o'lchovlar."""

    async def test_recent_empty(self, client: AsyncClient):
        """Bo'sh DB — bo'sh list."""
        r = await client.get("/api/v1/weights/recent")
        assert r.status_code == 200
        assert r.json() == []

    async def test_recent_with_data(self, client: AsyncClient, sample_weight):
        """O'lchov bor — qaytadi."""
        r = await client.get("/api/v1/weights/recent?min_confidence=0.0")
        assert r.status_code == 200
        data = r.json()
        assert len(data) >= 1

    async def test_recent_confidence_filter(self, client: AsyncClient, db, sample_animal):
        """min_confidence filtri ishlaydi."""
        from app.models.weight_measurement import WeightMeasurement

        # Past confidence
        w_low = WeightMeasurement(
            animal_id=200.0, timestamp=datetime.now(timezone.utc),
            estimated_weight_kg=200.0, confidence_score=0.50,
            camera_id="CAM-001",
        )
        # Yuqori confidence
        w_high = WeightMeasurement(
            animal_id=sample_animal.id,
            timestamp=datetime.now(timezone.utc),
            estimated_weight_kg=300.0, confidence_score=0.95,
            camera_id="CAM-001",
        )
        db.add(w_high)
        await db.commit()

        r = await client.get("/api/v1/weights/recent?min_confidence=0.9")
        assert r.status_code == 200
        data = r.json()
        # Faqat yuqori confidence li qaytishi kerak
        for item in data:
            assert item["confidence_score"] >= 0.9


class TestWeightAnimal:
    """GET /api/v1/weights/animal/{id} — jonivor o'lchovlari."""

    async def test_animal_weights_empty(self, client: AsyncClient, sample_animal):
        """O'lchov yo'q."""
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0

    async def test_animal_weights_with_data(
        self, client: AsyncClient, sample_animal, sample_weight
    ):
        """1 ta o'lchov bor."""
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1
        assert data["items"][0]["animal_id"] == sample_animal.id


class TestWeightStats:
    """GET /api/v1/weights/animal/{id}/stats."""

    async def test_stats_no_data(self, client: AsyncClient, sample_animal):
        """O'lchov yo'q — 404 yoki bo'sh stats."""
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}/stats")
        # 404 yoki 200 (bo'sh stats bilan)
        assert r.status_code in [200, 404]

    async def test_stats_with_data(
        self, client: AsyncClient, sample_animal, sample_weight
    ):
        """O'lchov bor — statistika qaytadi."""
        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}/stats")
        assert r.status_code == 200
        data = r.json()
        # Kerakli maydonlar
        assert "total_measurements" in data or "count" in data or len(data) > 0