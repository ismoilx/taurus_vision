"""
Taurus Vision — Medicine API Tests
/api/v1/medicine/ barcha endpointlarini test qiladi.
"""
import pytest
from datetime import date, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]
H = lambda t: {"Authorization": f"Bearer {t}"}
FUTURE = (date.today() + timedelta(days=365)).isoformat()


@pytest.fixture
async def sample_medicine(db: AsyncSession):
    from app.models.medicine import MedicineInventory, MedicineType, MedicineUnit
    med = MedicineInventory(
        name="Test Dori",
        medicine_type=MedicineType.ANTIBIOTIC,
        quantity=100.0,
        unit=MedicineUnit.ML,
        min_stock_quantity=10.0,
    )
    db.add(med)
    await db.commit()
    await db.refresh(med)
    return med


class TestMedicineAuthGuard:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/medicine/")
        assert r.status_code == 401

    async def test_create_no_token(self, client: AsyncClient):
        r = await client.post("/api/v1/medicine/", json={})
        assert r.status_code == 401


class TestMedicineCategories:
    async def test_get_categories(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/categories", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_summary(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/summary", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_low_stock(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/low-stock", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_expiring(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/expiring", headers=H(viewer_token))
        assert r.status_code == 200


class TestMedicineList:
    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_list_with_data(self, client: AsyncClient, viewer_token: str, sample_medicine):
        r = await client.get("/api/v1/medicine/", headers=H(viewer_token))
        assert r.status_code == 200


class TestMedicineCreate:
    async def test_create_minimal(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/medicine/", headers=H(manager_token), json={
            "name": "Yangi Dori",
            "medicine_type": "antibiotic",
            "quantity": 50.0,
            "unit": "ml",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Yangi Dori"

    async def test_create_with_expiry(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/medicine/", headers=H(manager_token), json={
            "name": "Muddatli Dori",
            "medicine_type": "vaccine",
            "quantity": 200.0,
            "unit": "ml",
            "expiry_date": FUTURE,
        })
        assert r.status_code == 201

    async def test_create_short_name_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/medicine/", headers=H(manager_token), json={
            "name": "A",
            "medicine_type": "antibiotic",
            "quantity": 10.0,
            "unit": "ml",
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/medicine/", headers=H(viewer_token), json={
            "name": "Test Dori",
            "medicine_type": "antibiotic",
            "quantity": 10.0,
            "unit": "ml",
        })
        assert r.status_code == 403


class TestMedicineDetail:
    async def test_get_existing(self, client: AsyncClient, viewer_token: str, sample_medicine):
        r = await client.get(f"/api/v1/medicine/{sample_medicine.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_medicine.id

    async def test_get_nonexistent(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/medicine/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_update(self, client: AsyncClient, manager_token: str, sample_medicine):
        r = await client.put(f"/api/v1/medicine/{sample_medicine.id}", headers=H(manager_token),
                             json={"quantity": 200.0})
        assert r.status_code == 200

    async def test_restock(self, client: AsyncClient, manager_token: str, sample_medicine):
        r = await client.post(f"/api/v1/medicine/{sample_medicine.id}/restock",
                              headers=H(manager_token),
                              json={"quantity": 50.0})
        assert r.status_code == 200
        assert r.json()["quantity"] > sample_medicine.quantity

    async def test_delete(self, client: AsyncClient, admin_token: str, sample_medicine):
        r = await client.delete(f"/api/v1/medicine/{sample_medicine.id}", headers=H(admin_token))
        assert r.status_code in (200, 204)
