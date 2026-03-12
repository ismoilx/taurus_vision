"""
Taurus Vision — Farms, Tasks, Feed API Tests
"""
import pytest
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]
H = lambda t: {"Authorization": f"Bearer {t}"}


# ═══════════════════════════════════════════════════════════════════
# FARMS
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_farm(db: AsyncSession):
    from app.models.farm import Farm
    farm = Farm(name="Test Ferma", location="Toshkent", is_active=True)
    db.add(farm); await db.commit(); await db.refresh(farm); return farm


class TestFarmsAPI:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/farms")
        assert r.status_code == 401

    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/farms", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_farm(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/farms", headers=H(admin_token), json={
            "name": "Yangi Ferma",
            "location": "Samarqand",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Yangi Ferma"

    async def test_create_missing_name_rejected(self, client: AsyncClient, admin_token: str):
        r = await client.post("/api/v1/farms", headers=H(admin_token), json={"location": "Buxoro"})
        assert r.status_code == 422

    async def test_viewer_cannot_create_farm(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/farms", headers=H(viewer_token), json={"name": "Test"})
        assert r.status_code == 403

    async def test_get_farm(self, client: AsyncClient, viewer_token: str, sample_farm):
        r = await client.get(f"/api/v1/farms/{sample_farm.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_farm.id

    async def test_get_nonexistent_farm(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/farms/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_update_farm(self, client: AsyncClient, admin_token: str, sample_farm):
        r = await client.put(f"/api/v1/farms/{sample_farm.id}", headers=H(admin_token),
                             json={"name": "Yangilangan Ferma", "location": "Toshkent"})
        assert r.status_code == 200
        assert r.json()["name"] == "Yangilangan Ferma"

    async def test_deactivate_farm(self, client: AsyncClient, admin_token: str, sample_farm):
        r = await client.post(f"/api/v1/farms/{sample_farm.id}/deactivate", headers=H(admin_token))
        assert r.status_code == 200

    async def test_delete_farm(self, client: AsyncClient, admin_token: str, sample_farm):
        r = await client.delete(f"/api/v1/farms/{sample_farm.id}", headers=H(admin_token))
        assert r.status_code in (200, 204)


# ═══════════════════════════════════════════════════════════════════
# FARM TASKS
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_task(db: AsyncSession):
    from app.models.farm_task import FarmTask, TaskPriority, TaskStatus
    task = FarmTask(
        title="Test Vazifa",
        priority=TaskPriority.MEDIUM,
        status=TaskStatus.PENDING,
    )
    db.add(task); await db.commit(); await db.refresh(task); return task


class TestFarmTasksAPI:
    async def test_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/tasks/")
        assert r.status_code == 401

    async def test_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/tasks/", headers=H(viewer_token))
        assert r.status_code == 200
        data = r.json()
        assert "items" in data

    async def test_stats(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/tasks/stats", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_task(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/tasks/", headers=H(manager_token), json={
            "title": "Yangi vazifa",
            "priority": "high",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["title"] == "Yangi vazifa"

    async def test_create_empty_title_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/tasks/", headers=H(manager_token), json={"title": ""})
        assert r.status_code == 422

    async def test_viewer_cannot_create(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/tasks/", headers=H(viewer_token), json={"title": "Test"})
        assert r.status_code == 403

    async def test_get_task(self, client: AsyncClient, viewer_token: str, sample_task):
        r = await client.get(f"/api/v1/tasks/{sample_task.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_task.id

    async def test_get_nonexistent(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/tasks/999999", headers=H(viewer_token))
        assert r.status_code == 404

    async def test_update_task(self, client: AsyncClient, manager_token: str, sample_task):
        r = await client.patch(f"/api/v1/tasks/{sample_task.id}", headers=H(manager_token),
                               json={"title": "Yangilangan vazifa"})
        assert r.status_code == 200
        assert r.json()["title"] == "Yangilangan vazifa"

    async def test_start_task(self, client: AsyncClient, admin_token: str, sample_task):
        r = await client.post(f"/api/v1/tasks/{sample_task.id}/start", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] == "in_progress"

    async def test_complete_task(self, client: AsyncClient, admin_token: str, sample_task):
        await client.post(f"/api/v1/tasks/{sample_task.id}/start", headers=H(admin_token))
        r = await client.post(f"/api/v1/tasks/{sample_task.id}/complete", headers=H(admin_token))
        assert r.status_code == 200
        assert r.json()["status"] == "completed"

    async def test_cancel_task(self, client: AsyncClient, manager_token: str, sample_task):
        r = await client.post(f"/api/v1/tasks/{sample_task.id}/cancel", headers=H(manager_token))
        assert r.status_code == 200
        assert r.json()["status"] == "cancelled"


# ═══════════════════════════════════════════════════════════════════
# FEED
# ═══════════════════════════════════════════════════════════════════

@pytest.fixture
async def sample_feed_stock(db: AsyncSession):
    from app.models.feed import FeedStock, FeedType, FeedUnit
    stock = FeedStock(
        name="Beda",
        feed_type=FeedType.HAY,
        quantity_kg=500.0,
        unit=FeedUnit.KG,
        min_stock_kg=50.0,
        price_per_kg=2000.0,
    )
    db.add(stock); await db.commit(); await db.refresh(stock); return stock


class TestFeedAPI:
    async def test_stocks_list_no_token(self, client: AsyncClient):
        r = await client.get("/api/v1/feed/stocks/")
        assert r.status_code == 401

    async def test_stocks_list_empty(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/feed/stocks/", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_stocks_stats(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/feed/stocks/stats", headers=H(viewer_token))
        assert r.status_code == 200

    async def test_create_stock(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/feed/stocks/", headers=H(manager_token), json={
            "name": "Somon",
            "feed_type": "wheat_straw",
            "quantity_kg": 1000.0,
            "unit": "kg",
            "price_per_kg": 500.0,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["name"] == "Somon"

    async def test_create_negative_quantity_rejected(self, client: AsyncClient, manager_token: str):
        r = await client.post("/api/v1/feed/stocks/", headers=H(manager_token), json={
            "name": "Test",
            "feed_type": "hay",
            "quantity_kg": -100,
            "unit": "kg",
        })
        assert r.status_code == 422

    async def test_viewer_cannot_create_stock(self, client: AsyncClient, viewer_token: str):
        r = await client.post("/api/v1/feed/stocks/", headers=H(viewer_token), json={
            "name": "Test", "feed_type": "hay", "quantity_kg": 100, "unit": "kg"
        })
        assert r.status_code == 403

    async def test_get_stock(self, client: AsyncClient, viewer_token: str, sample_feed_stock):
        r = await client.get(f"/api/v1/feed/stocks/{sample_feed_stock.id}", headers=H(viewer_token))
        assert r.status_code == 200
        assert r.json()["id"] == sample_feed_stock.id

    async def test_update_stock(self, client: AsyncClient, manager_token: str, sample_feed_stock):
        r = await client.patch(f"/api/v1/feed/stocks/{sample_feed_stock.id}",
                               headers=H(manager_token), json={"quantity_kg": 600.0})
        assert r.status_code == 200

    async def test_restock(self, client: AsyncClient, manager_token: str, sample_feed_stock):
        r = await client.post(f"/api/v1/feed/stocks/{sample_feed_stock.id}/restock",
                              headers=H(manager_token), json={"quantity_kg": 200.0})
        assert r.status_code == 200
        assert r.json()["quantity_kg"] > sample_feed_stock.quantity_kg

    async def test_create_feed_record(self, client: AsyncClient, manager_token: str,
                                      sample_feed_stock, sample_animal):
        r = await client.post("/api/v1/feed/records/", headers=H(manager_token), json={
            "stock_id": sample_feed_stock.id,
            "animal_id": sample_animal.id,
            "quantity_kg": 5.0,
            "fed_at": datetime.now(timezone.utc).isoformat(),
        })
        assert r.status_code == 201

    async def test_list_feed_records(self, client: AsyncClient, viewer_token: str):
        r = await client.get("/api/v1/feed/records/", headers=H(viewer_token))
        assert r.status_code == 200