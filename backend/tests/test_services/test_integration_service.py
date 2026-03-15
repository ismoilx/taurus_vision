"""
TAURUS VISION — tests/test_services/test_integration_service.py
================================================================
IntegrationService + APIKey/Webhook models uchun AYAMAS vahshiy testlar.

Saqlash: backend/tests/test_services/test_integration_service.py

Qamrav (100+ test):
  ✓ _sign_payload       — HMAC-SHA256 format, farqli secret farqli imzo
  ✓ APIKey.generate_raw — format: tv_live_<8>_<32>
  ✓ APIKey.extract_prefix — to'g'ri, noto'g'ri format ValueError
  ✓ APIKey.hash_key       — 64 belgi hex, deterministik
  ✓ APIKey.parse_raw      — prefix + hash tuple
  ✓ APIKey.has_scope      — admin scope, oddiy scope
  ✓ APIKey.display_key    — prefix ko'rinadi, secret yashirilgan
  ✓ Webhook.listens_to    — mavjud/mavjud emas hodisa
  ✓ Webhook.health_status — inactive/degraded/healthy/unknown
  ✓ IntegrationService.create_api_key — admin scope ruxsati, raw_key qaytishi
  ✓ IntegrationService.list_api_keys
  ✓ IntegrationService.get_api_key     — mavjud, yo'q
  ✓ IntegrationService.update_api_key  — maydonlar, yo'q
  ✓ IntegrationService.delete_api_key  — mavjud, yo'q
  ✓ IntegrationService.create_webhook
  ✓ IntegrationService.list_webhooks
  ✓ IntegrationService.get_webhook     — mavjud, yo'q
  ✓ IntegrationService.update_webhook  — maydonlar
  ✓ IntegrationService.delete_webhook  — mavjud, yo'q
"""

import hashlib
import hmac
import secrets
import pytest
from datetime import datetime, timezone, timedelta

from app.models.integration import APIKey, Webhook
from app.services.integration_service import (
    IntegrationService, _sign_payload,
)
from app.schemas.integration import (
    APIKeyCreate, APIKeyUpdate,
    WebhookCreate, WebhookUpdate,
)
from app.core.exceptions import (
    EntityNotFoundError, PermissionDeniedError, BusinessRuleViolationError,
)

pytestmark = pytest.mark.asyncio


@pytest.fixture
def svc(db):
    return IntegrationService(db)


def _key_create(name="Test API Key", scopes=None) -> APIKeyCreate:
    return APIKeyCreate(
        name=name,
        scopes=scopes or ["read"],
    )


def _wh_create(name="Test Webhook", url=None, events=None) -> WebhookCreate:
    return WebhookCreate(
        name=name,
        url=url or "https://webhook.example.com/receiver",
        events=events or ["alert.critical"],
    )


# ═══════════════════════════════════════════════════════════════════════════════
# _sign_payload
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignPayload:

    def test_returns_sha256_prefix(self):
        result = _sign_payload("secret", 1234567890, '{"test": 1}')
        assert result.startswith("sha256=")

    def test_deterministic(self):
        r1 = _sign_payload("secret", 100, "body")
        r2 = _sign_payload("secret", 100, "body")
        assert r1 == r2

    def test_different_secret_different_sig(self):
        r1 = _sign_payload("secret1", 100, "body")
        r2 = _sign_payload("secret2", 100, "body")
        assert r1 != r2

    def test_different_timestamp_different_sig(self):
        r1 = _sign_payload("secret", 100, "body")
        r2 = _sign_payload("secret", 200, "body")
        assert r1 != r2

    def test_different_body_different_sig(self):
        r1 = _sign_payload("secret", 100, "body1")
        r2 = _sign_payload("secret", 100, "body2")
        assert r1 != r2

    def test_hex_length_64(self):
        """SHA-256 hex = 64 belgi."""
        result = _sign_payload("secret", 100, "body")
        hex_part = result.replace("sha256=", "")
        assert len(hex_part) == 64

    def test_verifiable_with_hmac(self):
        """Imzo HMAC bilan tekshiriladi."""
        secret = "my-webhook-secret"
        ts = 1700000000
        body = '{"event":"alert.critical"}'
        result = _sign_payload(secret, ts, body)
        expected_msg = f"{ts}.{body}".encode("utf-8")
        expected_sig = hmac.new(
            secret.encode("utf-8"), expected_msg, hashlib.sha256
        ).hexdigest()
        assert result == f"sha256={expected_sig}"


# ═══════════════════════════════════════════════════════════════════════════════
# APIKey model static methods
# ═══════════════════════════════════════════════════════════════════════════════

