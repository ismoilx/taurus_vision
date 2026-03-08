"""
Taurus Vision — Milk Production API Tests
/api/v1/milk/ barcha endpointlarini test qiladi.
"""
import pytest
from datetime import date
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]
H = lambda t: {"Authorization": f"Bearer {t}"}

@pytest.fixture
async def sample_milk_record(db: AsyncSession, sample_animal):
    from app.models.milk_production import MilkProduction, MilkSession
    rec = MilkProduction(
        animal_id=sample_animal.id,
        record_date=date.today(),
        session=MilkSession.MORNING,
        milk_kg=12.5,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


class TestMilkAuthGuard:
    async def test_create_no_token(self, client: AsyncClient, sample_animal):
        r = await client.post("/api/v1/milk/", json={
            "animal_id": 1, "record_date": str(date.today()), "milk_kg": 10.0
        })
        assert r.status_code == 401

    async def test_list_no_token(self, client: AsyncClient, sample_animal):
        r = await client.get("/api/v1/milk/animal/1")
        assert r.status_code == 401


class TestMilkCreate:
    async def test_create_minimal(self, client: AsyncClient, manager_token: str, sample_animal):
        r = await client.post("/api/v1/milk/", headers=H(manager_token), json={
            "animal_id": sample_animal.id,
            "record_date": str(date.today()),
            "session": "morning",
            "milk_kg": 12.5,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["milk_kg"] == 12.5
        assert data["animal_id"] == sample_animal.id

    async def test_create_full(self, client: AsyncClient, manager_token: str, sample_animal):
        r = await client.post("/api/v1/milk/", headers=H(manager_token), json={
            "animal_id": sample_animal.id,
            "record_date": str(date.today()),
            "session": "evening",
            "milk_kg": 8.3,
            "fat_percent": 3.8,
            "protein_percent": 3.2,
            "quality_grade": "grade_a",
            "milked_by": "Sardor",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["fat_percent"] == 3.8

    async def test_create_zero_milk_rejected(self, client: AsyncClient, manager_token: str, sample_animal):
        """milk_kg > 0 bo'lishi kerak."""
        r = await client.post("/api/v1/milk/", headers=H(manager_token), json={
            "animal_id": sample_animal.id,
            "record_date": str(date.today()),
            "session": "morning",
            "milk_kg": 0,
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str, sample_animal):
        r = await client.post("/api/v1/milk/", headers=H(viewer_token), json={
            "animal_id": sample_animal.id,
            "record_date": str(date.today()),
            "session": "morning",
            "milk_kg": 10.0,
        })
        assert r.status_code == 403

    async def test_nonexistent_animal(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/milk/", headers=H(manager_token), json={
            "animal_id": 999999,
            "record_date": str(date.today()),
            "session": "morning",
            "milk_kg": 10.0,
        })
        assert r.status_code in (404, 422)


class TestMilkList:
    async def test_list_animal_records(self, client: AsyncClient, viewer_token: str, sample_milk_record):
        r = await client.get(f"/api/v1/milk/animal/{sample_milk_record.animal_id}",
                             headers=H(viewer_token))
        assert r.status_code == 200

    async def test_list_nonexistent_animal(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/milk/animal/999999", headers=H(viewer_token))
        assert r.status_code in (200, 404)

    async def test_animal_summary(self, client: AsyncClient, viewer_token: str, sample_milk_record):
        r = await client.get(f"/api/v1/milk/animal/{sample_milk_record.animal_id}/summary",
                             headers=H(viewer_token))
        assert r.status_code == 200

    async def test_farm_summary(self, client: AsyncClient, viewer_token: str, sample_milk_record):
        r = await client.get("/api/v1/milk/farm/summary", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_daily_trend(self, client: AsyncClient, viewer_token: str, sample_milk_record):
        r = await client.get("/api/v1/milk/farm/daily", headers=H(viewer_token))
        assert r.status_code == 200


class TestMilkUpdateDelete:
    async def test_update_record(self, client: AsyncClient, manager_token: str, sample_milk_record):
        r = await client.put(f"/api/v1/milk/{sample_milk_record.id}", headers=H(manager_token),
                             json={"milk_kg": 15.0})
        assert r.status_code == 200
        assert r.json()["milk_kg"] == 15.0

    async def test_delete_record(self, client: AsyncClient, manager_token: str, sample_milk_record):
        r = await client.delete(f"/api/v1/milk/{sample_milk_record.id}", headers=H(manager_token))
        assert r.status_code in (200, 204)

    async def test_viewer_cannot_delete(self, client: AsyncClient, viewer_token: str, sample_milk_record):
        r = await client.delete(f"/api/v1/milk/{sample_milk_record.id}", headers=H(viewer_token))
        assert r.status_code == 403
