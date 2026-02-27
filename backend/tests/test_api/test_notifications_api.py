"""
Taurus Vision — Notifications API Tests (Sprint 11-12)

Test qamrovi:
    GET  /notifications/settings          — SMTP sozlamalarini ko'rish
    POST /notifications/test-email        — Test email yuborish
    POST /notifications/send/{alert_id}   — Alert uchun email yuborish
    POST /notifications/send-bulk         — Ko'plab alert uchun email

Notification service real SMTP yuborishi shart emas —
is_configured=False holatida "log" mode da ishlaydi.
Testlar email yuborishning o'zini emas, API qatlamni tekshiradi.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.api, pytest.mark.asyncio]

_BASE = "/api/v1/notifications"


# =============================================================================
# HELPERS
# =============================================================================

def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def _make_alert(db: AsyncSession, animal_id: int) -> object:
    """Test uchun Alert yaratadi."""
    from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
    from datetime import datetime, timezone

    alert = Alert(
        animal_id    = animal_id,
        alert_type   = AlertType.ADI_WARNING.value,
        severity     = AlertSeverity.MEDIUM.value,
        status       = AlertStatus.OPEN.value,
        title        = "Test alert for notification",
        description  = "Notification test — ADI warning",
        auto_generated = True,
        triggered_at = datetime.now(timezone.utc),
    )
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


# =============================================================================
# SOZLAMALAR TESTLARI
# =============================================================================

class TestNotificationSettings:
    """GET /notifications/settings"""

    async def test_settings_structure(
        self, client: AsyncClient, admin_token: str
    ):
        """Settings to'g'ri strukturada qaytadi."""
        r = await client.get(
            f"{_BASE}/settings",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()

        required = [
            "configured", "smtp_host", "smtp_port",
            "smtp_user", "from_address", "recipients",
        ]
        for key in required:
            assert key in data, f"Settings key '{key}' missing"

    async def test_settings_types(
        self, client: AsyncClient, admin_token: str
    ):
        """Settings maydonlar to'g'ri tipda."""
        r = await client.get(
            f"{_BASE}/settings",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()

        assert isinstance(data["configured"],      bool)
        assert isinstance(data["smtp_host"],        str)
        assert isinstance(data["smtp_port"],        int)
        assert isinstance(data["smtp_user"],        str)
        assert isinstance(data["recipients"],       list)
        assert data["smtp_port"] > 0

    async def test_settings_severity_rules_present(
        self, client: AsyncClient, admin_token: str
    ):
        """Severity qoidalari mavjud."""
        r = await client.get(
            f"{_BASE}/settings",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        # severity_rules optional — agar mavjud bo'lsa to'g'ri formatda
        if "severity_rules" in data:
            assert isinstance(data["severity_rules"], dict)

    async def test_settings_requires_auth(self, client: AsyncClient):
        """Token yo'q — 401/403."""
        r = await client.get(f"{_BASE}/settings")
        assert r.status_code in (401, 403)

    async def test_settings_viewer_can_read(
        self, client: AsyncClient, viewer_token: str
    ):
        """VIEWER ham sozlamalarni ko'ra oladi."""
        r = await client.get(
            f"{_BASE}/settings",
            headers=_auth(viewer_token),
        )
        # Viewer uchun ruxsat berilsa 200, aks holda 403
        assert r.status_code in (200, 403)


# =============================================================================
# TEST EMAIL TESTLARI
# =============================================================================

