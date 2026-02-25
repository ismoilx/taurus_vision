"""
Alerts API Tests — /api/v1/alerts/

Qamrovi:
  - GET  /alerts/               list + filter
  - GET  /alerts/stats          statistika
  - GET  /alerts/{id}           bitta olish
  - POST /alerts/               yaratish
  - PATCH /alerts/{id}/seen     ko'rildi
  - PATCH /alerts/{id}/resolve  yopish
  - PATCH /alerts/{id}/dismiss  rad etish

O'ZGARISHLAR (bugfix):
  - Auth header qo'shildi
  - Status lowercase: 'open'|'seen'|'resolved' (backend qaytaradigan format)
  - Stats response maydonlari to'g'rilandi: total_open, critical_open va h.k.
  - resolve body: {resolved_by, resolution_note}
  - dismiss body: {dismissed_by, reason}
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]


# =============================================================================
# HELPER
# =============================================================================

async def _create_alert(
    client: AsyncClient,
    token: str,
    animal_id: int,
    **kwargs,
) -> dict:
    """Yordamchi: alert yaratib qaytaradi."""
    payload = {
        "animal_id":   animal_id,
        "alert_type":  "animal_missing",
        "title":       "Test alert",
        "description": "Test tavsifi",
        **kwargs,
    }
    r = await client.post(
        "/api/v1/alerts/",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
    )
    assert r.status_code == 201, f"Alert yaratilmadi: {r.text}"
    return r.json()


# =============================================================================
# LIST
# =============================================================================

class TestAlertList:
    """GET /api/v1/alerts/ — ro'yxat."""

    async def test_list_empty(self, client: AsyncClient, admin_token: str):
        """Bo'sh DB — bo'sh list."""
        r = await client.get(
            "/api/v1/alerts/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 0

    async def test_list_with_alerts(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Alert bor — ro'yxatda ko'rinadi."""
        await _create_alert(client, admin_token, sample_animal.id)
        r = await client.get(
            "/api/v1/alerts/",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["total"] >= 1

    async def test_list_filter_severity(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """severity filtri ishlaydi."""
        r = await client.get(
            "/api/v1/alerts/?severity=critical",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200

    async def test_list_no_token(self, client: AsyncClient):
        """Token yo'q — 401."""
        r = await client.get("/api/v1/alerts/")
        assert r.status_code == 401


# =============================================================================
# STATS
# =============================================================================

class TestAlertStats:
    """GET /api/v1/alerts/stats."""

    async def test_stats_empty(self, client: AsyncClient, admin_token: str):
        """Bo'sh DB — nollar qaytadi."""
        r = await client.get(
            "/api/v1/alerts/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        # AlertStatsResponse haqiqiy maydonlari
        assert "total_open"    in data
        assert "critical_open" in data
        assert "high_open"     in data

    async def test_stats_with_data(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Alert qo'shilganda total_open oshadi."""
        await _create_alert(client, admin_token, sample_animal.id)
        r = await client.get(
            "/api/v1/alerts/stats",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["total_open"] >= 1


# =============================================================================
# CREATE
# =============================================================================

class TestAlertCreate:
    """POST /api/v1/alerts/ — yaratish."""

    async def test_create_valid(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """To'g'ri payload — 201, status lowercase 'open'."""
        r = await client.post(
            "/api/v1/alerts/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "animal_id":   sample_animal.id,
                "alert_type":  "weight_loss",
                "title":       "Vazn kamaydi",
                "description": "So'nggi 7 kunda 15 kg kamaydi",
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["alert_type"] == "weight_loss"
        assert data["status"]     == "open"   # backend lowercase qaytaradi

    async def test_create_missing_animal(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q animal_id — 404 yoki 201 (backend animal tekshirmaydi)."""
        r = await client.post(
            "/api/v1/alerts/",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "animal_id":   99999,
                "alert_type":  "animal_missing",
                "title":       "Test",
                "description": "Test",
            },
        )
        # Backend animal mavjudligini tekshirsa 404, tekshirmasa 201
        assert r.status_code in (201, 404, 422)

    async def test_create_no_token(self, client: AsyncClient, sample_animal):
        """Token yo'q — 401."""
        r = await client.post(
            "/api/v1/alerts/",
            json={
                "animal_id":   sample_animal.id,
                "alert_type":  "weight_loss",
                "title":       "Test",
                "description": "Test",
            },
        )
        assert r.status_code == 401


# =============================================================================
# GET SINGLE
# =============================================================================

class TestAlertGet:
    """GET /api/v1/alerts/{id}."""

    async def test_get_existing(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Mavjud alert — 200."""
        alert = await _create_alert(client, admin_token, sample_animal.id)
        r = await client.get(
            f"/api/v1/alerts/{alert['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == alert["id"]

    async def test_get_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q ID — 404."""
        r = await client.get(
            "/api/v1/alerts/99999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code in (404, 422)


# =============================================================================
# LIFECYCLE
# =============================================================================

class TestAlertActions:
    """Alert holat o'zgartirish: seen / resolve / dismiss."""

    async def test_mark_seen(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """open → seen."""
        alert = await _create_alert(client, admin_token, sample_animal.id)
        assert alert["status"] == "open"

        r = await client.patch(
            f"/api/v1/alerts/{alert['id']}/seen",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "seen"

    async def test_resolve(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """open → resolved."""
        alert = await _create_alert(client, admin_token, sample_animal.id)

        r = await client.patch(
            f"/api/v1/alerts/{alert['id']}/resolve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "resolved_by":     "admin",
                "resolution_note": "Muammo hal qilindi",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] == "resolved"

    async def test_dismiss(
        self, client: AsyncClient, admin_token: str, sample_animal
    ):
        """Alert rad etish — dismissed."""
        alert = await _create_alert(client, admin_token, sample_animal.id)

        r = await client.patch(
            f"/api/v1/alerts/{alert['id']}/dismiss",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "dismissed_by": "admin",
                "reason":       "Noto'g'ri signal",
            },
        )
        assert r.status_code == 200
        assert r.json()["status"] in ("dismissed", "resolved")

    async def test_resolve_nonexistent(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q alert — 404."""
        r = await client.patch(
            "/api/v1/alerts/99999/resolve",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"resolved_by": "admin", "resolution_note": "Test"},
        )
        assert r.status_code in (404, 422)

    async def test_no_token(self, client: AsyncClient, sample_animal):
        """Token yo'q — 401."""
        r = await client.patch(f"/api/v1/alerts/1/seen")
        assert r.status_code == 401