"""
Taurus Vision — Breeding API Tests
/api/v1/breeding/records barcha endpointlarini test qiladi.
"""
import pytest
from datetime import date, datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]
H = lambda t: {"Authorization": f"Bearer {t}"}


@pytest.fixture
async def male_animal(db: AsyncSession):
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
    a = Animal(tag_id="MALE-B01", species=AnimalSpecies.CATTLE, gender=AnimalGender.MALE,
               status=AnimalStatus.ACTIVE, acquisition_date=datetime(2023, 1, 1, tzinfo=timezone.utc))
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def female_animal(db: AsyncSession):
    from app.models.animal import Animal, AnimalSpecies, AnimalGender, AnimalStatus
    a = Animal(tag_id="FEMALE-B01", species=AnimalSpecies.CATTLE, gender=AnimalGender.FEMALE,
               status=AnimalStatus.ACTIVE, acquisition_date=datetime(2023, 1, 1, tzinfo=timezone.utc))
    db.add(a); await db.commit(); await db.refresh(a); return a


@pytest.fixture
async def sample_breeding(db: AsyncSession, male_animal, female_animal):
    from app.models.breeding import BreedingRecord, BreedingMethod, BreedingStatus
    rec = BreedingRecord(
        dam_id=female_animal.id, sire_id=male_animal.id,
        breeding_date=date.today(), method=BreedingMethod.NATURAL,
        status=BreedingStatus.PENDING,
    )
    db.add(rec); await db.commit(); await db.refresh(rec); return rec


class TestBreedingAuthGuard:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/breeding/records")
        assert r.status_code == 401

    async def test_create_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/breeding/records", json={})
        assert r.status_code == 401

    async def test_stats_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/breeding/stats")
        assert r.status_code == 401


class TestBreedingCreate:
    async def test_create_natural(self, client: AsyncClient, manager_token: str, male_animal, female_animal):
        r = await client.post("/api/v1/breeding/records", headers=H(manager_token), json={
            "dam_id": female_animal.id,
            "sire_id": male_animal.id,
            "breeding_date": str(date.today()),
            "method": "natural",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["dam_id"] == female_animal.id
        assert data["sire_id"] == male_animal.id
        assert "id" in data

    async def test_create_ai_method(self, client: AsyncClient, manager_token: str, female_animal):
        """Artificial insemination — sire_id ixtiyoriy."""
        r = await client.post("/api/v1/breeding/records", headers=H(manager_token), json={
            "dam_id": female_animal.id,
            "breeding_date": str(date.today()),
            "method": "artificial_insemination",
        })
        assert r.status_code == 201

    async def test_create_missing_dam_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/breeding/records", headers=H(manager_token), json={
            "breeding_date": str(date.today()),
            "method": "natural",
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str, male_animal, female_animal):
        r = await client.post("/api/v1/breeding/records", headers=H(viewer_token), json={
            "dam_id": female_animal.id,
            "sire_id": male_animal.id,
            "breeding_date": str(date.today()),
            "method": "natural",
        })
        assert r.status_code == 403


class TestBreedingList:
    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/breeding/records", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_list_with_data(self, client: AsyncClient, viewer_token: str, sample_breeding):
        r = await client.get("/api/v1/breeding/records", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_active_pregnancies(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/breeding/active-pregnancies", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_stats(self, client: AsyncClient, viewer_token: str, sample_breeding):
        r = await client.get("/api/v1/breeding/stats", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_available_females(self, client: AsyncClient, viewer_token: str, female_animal):
        r = await client.get("/api/v1/breeding/available-females", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_available_males(self, client: AsyncClient, viewer_token: str, male_animal):
        r = await client.get("/api/v1/breeding/available-males", headers=H(viewer_token))
        assert r.status_code == 200


class TestBreedingDetail:
    async def test_get_existing(self, client: AsyncClient, viewer_token: str, sample_breeding):
        r = await client.get(f"/api/v1/breeding/records/{sample_breeding.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_breeding.id

    async def test_get_nonexistent(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/breeding/records/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_update_notes(self, client: AsyncClient, manager_token: str, sample_breeding):
        r = await client.patch(f"/api/v1/breeding/records/{sample_breeding.id}",
                               headers=H(manager_token), json={"notes": "Yaxshi natija"})
        assert r.status_code == 200

    async def test_delete(self, client: AsyncClient, admin_token: str, sample_breeding):
        r = await client.delete(f"/api/v1/breeding/records/{sample_breeding.id}", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_mark_failed(self, client: AsyncClient, manager_token: str, sample_breeding):
        r = await client.post(f"/api/v1/breeding/records/{sample_breeding.id}/mark-failed",
                              headers=H(manager_token), json={})
        assert r.status_code == 200

    async def test_genealogy(self, client: AsyncClient, viewer_token: str, female_animal):
        r = await client.get(f"/api/v1/breeding/genealogy/{female_animal.id}", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_animal_history(self, client: AsyncClient, viewer_token: str, female_animal, sample_breeding):
        r = await client.get(f"/api/v1/breeding/animals/{female_animal.id}/history",
                             headers=H(viewer_token))
        assert r.status_code == 200