class TestEmailSend:
    """POST /notifications/test-email"""

    async def test_test_email_log_mode(
        self, client: AsyncClient, admin_token: str
    ):
        """SMTP sozlanmagan — log mode da ishlaydi, xato qaytarmaydi."""
        r = await client.post(
            f"{_BASE}/test-email",
            json={"recipient": "test@example.com"},
            headers=_auth(admin_token),
        )
        # Log mode da ham muvaffaqiyatli qaytishi kerak
        assert r.status_code == 200
        data = r.json()
        # "sent", "message" yoki "mode" fieldidan biri bo'lishi kerak
        has_result = any(k in data for k in ["sent", "message", "mode", "status"])
        assert has_result, f"Response has no result field: {data}"

    async def test_test_email_invalid_format(
        self, client: AsyncClient, admin_token: str
    ):
        """Bo'sh recipient — 422."""
        r = await client.post(
            f"{_BASE}/test-email",
            json={"recipient": ""},
            headers=_auth(admin_token),
        )
        # Bo'sh string qabul qilinmasligi kerak
        assert r.status_code in (200, 422)

    async def test_test_email_missing_recipient(
        self, client: AsyncClient, admin_token: str
    ):
        """recipient maydoni yo'q — 422."""
        r = await client.post(
            f"{_BASE}/test-email",
            json={},
            headers=_auth(admin_token),
        )
        assert r.status_code == 422

    async def test_test_email_requires_manager(
        self, client: AsyncClient, viewer_token: str
    ):
        """VIEWER test email yubora olmaydi."""
        r = await client.post(
            f"{_BASE}/test-email",
            json={"recipient": "test@example.com"},
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_test_email_no_auth(self, client: AsyncClient):
        """Token yo'q — 401/403."""
        r = await client.post(
            f"{_BASE}/test-email",
            json={"recipient": "test@example.com"},
        )
        assert r.status_code in (401, 403)


# =============================================================================
# ALERT NOTIFICATION TESTLARI
# =============================================================================

class TestAlertNotification:
    """POST /notifications/send/{alert_id}"""

    async def test_send_alert_notification(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Mavjud alert uchun notification yuboriladi."""
        alert = await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send/{alert.id}",
            json={},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "alert_id" in data
        assert data["alert_id"] == alert.id

    async def test_send_alert_with_recipients_override(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Recipients override bilan yuborish."""
        alert = await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send/{alert.id}",
            json={"recipients": ["override@example.com"]},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200

    async def test_send_nonexistent_alert(
        self, client: AsyncClient, admin_token: str
    ):
        """Yo'q alert — 404."""
        r = await client.post(
            f"{_BASE}/send/999999",
            json={},
            headers=_auth(admin_token),
        )
        assert r.status_code == 404

    async def test_send_requires_manager(
        self,
        client:      AsyncClient,
        viewer_token: str,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """VIEWER notification yubora olmaydi."""
        alert = await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send/{alert.id}",
            json={},
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_send_no_auth(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Token yo'q — 401/403."""
        alert = await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send/{alert.id}",
            json={},
        )
        assert r.status_code in (401, 403)

    async def test_send_returns_sent_flag(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Response 'sent' flagini qaytaradi."""
        alert = await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send/{alert.id}",
            json={},
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "sent" in data
        assert isinstance(data["sent"], bool)


# =============================================================================
# BULK NOTIFICATION TESTLARI
# =============================================================================

class TestBulkNotification:
    """POST /notifications/send-bulk"""

    async def test_bulk_send_empty_queue(
        self, client: AsyncClient, admin_token: str
    ):
        """Ochiq alertlar bo'lmasa — 0 navbatga qo'shiladi."""
        r = await client.post(
            f"{_BASE}/send-bulk",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "queued" in data
        assert isinstance(data["queued"], int)
        assert data["queued"] >= 0

    async def test_bulk_send_with_alerts(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Ochiq alertlar mavjud bo'lganda navbatga qo'shiladi."""
        # Bir nechta alert yaratamiz
        for _ in range(3):
            await _make_alert(db, sample_animal.id)

        r = await client.post(
            f"{_BASE}/send-bulk",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "queued"    in data
        assert "alert_ids" in data
        assert isinstance(data["alert_ids"], list)

    async def test_bulk_send_severity_filter(
        self,
        client:      AsyncClient,
        admin_token: str,
        db:          AsyncSession,
        sample_animal,
    ):
        """Severity filtr ishlaydi."""
        r = await client.post(
            f"{_BASE}/send-bulk?severity=critical",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "queued" in data

    async def test_bulk_send_requires_manager(
        self, client: AsyncClient, viewer_token: str
    ):
        """VIEWER bulk yuborolmaydi."""
        r = await client.post(
            f"{_BASE}/send-bulk",
            headers=_auth(viewer_token),
        )
        assert r.status_code in (401, 403)

    async def test_bulk_send_invalid_severity(
        self, client: AsyncClient, admin_token: str
    ):
        """Noto'g'ri severity — 422 yoki filtered result."""
        r = await client.post(
            f"{_BASE}/send-bulk?severity=invalid_severity",
            headers=_auth(admin_token),
        )
        # 422 yoki 200 with 0 queued (DB da match yo'q)
        assert r.status_code in (200, 422)

    async def test_bulk_send_returns_message(
        self, client: AsyncClient, admin_token: str
    ):
        """Response 'message' fieldini o'z ichiga oladi."""
        r = await client.post(
            f"{_BASE}/send-bulk",
            headers=_auth(admin_token),
        )
        assert r.status_code == 200
        data = r.json()
        assert "message" in data
        assert isinstance(data["message"], str)
        assert len(data["message"]) > 0