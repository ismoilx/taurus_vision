"""
Animals API Tests — /api/v1/animals/

Qamrovi:
  - GET  /animals/                  list + pagination + filter
  - POST /animals/                  yaratish
  - GET  /animals/{id}              bitta olish
  - PATCH /animals/{id}             yangilash
  - DELETE /animals/{id}            o'chirish
  - GET  /animals/{id}/detections   detection tarixi

O'ZGARISHLAR (bugfix):
  - Barcha so'rovlarga Authorization header qo'shildi
  - conftest.py dagi admin_token fixture ishlatiladi
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


# =============================================================================
# LIST
# =============================================================================

class TestAnimalsList:
    """GET /api/v1/animals/ — ro'yxat va pagination."""

    async def test_list_empty(self, client: AsyncClient, admin_token: str):
        """Bo'sh DB — bo'sh list."""
        r = await client.get(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0
        assert data["items"] == []

    async def test_list_with_animals(
        self, client: AsyncClient, admin_token: str, sample_animals
    ):
        """3 ta jonivor mavjud — 3 ta qaytadi."""
        r = await client.get(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 3
        assert len(data["items"]) == 3

    async def test_list_pagination(
        self, client: AsyncClient, admin_token: str, sample_animals
    ):
        """limit=2 — faqat 2 ta qaytadi, total=3."""
        r = await client.get(
            "/api/v1/animals/?limit=2&skip=0",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data["items"]) == 2
        assert data["total"] == 3

    async def test_list_filter_species(
        self, client: AsyncClient, admin_token: str, sample_animals
    ):
        """Species filtri — cattle 2 ta, goat 1 ta."""
        r = await client.get(
            "/api/v1/animals/?species=cattle",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["total"] == 2

        r2 = await client.get(
            "/api/v1/animals/?species=goat",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["total"] == 1

    async def test_list_no_token(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.get("/api/v1/animals/")
        assert r.status_code == 401


# =============================================================================
# CREATE
# =============================================================================

class TestAnimalCreate:
    """POST /api/v1/animals/ — jonivor yaratish."""

    async def test_create_valid(self, client: AsyncClient, admin_token: str):
        """To'g'ri ma'lumotlar bilan yaratish."""
        r = await client.post(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tag_id":  "NEW-TAG-001",
                "species": "cattle",
                "gender":  "female",
                "status":  "active",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["tag_id"]  == "NEW-TAG-001"
        assert data["species"] == "cattle"
        assert data["id"]      > 0

    async def test_create_duplicate_tag(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Bir xil tag_id — 409 Conflict."""
        r = await client.post(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tag_id":  sample_animal.tag_id,
                "species": "cattle",
                "gender":  "female",
                "status":  "active",
            },
        )
        assert r.status_code == 409

    async def test_create_invalid_species(
        self, client: AsyncClient, admin_token: str
    ):
        """Noto'g'ri species — 422."""
        r = await client.post(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "tag_id":  "INVALID-001",
                "species": "dragon",
                "gender":  "female",
                "status":  "active",
            },
        )
        assert r.status_code == 422

    async def test_create_missing_required_field(
        self, client: AsyncClient, admin_token: str
    ):
        """Majburiy maydon yo'q — 422."""
        r = await client.post(
            "/api/v1/animals/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"tag_id": "X"},
        )
        assert r.status_code == 422

    async def test_create_no_token(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.post(
            "/api/v1/animals/",
            json={"tag_id": "X", "species": "cattle", "gender": "female", "status": "active"},
        )
        assert r.status_code == 401


# =============================================================================
# GET SINGLE
# =============================================================================

class TestAnimalGet:
    """GET /api/v1/animals/{id}."""

    async def test_get_existing(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Mavjud jonivor — 200 + to'g'ri ma'lumot."""
        r = await client.get(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["id"]     == sample_animal.id
        assert data["tag_id"] == sample_animal.tag_id

    async def test_get_nonexistent(self, client: AsyncClient, admin_token: str):
        """Yo'q ID — 404."""
        r = await client.get(
            "/api/v1/animals/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_get_response_fields(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Javob barcha kerakli maydonlarni o'z ichiga oladi."""
        r = await client.get(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        required = ["id", "tag_id", "species", "gender", "status",
                    "total_detections", "last_detected_at"]
        for field in required:
            assert field in data, f"'{field}' maydoni yo'q"

    async def test_get_no_token(self, client: AsyncClient, sample_animal):
        """Token yo'q — 401."""
        r = await client.get(f"/api/v1/animals/{sample_animal.id}")
        assert r.status_code == 401


# =============================================================================
# UPDATE
# =============================================================================

class TestAnimalUpdate:
    """PATCH /api/v1/animals/{id}."""

    async def test_update_status(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Status yangilash."""
        r = await client.patch(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "quarantine"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "quarantine"

    async def test_update_notes(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Notes qo'shish."""
        r = await client.patch(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"notes": "Sinov eslatmasi"},
        )
        assert r.status_code == 200
        assert r.json()["notes"] == "Sinov eslatmasi"

    async def test_update_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q ID — 404."""
        r = await client.patch(
            "/api/v1/animals/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"status": "active"},
        )
        assert r.status_code == 404

    async def test_update_no_token(self, client: AsyncClient, sample_animal):
        """Token yo'q — 401."""
        r = await client.patch(
            f"/api/v1/animals/{sample_animal.id}",
            json={"status": "active"},
        )
        assert r.status_code == 401


# =============================================================================
# DELETE
# =============================================================================

class TestAnimalDelete:
    """DELETE /api/v1/animals/{id}."""

    async def test_delete_existing(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Mavjud jonivorni o'chirish — 204."""
        r = await client.delete(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 204

        # Keyin yana so'rasak 404
        r2 = await client.get(
            f"/api/v1/animals/{sample_animal.id}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 404

    async def test_delete_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q ID — 404."""
        r = await client.delete(
            "/api/v1/animals/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_delete_no_token(self, client: AsyncClient, sample_animal):
        """Token yo'q — 401."""
        r = await client.delete(f"/api/v1/animals/{sample_animal.id}")
        assert r.status_code == 401


# =============================================================================
# DETECTIONS
# =============================================================================

class TestAnimalDetections:
    """GET /api/v1/animals/{id}/detections."""

    async def test_detections_empty(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Detection yo'q — bo'sh list."""
        r = await client.get(
            f"/api/v1/animals/{sample_animal.id}/detections",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json() == []

    async def test_detections_with_data(
        self, client: AsyncClient, admin_token: str,
        sample_animal, sample_detection,
    ):
        """1 ta detection bor — 1 ta qaytadi."""
        r = await client.get(
            f"/api/v1/animals/{sample_animal.id}/detections",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        assert data[0]["confidence"] == pytest.approx(0.92, abs=0.01)
        assert data[0]["camera_id"] == "CAM-TEST-001"

    async def test_detections_limit(
        self, client: AsyncClient, admin_token: str, db, sample_animal
    ):
        """limit parametri ishlaydi."""
        from app.models.detection import Detection
        from datetime import datetime, timezone

        for _ in range(5):
            d = Detection(
                animal_id=  sample_animal.id,
                camera_id=  "CAM-001",
                timestamp=  datetime.now(timezone.utc),
                confidence= 0.85,
                class_id=   19,
                class_name= "cow",
                bbox=       {"x": 0.3, "y": 0.2, "w": 0.25, "h": 0.35},
            )
            db.add(d)
        await db.commit()

        r = await client.get(
            f"/api/v1/animals/{sample_animal.id}/detections?limit=3",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert len(r.json()) == 3