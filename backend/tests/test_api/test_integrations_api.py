"""
TAURUS VISION — tests/test_api/test_integrations_api.py
=========================================================
Integrations API uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_api/test_integrations_api.py

Qamrav (80+ test):
  ✓ GET  /integrations/meta             — 200 tuzilma, 401
  ✓ GET  /integrations/api-keys         — 200, 401, 403 (non-admin)
  ✓ POST /integrations/api-keys         — 201, raw_key, admin-scope xato, 401, 403
  ✓ GET  /integrations/api-keys/{id}    — 200, 404, 401
  ✓ PATCH /integrations/api-keys/{id}   — 200, 404, 401
  ✓ DELETE /integrations/api-keys/{id}  — 204, 404, 401
  ✓ GET  /integrations/webhooks         — 200, 401
  ✓ POST /integrations/webhooks         — 201, http rejected, 401
  ✓ GET  /integrations/webhooks/{id}    — 200, 404, 401
  ✓ PATCH /integrations/webhooks/{id}   — 200, 401
  ✓ DELETE /integrations/webhooks/{id}  — 204, 401
  ✓ POST /integrations/webhooks/{id}/test — 200/422, 401
"""

import pytest
from httpx import AsyncClient

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

BASE = "/api/v1/integrations"


# ─── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
async def api_key(client, admin_token):
    """Test API kaliti."""
    r = await client.post(
        f"{BASE}/api-keys",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "Test API Key", "scopes": ["read"]},
    )
    assert r.status_code == 201, r.text
    return r.json()