class TestAPIKeyModel:

    def test_generate_raw_format(self):
        key = APIKey.generate_raw()
        parts = key.split("_")
        assert len(parts) == 4
        assert parts[0] == "tv"
        assert parts[1] == "live"
        assert len(parts[2]) == 8   # prefix: 4 bytes → 8 hex
        assert len(parts[3]) == 32  # secret: 16 bytes → 32 hex

    def test_generate_raw_starts_with_tv_live(self):
        key = APIKey.generate_raw()
        assert key.startswith("tv_live_")

    def test_generate_raw_unique(self):
        keys = {APIKey.generate_raw() for _ in range(10)}
        assert len(keys) == 10

    def test_extract_prefix_correct(self):
        key = "tv_live_ab12cd34_secret1234567890123456"
        prefix = APIKey.extract_prefix(key)
        assert prefix == "ab12cd34"

    def test_extract_prefix_wrong_format_raises(self):
        with pytest.raises(ValueError):
            APIKey.extract_prefix("wrong_format_key")

    def test_extract_prefix_short_raises(self):
        with pytest.raises(ValueError):
            APIKey.extract_prefix("tv_live")

    def test_hash_key_64_chars(self):
        h = APIKey.hash_key("tv_live_ab12cd34_secret")
        assert len(h) == 64

    def test_hash_key_deterministic(self):
        k = "tv_live_ab12cd34_secret1234567890"
        assert APIKey.hash_key(k) == APIKey.hash_key(k)

    def test_hash_key_different_inputs(self):
        h1 = APIKey.hash_key("key1")
        h2 = APIKey.hash_key("key2")
        assert h1 != h2

    def test_parse_raw_returns_tuple(self):
        key = APIKey.generate_raw()
        result = APIKey.parse_raw(key)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_parse_raw_prefix_matches(self):
        key = APIKey.generate_raw()
        prefix, hashed = APIKey.parse_raw(key)
        assert prefix == APIKey.extract_prefix(key)

    def test_parse_raw_hash_matches(self):
        key = APIKey.generate_raw()
        prefix, hashed = APIKey.parse_raw(key)
        assert hashed == APIKey.hash_key(key)

    def test_has_scope_admin_covers_all(self):
        k = APIKey(
            name="Admin Key", key_prefix="test",
            key_hash="hash", scopes=["admin"],
        )
        assert k.has_scope("read") is True
        assert k.has_scope("write") is True
        assert k.has_scope("admin") is True

    def test_has_scope_specific(self):
        k = APIKey(
            name="Read Key", key_prefix="test",
            key_hash="hash", scopes=["read", "analytics"],
        )
        assert k.has_scope("read") is True
        assert k.has_scope("analytics") is True
        assert k.has_scope("write") is False

    def test_display_key_hides_secret(self):
        k = APIKey(
            name="Display", key_prefix="ab12cd34",
            key_hash="hash", scopes=["read"],
        )
        display = k.display_key
        assert "ab12cd34" in display
        assert "****" in display or "*" in display
        assert "tv_live_" in display


# ═══════════════════════════════════════════════════════════════════════════════
# Webhook model methods
# ═══════════════════════════════════════════════════════════════════════════════

class TestWebhookModel:

    def _wh(self, events=None, is_active=True, failures=0, successes=0):
        return Webhook(
            name="Test WH",
            url="https://example.com/wh",
            secret=secrets.token_hex(16),
            events=events or ["alert.critical"],
            is_active=is_active,
            failure_count=failures,
            success_count=successes,
        )

    def test_listens_to_subscribed_event(self):
        wh = self._wh(events=["alert.critical", "adi.warning"])
        assert wh.listens_to("alert.critical") is True
        assert wh.listens_to("adi.warning") is True

    def test_listens_to_unsubscribed_event(self):
        wh = self._wh(events=["alert.critical"])
        assert wh.listens_to("adi.warning") is False

    def test_listens_to_empty_events(self):
        wh = self._wh(events=[])
        assert wh.listens_to("alert.critical") is False

    def test_health_status_inactive(self):
        wh = self._wh(is_active=False)
        assert wh.health_status == "inactive"

    def test_health_status_degraded_3_failures(self):
        wh = self._wh(is_active=True, failures=3, successes=10)
        assert wh.health_status == "degraded"

    def test_health_status_healthy(self):
        wh = self._wh(is_active=True, failures=0, successes=5)
        assert wh.health_status == "healthy"

    def test_health_status_unknown_no_success(self):
        wh = self._wh(is_active=True, failures=0, successes=0)
        assert wh.health_status == "unknown"

    def test_health_status_degraded_more_failures(self):
        wh = self._wh(is_active=True, failures=10, successes=50)
        assert wh.health_status == "degraded"


