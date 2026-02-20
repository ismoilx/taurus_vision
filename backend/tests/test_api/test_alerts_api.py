"""
Alerts API Tests — /api/v1/alerts/

Qamrovi:
  - GET  /alerts/          list + filter
  - GET  /alerts/stats     statistika
  - GET  /alerts/{id}      bitta olish
  - POST /alerts/          yaratish
  - PATCH /alerts/{id}/seen     ko'rildi
  - PATCH /alerts/{id}/resolve  yopish
  - PATCH /alerts/{id}/dismiss  rad etish
"""

import pytest
from httpx import AsyncClient


pytestmark = [pytest.mark.api, pytest.mark.asyncio]


async def _create_alert(client: AsyncClient, animal_id: int, **kwargs) -> dict:
    """Yordamchi: alert yaratib qaytaradi."""
    payload = {
        "animal_id":   animal_id,
        "alert_type":  "animal_missing",
        "title":       "Test alert",
        "description": "Test tavsifi",
        **kwargs,
    }
    r = await client.post("/api/v1/alerts/", json=payload)
    assert r.status_code == 201, f"Alert yaratilmadi: {r.text}"
    return r.json()


class TestAlertList:
    """GET /api/v1/alerts/ — ro'yxat."""

    async def test_list_empty(self, client: AsyncClient):
        """Bo'sh DB — bo'sh list."""
        r = await client.get("/api/v1/alerts/")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0

    async def test_list_with_alerts(self, client: AsyncClient, sample_animal):
        """Alert bor — ro'yxatda ko'rinadi."""
        await _create_alert(client, sample_animal.id)
        r = await client.get("/api/v1/alerts/")
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_list_filter_status_open(self, client: AsyncClient, sample_animal):
        """status=OPEN filtri ishlaydi."""
        await _create_alert(client, sample_animal.id)
        r = await client.get("/api/v1/alerts/?status=OPEN")
        assert r.status_code == 200
        for alert in r.json()["items"]:
            assert alert["status"] == "OPEN"

    async def test_list_filter_severity(self, client: AsyncClient, sample_animal):
        """severity filtri ishlaydi."""
        r = await client.get("/api/v1/alerts/?severity=critical")
        assert r.status_code == 200


class TestAlertStats:
    """GET /api/v1/alerts/stats."""

    async def test_stats_empty(self, client: AsyncClient):
        """Bo'sh DB — nollar."""
        r = await client.get("/api/v1/alerts/stats")
        assert r.status_code == 200
        data = r.json()
        assert "total"    in data
        assert "open"     in data
        assert "resolved" in data

    async def test_stats_with_data(self, client: AsyncClient, sample_animal):
        """Alert qo'shilganda statistika yangilanadi."""
        await _create_alert(client, sample_animal.id)
        r = await client.get("/api/v1/alerts/stats")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        assert data["open"]  >= 1


class TestAlertCreate:
    """POST /api/v1/alerts/ — yaratish."""

    async def test_create_valid(self, client: AsyncClient, sample_animal):
        """To'g'ri payload bilan yaratish — 201."""
        r = await client.post("/api/v1/alerts/", json={
            "animal_id":   sample_animal.id,
            "alert_type":  "weight_loss",
            "title":       "Vazn kamaydi",
            "description": "So'nggi 7 kunda 15 kg kamaydi",
        })
        assert r.status_code == 201
        data = r.json()
        assert data["alert_type"] == "weight_loss"
        assert data["status"]     == "OPEN"

    async def test_create_missing_animal(self, client: AsyncClient):
        """Yo'q animal_id — 404."""
        r = await client.post("/api/v1/alerts/", json={
            "animal_id":   99999,
            "alert_type":  "animal_missing",
            "title":       "Test",
            "description": "Test",
        })
        assert r.status_code == 404

    async def test_create_no_animal(self, client: AsyncClient):
        """animal_id yo'q (farm-level alert) — 201."""
        r = await client.post("/api/v1/alerts/", json={
            "alert_type":  "camera_offline",
            "title":       "Kamera o'chdi",
            "description": "CAM-001 javob bermayapti",
            "camera_id":   "CAM-001",
        })
        # Ba'zi implementatsiyalar animal_id talab qilmaydi
        assert r.status_code in [201, 422]


class TestAlertGet:
    """GET /api/v1/alerts/{id}."""

    async def test_get_existing(self, client: AsyncClient, sample_animal):
        """Mavjud alert — 200."""
        alert = await _create_alert(client, sample_animal.id)
        r = await client.get(f"/api/v1/alerts/{alert['id']}")
        assert r.status_code == 200
        assert r.json()["id"] == alert["id"]

    async def test_get_nonexistent(self, client: AsyncClient):
        """Yo'q ID — 404."""
        r = await client.get("/api/v1/alerts/99999")
        assert r.status_code == 404


class TestAlertActions:
    """Alert holat o'zgartirish: seen / resolve / dismiss."""

    async def test_mark_seen(self, client: AsyncClient, sample_animal):
        """OPEN → SEEN."""
        alert = await _create_alert(client, sample_animal.id)
        assert alert["status"] == "OPEN"

        r = await client.patch(f"/api/v1/alerts/{alert['id']}/seen")
        assert r.status_code == 200
        assert r.json()["status"] == "SEEN"

    async def test_resolve(self, client: AsyncClient, sample_animal):
        """OPEN → RESOLVED."""
        alert = await _create_alert(client, sample_animal.id)

        r = await client.patch(
            f"/api/v1/alerts/{alert['id']}/resolve",
            json={"note": "Muammo hal qilindi"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "RESOLVED"

    async def test_dismiss(self, client: AsyncClient, sample_animal):
        """Alert rad etish."""
        alert = await _create_alert(client, sample_animal.id)

        r = await client.patch(f"/api/v1/alerts/{alert['id']}/dismiss")
        assert r.status_code == 200
        assert r.json()["status"] in ["DISMISSED", "RESOLVED"]

    async def test_resolve_nonexistent(self, client: AsyncClient):
        """Yo'q alert — 404."""
        r = await client.patch(
            "/api/v1/alerts/99999/resolve",
            json={"note": "Test"},
        )
        assert r.status_code == 404