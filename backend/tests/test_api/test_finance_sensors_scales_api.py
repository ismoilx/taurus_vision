"""
Taurus Vision — Finance, Sensors, Scales API Tests
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]
H = lambda t: {"Authorization": f"Bearer {t}"}

# ═══════════════════════════════════════════════════════════════════
# FINANCE
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_transaction(db: AsyncSession):
    from app.models.finance import FinanceTransaction, TransactionType, TransactionCategory
    tx = FinanceTransaction(
        transaction_type=TransactionType.EXPENSE,
        category=TransactionCategory.FEED,
        amount=500000.0,
        currency="UZS",
        description="Test xarajat",
        transaction_date=datetime.now(timezone.utc),
    )
    db.add(tx); await db.commit(); await db.refresh(tx); return tx


class TestFinanceAPI:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/finance/")
        assert r.status_code == 401

    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/finance/", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_expense(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/finance/", headers=H(manager_token), json={
            "transaction_type": "expense",
            "category": "feed",
            "amount": 1000000.0,
            "currency": "UZS",
            "description": "Beda xaridi",
            "transaction_date": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 201
        data = r.json()
        assert data["amount"] == 1000000.0
        assert data["transaction_type"] == "expense"

    async def test_create_income(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/finance/", headers=H(manager_token), json={
            "transaction_type": "income",
            "category": "animal_sale",
            "amount": 5000000.0,
            "currency": "UZS",
            "description": "Mol sotiw",
            "transaction_date": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 201

    async def test_create_negative_amount_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/finance/", headers=H(manager_token), json={
            "transaction_type": "expense",
            "category": "feed",
            "amount": -100,
            "currency": "UZS",
            "transaction_date": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/finance/", headers=H(viewer_token), json={
            "transaction_type": "expense",
            "category": "feed",
            "amount": 100,
            "currency": "UZS",
            "transaction_date": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 403

    async def test_get_transaction(self, client: AsyncClient, viewer_token: str, sample_transaction):
        r = await client.get(f"/api/v1/finance/{sample_transaction.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_transaction.id

    async def test_summary(self, client: AsyncClient, viewer_token: str, sample_transaction):
        r = await client.get("/api/v1/finance/summary", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_monthly_report(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/finance/monthly", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_update_transaction(self, client: AsyncClient, manager_token: str, sample_transaction):
        r = await client.patch(f"/api/v1/finance/{sample_transaction.id}",
                               headers=H(manager_token), json={"description": "Yangilangan izoh"})
        assert r.status_code == 200

    async def test_delete_transaction(self, client: AsyncClient, admin_token: str, sample_transaction):
        r = await client.delete(f"/api/v1/finance/{sample_transaction.id}", headers=H(admin_token))
        assert r.status_code in (200, 204)


# ═══════════════════════════════════════════════════════════════════
# SENSORS
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_sensor_reading(db: AsyncSession):
    from app.models.sensor_reading import SensorReading, SensorType
    sr = SensorReading(
        device_id="SENSOR-001",
        sensor_type=SensorType.TEMPERATURE,
        value=38.5,
        unit="°C",
        timestamp=datetime.now(timezone.utc),
    )
    db.add(sr); await db.commit(); await db.refresh(sr); return sr


class TestSensorsAPI:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/sensors/readings")
        assert r.status_code == 401

    async def test_list_readings(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/sensors/readings", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_reading(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/sensors/reading", headers=H(admin_token), json={
            "device_id": "SENSOR-TEST",
            "sensor_type": "temperature",
            "value": 38.5,
            "unit": "°C",
        })
        assert r.status_code in (200, 201)

    async def test_device_status(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/sensors/devices", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_latest_readings(self, client: AsyncClient, viewer_token: str, sample_sensor_reading):
        r = await client.get("/api/v1/sensors/latest", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_anomalies(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/sensors/anomalies", headers=H(viewer_token))
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# SCALES
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_scale(db: AsyncSession):
    from app.models.scale import Scale, ScaleType, ScaleStatus
    scale = Scale(
        name="Test Tarozi",
        scale_type=ScaleType.FLOOR,
        status=ScaleStatus.ACTIVE,
        capacity_kg=2000.0,
        precision_kg=0.5,
        location="Darvoza",
    )
    db.add(scale); await db.commit(); await db.refresh(scale); return scale


class TestScalesAPI:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/scales")
        assert r.status_code == 401

    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/scales", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_scale(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/scales", headers=H(admin_token), json={
            "name": "Yangi Tarozi",
            "scale_type": "floor",
            "capacity_kg": 1500.0,
            "precision_kg": 0.5,
            "location": "Molxona",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Yangi Tarozi"

    async def test_viewer_cannot_create_scale(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/scales", headers=H(viewer_token), json={
            "name": "Test", "scale_type": "floor", "capacity_kg": 1000, "precision_kg": 0.1
        })
        assert r.status_code == 403

    async def test_get_scale(self, client: AsyncClient, viewer_token: str, sample_scale):
        r = await client.get(f"/api/v1/scales/{sample_scale.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_scale.id

    async def test_update_scale(self, client: AsyncClient, admin_token: str, sample_scale):
        r = await client.put(f"/api/v1/scales/{sample_scale.id}", headers=H(admin_token),
                             json={"name": "Yangilangan Tarozi", "scale_type": "floor",
                                   "capacity_kg": 2000, "precision_kg": 0.5})
        assert r.status_code == 200

    async def test_delete_scale(self, client: AsyncClient, admin_token: str, sample_scale):
        r = await client.delete(f"/api/v1/scales/{sample_scale.id}", headers=H(admin_token))
        assert r.status_code in (200, 204)

    async def test_manual_weight(self, client: AsyncClient, manager_token: str, sample_animal, sample_scale):
        r = await client.post("/api/v1/scales/weights/manual", headers=H(manager_token), json={
            "animal_id": sample_animal.id,
            "scale_id": sample_scale.id,
            "actual_weight_kg": 450.0,
        })
        assert r.status_code == 201

    async def test_weight_comparison(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/scales/comparison", headers=H(viewer_token))
        assert r.status_code == 200