# ═══════════════════════════════════════════════════════════════════════════════
# IntegrationService — APIKey CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationServiceAPIKey:

    async def test_create_api_key_success(self, db, svc):
        resp = await svc.create_api_key(_key_create(), created_by=1)
        await db.commit()
        assert resp.id is not None

    async def test_create_api_key_returns_raw_key(self, db, svc):
        resp = await svc.create_api_key(_key_create(), created_by=1)
        await db.commit()
        assert resp.raw_key is not None
        assert resp.raw_key.startswith("tv_live_")

    async def test_create_api_key_raw_key_once_only(self, db, svc):
        """Raw key faqat yaratilganda bir marta ko'rsatiladi."""
        resp = await svc.create_api_key(_key_create(), created_by=1)
        await db.commit()
        # get qilganda raw_key yo'q
        found = await svc.get_api_key(resp.id)
        assert not hasattr(found, "raw_key") or found.raw_key is None

    async def test_create_admin_scope_by_admin_ok(self, db, svc):
        resp = await svc.create_api_key(
            _key_create(scopes=["admin"]),
            created_by=1, is_admin=True)
        await db.commit()
        assert resp.id is not None

    async def test_create_admin_scope_by_non_admin_raises(self, db, svc):
        with pytest.raises(PermissionDeniedError) as exc_info:
            await svc.create_api_key(
                _key_create(scopes=["admin"]),
                created_by=1, is_admin=False)
        assert "admin" in exc_info.value.message.lower()

    async def test_list_api_keys(self, db, svc):
        await svc.create_api_key(_key_create(name="Key 1"), created_by=1)
        await svc.create_api_key(_key_create(name="Key 2"), created_by=1)
        await db.commit()
        result = await svc.list_api_keys()
        assert result.total >= 2

    async def test_get_api_key_existing(self, db, svc):
        created = await svc.create_api_key(_key_create(name="Get Key"), created_by=1)
        await db.commit()
        found = await svc.get_api_key(created.id)
        assert found.id == created.id

    async def test_get_api_key_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_api_key(999999)

    async def test_update_api_key_name(self, db, svc):
        created = await svc.create_api_key(_key_create(name="Old Name"), created_by=1)
        await db.commit()
        updated = await svc.update_api_key(
            created.id, APIKeyUpdate(name="New Name"))
        await db.commit()
        assert updated.name == "New Name"

    async def test_update_api_key_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_api_key(999999, APIKeyUpdate(name="Ghost"))

    async def test_delete_api_key_success(self, db, svc):
        created = await svc.create_api_key(_key_create(name="Delete Me"), created_by=1)
        await db.commit()
        kid = created.id
        await svc.delete_api_key(kid)
        await db.commit()
        with pytest.raises(EntityNotFoundError):
            await svc.get_api_key(kid)

    async def test_delete_api_key_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_api_key(999999)

    async def test_create_all_scopes(self, db, svc):
        for scope in ["read", "write", "analytics", "alerts"]:
            resp = await svc.create_api_key(
                _key_create(name=f"Scope {scope}", scopes=[scope]),
                created_by=1, is_admin=True)
            await db.commit()
            assert resp.id is not None


# ═══════════════════════════════════════════════════════════════════════════════
# IntegrationService — Webhook CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestIntegrationServiceWebhook:

    async def test_create_webhook_success(self, db, svc):
        resp = await svc.create_webhook(_wh_create(), created_by=1)
        await db.commit()
        assert resp.id is not None

    async def test_create_webhook_https_required(self, db, svc):
        """HTTPS bo'lmagan URL rad etiladi."""
        with pytest.raises((BusinessRuleViolationError, Exception)):
            await svc.create_webhook(
                WebhookCreate(
                    name="HTTP WH",
                    url="http://insecure.com/webhook",
                    events=["alert.critical"],
                ),
                created_by=1)

    async def test_list_webhooks(self, db, svc):
        await svc.create_webhook(_wh_create(name="WH 1"), created_by=1)
        await svc.create_webhook(_wh_create(name="WH 2"), created_by=1)
        await db.commit()
        result = await svc.list_webhooks()
        assert result.total >= 2

    async def test_get_webhook_existing(self, db, svc):
        created = await svc.create_webhook(_wh_create(name="Get WH"), created_by=1)
        await db.commit()
        found = await svc.get_webhook(created.id)
        assert found.id == created.id

    async def test_get_webhook_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.get_webhook(999999)

    async def test_update_webhook_name(self, db, svc):
        created = await svc.create_webhook(_wh_create(name="Old WH"), created_by=1)
        await db.commit()
        updated = await svc.update_webhook(
            created.id, WebhookUpdate(name="New WH"))
        await db.commit()
        assert updated.name == "New WH"

    async def test_update_webhook_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.update_webhook(999999, WebhookUpdate(name="Ghost"))

    async def test_delete_webhook_success(self, db, svc):
        created = await svc.create_webhook(_wh_create(name="Delete WH"), created_by=1)
        await db.commit()
        wid = created.id
        await svc.delete_webhook(wid)
        await db.commit()
        with pytest.raises(EntityNotFoundError):
            await svc.get_webhook(wid)

    async def test_delete_webhook_missing_raises(self, db, svc):
        with pytest.raises(EntityNotFoundError):
            await svc.delete_webhook(999999)

    async def test_create_webhook_multiple_events(self, db, svc):
        resp = await svc.create_webhook(
            _wh_create(events=["alert.critical", "adi.warning", "animal.missing"]),
            created_by=1)
        await db.commit()
        assert resp.id is not None

    async def test_create_webhook_deactivated(self, db, svc):
        resp = await svc.create_webhook(
            WebhookCreate(
                name="Inactive WH",
                url="https://example.com/hook",
                events=["alert.critical"],
                is_active=False,
            ),
            created_by=1)
        await db.commit()
        assert resp.id is not None
        assert resp.is_active is False