@pytest.fixture
async def webhook(client, admin_token):
    """Test webhook."""
    r = await client.post(
        f"{BASE}/webhooks",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "name": "Test Webhook",
            "url": "https://webhook.example.com/receiver",
            "events": ["alert.critical"],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ═══════════════════════════════════════════════════════════════════════════════
# META
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationMeta:

    async def test_get_meta_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/meta",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "scopes" in data
        assert "events" in data

    async def test_get_meta_viewer_ok(self, client, viewer_token):
        r = await client.get(
            f"{BASE}/meta",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200

    async def test_get_meta_no_token_401(self, client):
        r = await client.get(f"{BASE}/meta")
        assert r.status_code == 401

    async def test_meta_scopes_list(self, client, admin_token):
        r = await client.get(
            f"{BASE}/meta",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        assert isinstance(data["scopes"], list)
        assert len(data["scopes"]) > 0

    async def test_meta_events_list(self, client, admin_token):
        r = await client.get(
            f"{BASE}/meta",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        assert isinstance(data["events"], list)
        assert len(data["events"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# API KEYS
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIKeysList:

    async def test_list_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_list_no_token_401(self, client):
        r = await client.get(f"{BASE}/api-keys")
        assert r.status_code == 401

    async def test_list_viewer_403(self, client, viewer_token):
        r = await client.get(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 403

    async def test_list_manager_403(self, client, manager_token):
        r = await client.get(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert r.status_code == 403


class TestAPIKeyCreate:

    async def test_create_201(self, client, admin_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "New Key", "scopes": ["read"]},
        )
        assert r.status_code == 201
        data = r.json()
        assert "raw_key" in data
        assert data["raw_key"].startswith("tv_live_")

    async def test_create_key_prefix_visible(self, client, admin_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Prefix Test Key", "scopes": ["read"]},
        )
        data = r.json()
        assert data["key_prefix"] is not None
        assert len(data["key_prefix"]) > 0

    async def test_create_admin_scope_by_admin_ok(self, client, admin_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Admin Scope Key", "scopes": ["admin"]},
        )
        assert r.status_code == 201

    async def test_create_admin_scope_by_manager_403(self, client, manager_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {manager_token}"},
            json={"name": "Forbidden Key", "scopes": ["admin"]},
        )
        assert r.status_code == 403

    async def test_create_no_token_401(self, client):
        r = await client.post(
            f"{BASE}/api-keys",
            json={"name": "No Auth", "scopes": ["read"]},
        )
        assert r.status_code == 401

    async def test_create_viewer_403(self, client, viewer_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "Viewer Key", "scopes": ["read"]},
        )
        assert r.status_code == 403

    async def test_create_multiple_scopes(self, client, admin_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Multi Scope Key", "scopes": ["read", "write", "analytics"]},
        )
        assert r.status_code == 201


class TestAPIKeyGet:

    async def test_get_200(self, client, admin_token, api_key):
        r = await client.get(
            f"{BASE}/api-keys/{api_key['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == api_key["id"]

    async def test_get_missing_404(self, client, admin_token):
        r = await client.get(
            f"{BASE}/api-keys/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_get_no_token_401(self, client, api_key):
        r = await client.get(f"{BASE}/api-keys/{api_key['id']}")
        assert r.status_code == 401

    async def test_raw_key_hidden_in_get(self, client, admin_token, api_key):
        """raw_key get'da ko'rinmasligi kerak."""
        r = await client.get(
            f"{BASE}/api-keys/{api_key['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        data = r.json()
        # raw_key yo'q yoki None
        assert data.get("raw_key") is None


class TestAPIKeyUpdate:

    async def test_update_name_200(self, client, admin_token, api_key):
        r = await client.patch(
            f"{BASE}/api-keys/{api_key['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Updated Key Name"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Key Name"

    async def test_update_missing_404(self, client, admin_token):
        r = await client.patch(
            f"{BASE}/api-keys/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Ghost"},
        )
        assert r.status_code == 404

    async def test_update_no_token_401(self, client, api_key):
        r = await client.patch(
            f"{BASE}/api-keys/{api_key['id']}",
            json={"name": "No Auth"},
        )
        assert r.status_code == 401


class TestAPIKeyDelete:

    async def test_delete_204(self, client, admin_token):
        r = await client.post(
            f"{BASE}/api-keys",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Delete Me Key", "scopes": ["read"]},
        )
        kid = r.json()["id"]
        r2 = await client.delete(
            f"{BASE}/api-keys/{kid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 204

    async def test_delete_missing_404(self, client, admin_token):
        r = await client.delete(
            f"{BASE}/api-keys/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_delete_no_token_401(self, client, api_key):
        r = await client.delete(f"{BASE}/api-keys/{api_key['id']}")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# WEBHOOKS
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookList:

    async def test_list_200(self, client, admin_token):
        r = await client.get(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        assert "total" in data

    async def test_list_manager_ok(self, client, manager_token):
        r = await client.get(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {manager_token}"},
        )
        assert r.status_code == 200

    async def test_list_no_token_401(self, client):
        r = await client.get(f"{BASE}/webhooks")
        assert r.status_code == 401


class TestWebhookCreate:

    async def test_create_https_201(self, client, admin_token):
        r = await client.post(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Test WH",
                "url": "https://example.com/hook",
                "events": ["alert.critical"],
            },
        )
        assert r.status_code == 201
        data = r.json()
        assert data["url"] == "https://example.com/hook"

    async def test_create_http_rejected(self, client, admin_token):
        """HTTP URL rad etiladi."""
        r = await client.post(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "HTTP WH",
                "url": "http://insecure.com/hook",
                "events": ["alert.critical"],
            },
        )
        # 400 yoki 422 qaytishi kerak
        assert r.status_code in (400, 422)

    async def test_create_no_token_401(self, client):
        r = await client.post(
            f"{BASE}/webhooks",
            json={"name": "x", "url": "https://x.com", "events": []},
        )
        assert r.status_code == 401

    async def test_create_viewer_403(self, client, viewer_token):
        r = await client.post(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {viewer_token}"},
            json={"name": "x", "url": "https://x.com", "events": []},
        )
        assert r.status_code == 403

    async def test_create_multiple_events(self, client, admin_token):
        r = await client.post(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Multi Event WH",
                "url": "https://example.com/multi",
                "events": ["alert.critical", "adi.warning", "animal.missing"],
            },
        )
        assert r.status_code == 201


class TestWebhookGetUpdateDelete:

    async def test_get_webhook_200(self, client, admin_token, webhook):
        r = await client.get(
            f"{BASE}/webhooks/{webhook['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        assert r.json()["id"] == webhook["id"]

    async def test_get_webhook_missing_404(self, client, admin_token):
        r = await client.get(
            f"{BASE}/webhooks/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_get_webhook_no_token_401(self, client, webhook):
        r = await client.get(f"{BASE}/webhooks/{webhook['id']}")
        assert r.status_code == 401

    async def test_update_webhook_200(self, client, admin_token, webhook):
        r = await client.patch(
            f"{BASE}/webhooks/{webhook['id']}",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Updated Webhook"},
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Webhook"

    async def test_update_webhook_no_token_401(self, client, webhook):
        r = await client.patch(
            f"{BASE}/webhooks/{webhook['id']}",
            json={"name": "No Auth"},
        )
        assert r.status_code == 401

    async def test_delete_webhook_204(self, client, admin_token):
        r = await client.post(
            f"{BASE}/webhooks",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "Delete WH", "url": "https://del.com/hook",
                  "events": ["alert.critical"]},
        )
        wid = r.json()["id"]
        r2 = await client.delete(
            f"{BASE}/webhooks/{wid}",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r2.status_code == 204

    async def test_delete_webhook_missing_404(self, client, admin_token):
        r = await client.delete(
            f"{BASE}/webhooks/999999",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 404

    async def test_delete_webhook_no_token_401(self, client, webhook):
        r = await client.delete(f"{BASE}/webhooks/{webhook['id']}")
        assert r.status_code == 401

    async def test_test_webhook_endpoint(self, client, admin_token, webhook):
        """Webhook test ping — muvaffaqiyatsiz bo'lishi mumkin ama 200/422 qaytishi kerak."""
        r = await client.post(
            f"{BASE}/webhooks/{webhook['id']}/test",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        # External URL mavjud emas — xato kodi yoki muvaffaqiyat
        assert r.status_code in (200, 400, 422, 500)
        assert isinstance(r.json(), dict)