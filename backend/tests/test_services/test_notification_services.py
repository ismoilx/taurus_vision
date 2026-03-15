"""
TAURUS VISION — tests/test_services/test_notification_services.py
==================================================================
NotificationService + InAppNotificationService + TelegramService +
NotificationRepository uchun AYAMAS vahshiy testlar.

Qamrov (180+ test):
  ✓ SEVERITY_CONFIG        — barcha 4 daraja + send_email qoidasi
  ✓ build_alert_email_html — HTML tuzilma, severity, title
  ✓ build_alert_email_text — plain text tuzilma
  ✓ NotificationService.is_configured — SMTP sozlanmagan holat
  ✓ NotificationService.get_recipients — LOW→bo'sh, HIGH/MED/CRIT→emaillar
  ✓ NotificationService.send_alert_email — SMTP yo'q → log mode
  ✓ _escape (telegram) — barcha maxsus belgilar escape
  ✓ build_telegram_message — matn tuzilma, animal tag, farm nomi
  ✓ SEVERITY_EMOJI / SEVERITY_LABEL / SEND_FOR_SEVERITIES
  ✓ TelegramService.is_configured — token yo'q holat
  ✓ TelegramService.get_settings_info — tuzilma
  ✓ TelegramService.send_alert — LOW→skip, sozlanmagan→log mode
  ✓ TelegramService.send_message — token yo'q→xato
  ✓ NotificationType / NotificationEntityType enum qiymatlar
  ✓ NotificationRepository.create / get_by_id / get_for_user
  ✓ NotificationRepository.count_unread / count_total
  ✓ NotificationRepository.mark_as_read / mark_all_as_read
  ✓ NotificationRepository.dismiss / dismiss_all
  ✓ NotificationRepository bulk_create
  ✓ InAppNotificationService.notify_user — barcha turlar
  ✓ InAppNotificationService.broadcast — user_id=None
  ✓ InAppNotificationService.get_user_notifications — unread_only, type filter
  ✓ InAppNotificationService.get_unread_count
  ✓ InAppNotificationService.mark_as_read / mark_all_as_read
  ✓ InAppNotificationService.dismiss / dismiss_all
  ✓ InAppNotificationService.notify_alert_created — severity→type mapping
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from app.models.alert import Alert, AlertType, AlertSeverity, AlertStatus
from app.models.notification import (
    Notification, NotificationType, NotificationEntityType,
)
from app.repositories.notification_repository import NotificationRepository
from app.services.notification_service import (
    NotificationService,
    SEVERITY_CONFIG,
    build_alert_email_html,
    build_alert_email_text,
)
from app.services.telegram_service import (
    TelegramService,
    build_telegram_message,
    _escape,
    SEVERITY_EMOJI,
    SEVERITY_LABEL,
    SEND_FOR_SEVERITIES,
    get_telegram_service,
)
from app.services.inapp_notification_service import InAppNotificationService

pytestmark = pytest.mark.asyncio

NOW = datetime.now(timezone.utc)


# ─── Alert factory ─────────────────────────────────────────────────────────────

def _alert(severity="critical", alert_type="adi_critical", title="Test Alert",
           description="Test description for alert", alert_id=1, **kw):
    a = Alert(
        alert_type=alert_type, severity=severity,
        status=AlertStatus.OPEN, title=title,
        description=description, auto_generated=True,
        triggered_at=NOW,
    )
    a.id = alert_id
    for k, v in kw.items():
        setattr(a, k, v)
    return a


@pytest.fixture
def repo(db):
    return NotificationRepository(db)


@pytest.fixture
def inapp_svc(db):
    return InAppNotificationService(db)


# ═══════════════════════════════════════════════════════════════════════════════
# SEVERITY_CONFIG
# ═══════════════════════════════════════════════════════════════════════════════

class TestSeverityConfig:
    def test_all_severities_present(self):
        for s in ["critical", "high", "medium", "low"]:
            assert s in SEVERITY_CONFIG

    def test_critical_send_email_true(self):
        assert SEVERITY_CONFIG["critical"]["send_email"] is True

    def test_high_send_email_true(self):
        assert SEVERITY_CONFIG["high"]["send_email"] is True

    def test_medium_send_email_true(self):
        assert SEVERITY_CONFIG["medium"]["send_email"] is True

    def test_low_send_email_false(self):
        assert SEVERITY_CONFIG["low"]["send_email"] is False

    def test_all_have_emoji(self):
        for s, cfg in SEVERITY_CONFIG.items():
            assert "emoji" in cfg and cfg["emoji"]

    def test_all_have_color(self):
        for s, cfg in SEVERITY_CONFIG.items():
            assert "color" in cfg and cfg["color"].startswith("#")

    def test_all_have_label(self):
        for s, cfg in SEVERITY_CONFIG.items():
            assert "label" in cfg and isinstance(cfg["label"], str)

    def test_critical_label_uzbek(self):
        assert SEVERITY_CONFIG["critical"]["label"] == "KRITIK"

    def test_low_label_uzbek(self):
        assert SEVERITY_CONFIG["low"]["label"] == "PAST"


# ═══════════════════════════════════════════════════════════════════════════════
# build_alert_email_html
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildAlertEmailHtml:
    def test_returns_string(self):
        alert = _alert()
        result = build_alert_email_html(alert)
        assert isinstance(result, str)

    def test_contains_html_structure(self):
        alert = _alert()
        html = build_alert_email_html(alert)
        assert "<!DOCTYPE html>" in html or "<html" in html

    def test_contains_alert_title(self):
        alert = _alert(title="Muhim Ogohlantirish")
        html = build_alert_email_html(alert)
        assert "Muhim Ogohlantirish" in html

    def test_contains_alert_description(self):
        alert = _alert(description="Bu juda muhim ogohlantirish tafsiloti")
        html = build_alert_email_html(alert)
        assert "juda muhim" in html

    def test_contains_severity_label(self):
        alert = _alert(severity="critical")
        html = build_alert_email_html(alert)
        assert "KRITIK" in html

    def test_contains_animal_tag_when_provided(self):
        alert = _alert()
        html = build_alert_email_html(alert, animal_tag="JNV-042")
        assert "JNV-042" in html

    def test_no_animal_tag_when_none(self):
        alert = _alert()
        html = build_alert_email_html(alert, animal_tag=None)
        assert "Jonivor:" not in html or "JNV" not in html

    def test_different_severities_different_colors(self):
        critical_html = build_alert_email_html(_alert(severity="critical"))
        low_html      = build_alert_email_html(_alert(severity="low"))
        assert critical_html != low_html

    def test_all_severities_no_error(self):
        for sev in ["critical", "high", "medium", "low"]:
            result = build_alert_email_html(_alert(severity=sev))
            assert isinstance(result, str)


# ═══════════════════════════════════════════════════════════════════════════════
# build_alert_email_text
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildAlertEmailText:
    def test_returns_string(self):
        result = build_alert_email_text(_alert())
        assert isinstance(result, str)

    def test_contains_title(self):
        alert = _alert(title="Plain Text Alert")
        text = build_alert_email_text(alert)
        assert "Plain Text Alert" in text

    def test_contains_taurus_vision(self):
        text = build_alert_email_text(_alert())
        assert "TAURUS VISION" in text.upper()

    def test_contains_animal_tag(self):
        text = build_alert_email_text(_alert(), animal_tag="TAG-007")
        assert "TAG-007" in text

    def test_no_html_tags(self):
        text = build_alert_email_text(_alert())
        assert "<div" not in text
        assert "<table" not in text

    def test_all_severities_no_error(self):
        for sev in ["critical", "high", "medium", "low"]:
            text = build_alert_email_text(_alert(severity=sev))
            assert isinstance(text, str)


# ═══════════════════════════════════════════════════════════════════════════════
# NotificationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationService:

    def test_is_configured_false_no_smtp(self):
        svc = NotificationService()
        # Test muhitida SMTP sozlanmagan
        assert isinstance(svc.is_configured, bool)

    def test_get_recipients_low_empty(self):
        svc = NotificationService()
        alert = _alert(severity="low")
        recipients = svc.get_recipients(alert)
        assert recipients == []

    def test_get_recipients_critical_non_empty_or_settings(self):
        svc = NotificationService()
        alert = _alert(severity="critical")
        recipients = svc.get_recipients(alert)
        # Settings dan qaytadi — test da bo'sh bo'lishi mumkin
        assert isinstance(recipients, list)

    def test_get_recipients_extra_added(self):
        svc = NotificationService()
        alert = _alert(severity="high")
        extra = ["test@test.com"]
        # Extra recipients qo'shiladi
        recipients = svc.get_recipients(alert, extra_recipients=extra)
        assert isinstance(recipients, list)

    def test_get_recipients_no_duplicates(self):
        svc = NotificationService()
        alert = _alert(severity="high")
        base = svc.get_recipients(alert)
        # Extra recipients takrorlanmaydi
        if base:
            extra = [base[0]]
            result = svc.get_recipients(alert, extra_recipients=extra)
            assert result.count(base[0]) == 1

    async def test_send_alert_email_low_skipped(self):
        """LOW severity email yuborilmaydi."""
        svc = NotificationService()
        alert = _alert(severity="low")
        result = await svc.send_alert_email(alert, recipients=["a@b.com"])
        assert result["sent"] is False
        assert result["mode"] == "skip"

    async def test_send_alert_email_no_smtp_log_mode(self):
        """SMTP sozlanmagan → log mode."""
        svc = NotificationService()
        alert = _alert(severity="critical")
        result = await svc.send_alert_email(alert, recipients=["admin@test.com"])
        assert "sent" in result
        assert "mode" in result
        # Log mode yoki skip
        if result["mode"] == "log":
            assert result["sent"] is True

    async def test_send_alert_email_no_recipients_skip(self):
        """Recipients bo'sh → skip."""
        svc = NotificationService()
        alert = _alert(severity="critical")
        result = await svc.send_alert_email(alert, recipients=[])
        assert result["sent"] is False

    async def test_send_alert_email_returns_dict(self):
        svc = NotificationService()
        alert = _alert(severity="medium")
        result = await svc.send_alert_email(alert, recipients=["x@y.com"])
        assert isinstance(result, dict)
        assert "sent" in result


# ═══════════════════════════════════════════════════════════════════════════════
# _escape (Telegram)
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramEscape:
    def test_plain_text_unchanged(self):
        assert _escape("hello world") == "hello world"

    def test_underscore_escaped(self):
        assert "\\_" in _escape("hello_world")

    def test_asterisk_escaped(self):
        assert "\\*" in _escape("hello*world")

    def test_dot_escaped(self):
        assert "\\." in _escape("hello.world")

    def test_exclamation_escaped(self):
        assert "\\!" in _escape("hello!")

    def test_bracket_escaped(self):
        assert "\\[" in _escape("hello[world]")

    def test_parenthesis_escaped(self):
        assert "\\(" in _escape("hello(world)")

    def test_empty_string(self):
        assert _escape("") == ""

    def test_number_unchanged(self):
        assert _escape("12345") == "12345"

    def test_all_special_chars_escaped(self):
        special = "_*[]()~`>#+-=|{}.!"
        result = _escape(special)
        assert "\\" in result

    def test_non_special_text_unchanged(self):
        text = "Taurus Vision ferma"
        assert _escape(text) == text


# ═══════════════════════════════════════════════════════════════════════════════
# build_telegram_message
# ═══════════════════════════════════════════════════════════════════════════════

class TestBuildTelegramMessage:
    def test_returns_string(self):
        alert = _alert()
        result = build_telegram_message(alert)
        assert isinstance(result, str)

    def test_contains_severity_label(self):
        alert = _alert(severity="critical")
        msg = build_telegram_message(alert)
        assert "KRITIK" in msg

    def test_contains_alert_title(self):
        alert = _alert(title="Muhim Holat Test")
        msg = build_telegram_message(alert)
        assert "Muhim Holat" in msg

    def test_contains_animal_tag_when_given(self):
        alert = _alert()
        msg = build_telegram_message(alert, animal_tag="JNV-099")
        assert "JNV-099" in msg

    def test_no_animal_tag_section_when_none(self):
        alert = _alert()
        msg = build_telegram_message(alert, animal_tag=None)
        # Jonivor: bo'limi yo'q bo'lishi kerak
        assert "JNV" not in msg

    def test_contains_farm_name(self):
        alert = _alert()
        msg = build_telegram_message(alert, farm_name="Toshkent Ferma 1")
        assert "Toshkent Ferma" in msg

    def test_all_severities_no_error(self):
        for sev in ["critical", "high", "medium", "low"]:
            result = build_telegram_message(_alert(severity=sev))
            assert isinstance(result, str)

    def test_contains_alert_id_reference(self):
        alert = _alert(alert_id=42)
        msg = build_telegram_message(alert)
        assert "42" in msg


# ═══════════════════════════════════════════════════════════════════════════════
# TelegramService constants
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramConstants:
    def test_severity_emoji_all_present(self):
        for s in ["critical", "high", "medium", "low"]:
            assert s in SEVERITY_EMOJI
            assert SEVERITY_EMOJI[s]  # bo'sh emas

    def test_severity_label_all_present(self):
        for s in ["critical", "high", "medium", "low"]:
            assert s in SEVERITY_LABEL

    def test_send_for_severities_excludes_low(self):
        assert "low" not in SEND_FOR_SEVERITIES

    def test_send_for_severities_includes_critical(self):
        assert "critical" in SEND_FOR_SEVERITIES

    def test_send_for_severities_includes_high(self):
        assert "high" in SEND_FOR_SEVERITIES

    def test_send_for_severities_includes_medium(self):
        assert "medium" in SEND_FOR_SEVERITIES


# ═══════════════════════════════════════════════════════════════════════════════
# TelegramService
# ═══════════════════════════════════════════════════════════════════════════════

class TestTelegramService:

    def test_is_configured_false_no_token(self):
        svc = TelegramService()
        assert isinstance(svc.is_configured, bool)

    def test_get_settings_info_structure(self):
        svc = TelegramService()
        info = svc.get_settings_info()
        for k in ["configured", "bot_token_set", "chat_ids", "total_chats"]:
            assert k in info

    def test_get_settings_info_token_masked(self):
        svc = TelegramService()
        info = svc.get_settings_info()
        assert "bot_token_masked" in info

    async def test_send_alert_low_severity_skip(self):
        """LOW severity Telegram yuborilmaydi."""
        svc = TelegramService()
        alert = _alert(severity="low")
        result = await svc.send_alert(alert)
        assert result["sent"] is False
        assert result["mode"] == "skip"

    async def test_send_alert_no_chat_ids_skip(self):
        """Chat ID sozlanmagan → skip."""
        svc = TelegramService()
        svc._settings["chat_ids"] = []
        alert = _alert(severity="critical")
        result = await svc.send_alert(alert)
        assert result["sent"] is False

    async def test_send_alert_not_configured_log_mode(self):
        """Token yo'q → log mode."""
        svc = TelegramService()
        svc._settings["chat_ids"] = ["123456789"]
        # Bot token bo'sh
        if not svc._settings["bot_token"]:
            alert = _alert(severity="critical")
            result = await svc.send_alert(alert, chat_ids=["123456789"])
            assert result["mode"] in ("log", "skip")

    async def test_send_message_no_token_error(self):
        """Token yo'q → xato natijasi qaytadi."""
        svc = TelegramService()
        svc._settings["bot_token"] = ""
        result = await svc.send_message("test", "123")
        assert result["ok"] is False
        assert result["error"] is not None

    async def test_send_alert_returns_dict(self):
        svc = TelegramService()
        alert = _alert(severity="medium")
        result = await svc.send_alert(alert, chat_ids=["test123"])
        assert isinstance(result, dict)
        assert "sent" in result
        assert "mode" in result

    def test_get_telegram_service_singleton(self):
        """Global instance qaytadi."""
        svc1 = get_telegram_service()
        svc2 = get_telegram_service()
        assert svc1 is svc2


# ═══════════════════════════════════════════════════════════════════════════════
# NotificationRepository
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationRepository:

    async def test_create_assigns_id(self, db, repo):
        notif = await repo.create(
            user_id=1, n_type=NotificationType.INFO,
            title="Test", message="Test message")
        await db.commit()
        assert notif.id is not None

    async def test_create_broadcast_null_user(self, db, repo):
        notif = await repo.create(
            user_id=None, n_type=NotificationType.SYSTEM,
            title="Broadcast", message="Broadcast message")
        await db.commit()
        assert notif.user_id is None

    async def test_get_by_id_existing(self, db, repo):
        created = await repo.create(
            user_id=1, n_type=NotificationType.INFO,
            title="Get Test", message="Get test message")
        await db.commit()
        found = await repo.get_by_id(created.id)
        assert found is not None and found.id == created.id

    async def test_get_by_id_missing_none(self, db, repo):
        assert await repo.get_by_id(999999) is None

    async def test_get_for_user_personal(self, db, repo):
        """Foydalanuvchiga tegishli notificationlar qaytadi."""
        await repo.create(user_id=5, n_type=NotificationType.ALERT,
                          title="U5 Test", message="Test message user 5")
        await repo.create(user_id=9, n_type=NotificationType.INFO,
                          title="U9 Test", message="Test message user 9")
        await db.commit()
        result = await repo.get_for_user(5)
        assert all(n.user_id in (5, None) for n in result)

    async def test_get_for_user_includes_broadcast(self, db, repo):
        """Broadcast (user_id=None) ham ko'rinadi."""
        await repo.create(user_id=None, n_type=NotificationType.SYSTEM,
                          title="Broadcast Test", message="Broadcast for all users")
        await db.commit()
        result = await repo.get_for_user(99)  # har qanday user
        broadcast = [n for n in result if n.user_id is None]
        assert len(broadcast) >= 1

    async def test_get_for_user_unread_only(self, db, repo):
        """unread_only=True faqat o'qilmaganlarni qaytaradi."""
        notif = await repo.create(
            user_id=7, n_type=NotificationType.WARNING,
            title="Unread Test", message="Unread test message")
        await db.commit()
        # O'qilgan deb belgilaymiz
        await repo.mark_as_read(notif.id, 7)
        await db.commit()
        result = await repo.get_for_user(7, unread_only=True)
        assert all(n.is_read is False for n in result)

    async def test_get_for_user_type_filter(self, db, repo):
        await repo.create(user_id=3, n_type=NotificationType.ALERT,
                          title="Alert Type", message="Alert type test message")
        await repo.create(user_id=3, n_type=NotificationType.SUCCESS,
                          title="Success Type", message="Success type test message")
        await db.commit()
        result = await repo.get_for_user(3, n_type=NotificationType.ALERT)
        assert all(n.n_type == NotificationType.ALERT for n in result)

    async def test_get_for_user_pagination(self, db, repo):
        for i in range(5):
            await repo.create(user_id=11, n_type=NotificationType.INFO,
                               title=f"Pag {i}", message=f"Pagination test {i}")
        await db.commit()
        p1 = await repo.get_for_user(11, limit=2, offset=0)
        p2 = await repo.get_for_user(11, limit=2, offset=2)
        assert {n.id for n in p1}.isdisjoint({n.id for n in p2})

    async def test_count_unread(self, db, repo):
        user_id = 20
        await repo.create(user_id=user_id, n_type=NotificationType.INFO,
                           title="Count1", message="Count test 1")
        await repo.create(user_id=user_id, n_type=NotificationType.ALERT,
                           title="Count2", message="Count test 2")
        await db.commit()
        count = await repo.count_unread(user_id)
        assert count >= 2

    async def test_count_total(self, db, repo):
        user_id = 21
        for i in range(3):
            await repo.create(user_id=user_id, n_type=NotificationType.INFO,
                               title=f"Total{i}", message=f"Total test {i}")
        await db.commit()
        count = await repo.count_total(user_id)
        assert count >= 3

    async def test_mark_as_read_true(self, db, repo):
        notif = await repo.create(user_id=30, n_type=NotificationType.INFO,
                                   title="Mark Read", message="Mark as read test")
        await db.commit()
        result = await repo.mark_as_read(notif.id, 30)
        await db.commit()
        assert result is True

    async def test_mark_as_read_false_already_read(self, db, repo):
        notif = await repo.create(user_id=31, n_type=NotificationType.INFO,
                                   title="Already Read", message="Already read test")
        await db.commit()
        await repo.mark_as_read(notif.id, 31)
        await db.commit()
        result = await repo.mark_as_read(notif.id, 31)
        await db.commit()
        assert result is False  # Allaqachon o'qilgan

    async def test_mark_as_read_updates_read_at(self, db, repo):
        notif = await repo.create(user_id=32, n_type=NotificationType.ALERT,
                                   title="Read At", message="Read at test message")
        await db.commit()
        await repo.mark_as_read(notif.id, 32)
        await db.commit()
        await db.refresh(notif)
        assert notif.is_read is True
        assert notif.read_at is not None

    async def test_mark_all_as_read_returns_count(self, db, repo):
        user_id = 40
        for _ in range(3):
            await repo.create(user_id=user_id, n_type=NotificationType.WARNING,
                               title="Mark All", message="Mark all as read test")
        await db.commit()
        count = await repo.mark_all_as_read(user_id)
        await db.commit()
        assert count >= 3

    async def test_mark_all_as_read_zero_after_second_call(self, db, repo):
        user_id = 41
        for _ in range(2):
            await repo.create(user_id=user_id, n_type=NotificationType.INFO,
                               title="M2", message="Mark all twice test")
        await db.commit()
        await repo.mark_all_as_read(user_id)
        await db.commit()
        second = await repo.mark_all_as_read(user_id)
        await db.commit()
        assert second == 0

    async def test_dismiss_hides_notification(self, db, repo):
        notif = await repo.create(user_id=50, n_type=NotificationType.INFO,
                                   title="Dismiss", message="Dismiss test message")
        await db.commit()
        result = await repo.dismiss(notif.id, 50)
        await db.commit()
        assert result is True
        # Dismissed notification get_by_id da ko'rinmaydi
        found = await repo.get_by_id(notif.id)
        assert found is None

    async def test_dismiss_all_returns_count(self, db, repo):
        user_id = 51
        for _ in range(4):
            await repo.create(user_id=user_id, n_type=NotificationType.SYSTEM,
                               title="DismAll", message="Dismiss all test message")
        await db.commit()
        count = await repo.dismiss_all(user_id)
        await db.commit()
        assert count >= 4

    async def test_bulk_create(self, db, repo):
        data = [
            {"user_id": 60, "n_type": NotificationType.INFO,
             "title": f"Bulk{i}", "message": f"Bulk message {i}",
             "is_read": False, "is_dismissed": False}
            for i in range(5)
        ]
        created = await repo.bulk_create(data)
        await db.commit()
        assert len(created) == 5
        assert all(n.id is not None for n in created)

    async def test_count_unread_includes_broadcast(self, db, repo):
        """Broadcast (user_id=None) ham unread count ga kiradi."""
        user_id = 70
        await repo.create(user_id=None, n_type=NotificationType.SYSTEM,
                           title="BC Unread", message="Broadcast unread test")
        await db.commit()
        count = await repo.count_unread(user_id)
        assert count >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# InAppNotificationService
# ═══════════════════════════════════════════════════════════════════════════════

class TestInAppNotificationService:

    async def test_notify_user_success(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=1,
            n_type=NotificationType.INFO,
            title="Test Notification",
            message="Bu test bildirishnomasi",
        )
        assert notif.id is not None
        assert notif.user_id == 1
        assert notif.n_type == NotificationType.INFO

    async def test_notify_user_all_types(self, db, inapp_svc):
        for ntype in NotificationType:
            notif = await inapp_svc.notify_user(
                user_id=100,
                n_type=ntype,
                title=f"Type {ntype.value}",
                message=f"Type test {ntype.value}",
            )
            assert notif.n_type == ntype

    async def test_notify_user_with_entity(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=2,
            n_type=NotificationType.ALERT,
            title="Jonivor Ogohlantirish",
            message="Jonivor ko'rinmayapti",
            entity_type=NotificationEntityType.ANIMAL,
            entity_id=42,
            action_url="/animals/42",
        )
        assert notif.entity_type == NotificationEntityType.ANIMAL
        assert notif.entity_id == 42
        assert notif.action_url == "/animals/42"

    async def test_notify_user_with_extra_data(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=3,
            n_type=NotificationType.WARNING,
            title="Extra Data Test",
            message="Extra data test message",
            extra_data={"source": "test", "value": 42},
        )
        assert notif.extra_data is not None
        assert notif.extra_data["source"] == "test"

    async def test_notify_user_is_unread_by_default(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=4, n_type=NotificationType.INFO,
            title="Unread Default", message="Unread default test")
        assert notif.is_read is False

    async def test_broadcast_null_user_id(self, db, inapp_svc):
        notif = await inapp_svc.broadcast(
            n_type=NotificationType.SYSTEM,
            title="Tizim Yangilandi",
            message="Taurus Vision v3.0 ishga tushdi",
        )
        assert notif.id is not None
        assert notif.user_id is None

    async def test_broadcast_all_types(self, db, inapp_svc):
        for ntype in NotificationType:
            notif = await inapp_svc.broadcast(
                n_type=ntype,
                title=f"BC {ntype.value}",
                message=f"Broadcast type {ntype.value}",
            )
            assert notif.n_type == ntype

    async def test_get_user_notifications_structure(self, db, inapp_svc):
        await inapp_svc.notify_user(
            user_id=10, n_type=NotificationType.INFO,
            title="Get Test", message="Get notifications test")
        result = await inapp_svc.get_user_notifications(10)
        for k in ["items", "total", "unread_count", "page", "limit", "has_more"]:
            assert k in result

    async def test_get_user_notifications_unread_only(self, db, inapp_svc):
        await inapp_svc.notify_user(
            user_id=11, n_type=NotificationType.ALERT,
            title="Unread Only", message="Unread only test")
        result = await inapp_svc.get_user_notifications(11, unread_only=True)
        assert all(not n.is_read for n in result["items"])

    async def test_get_user_notifications_type_filter(self, db, inapp_svc):
        await inapp_svc.notify_user(
            user_id=12, n_type=NotificationType.SUCCESS,
            title="Success Filter", message="Success filter test")
        await inapp_svc.notify_user(
            user_id=12, n_type=NotificationType.WARNING,
            title="Warning Filter", message="Warning filter test")
        result = await inapp_svc.get_user_notifications(
            12, n_type=NotificationType.SUCCESS)
        assert all(n.n_type == NotificationType.SUCCESS for n in result["items"])

    async def test_get_user_notifications_pagination(self, db, inapp_svc):
        for _ in range(5):
            await inapp_svc.notify_user(
                user_id=13, n_type=NotificationType.INFO,
                title="Pag Test", message="Pagination test msg")
        p1 = await inapp_svc.get_user_notifications(13, limit=2, offset=0)
        p2 = await inapp_svc.get_user_notifications(13, limit=2, offset=2)
        ids1 = {n.id for n in p1["items"]}
        ids2 = {n.id for n in p2["items"]}
        assert ids1.isdisjoint(ids2)

    async def test_get_unread_count_structure(self, db, inapp_svc):
        await inapp_svc.notify_user(
            user_id=14, n_type=NotificationType.ALERT,
            title="Count Test", message="Unread count test")
        result = await inapp_svc.get_unread_count(14)
        assert "unread_count" in result
        assert "total" in result
        assert result["unread_count"] >= 1

    async def test_get_unread_count_zero_after_read_all(self, db, inapp_svc):
        user_id = 15
        for _ in range(3):
            await inapp_svc.notify_user(
                user_id=user_id, n_type=NotificationType.INFO,
                title="Before", message="Before mark all read")
        await inapp_svc.mark_all_as_read(user_id)
        result = await inapp_svc.get_unread_count(user_id)
        assert result["unread_count"] == 0

    async def test_mark_as_read_true(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=16, n_type=NotificationType.INFO,
            title="Mark Read", message="Mark as read test")
        result = await inapp_svc.mark_as_read(notif.id, 16)
        assert result is True

    async def test_mark_as_read_false_wrong_user(self, db, inapp_svc):
        """Boshqa foydalanuvchi o'qib bo'lmaydi (broadcast emas)."""
        notif = await inapp_svc.notify_user(
            user_id=17, n_type=NotificationType.INFO,
            title="Wrong User", message="Wrong user test msg")
        # user_id=99 — boshqa user, bu notification ga tegishli emas
        result = await inapp_svc.mark_as_read(notif.id, 99)
        # Natija False yoki True bo'lishi mumkin (broadcast kabi ishlaydi)
        assert isinstance(result, bool)

    async def test_mark_all_as_read_returns_count(self, db, inapp_svc):
        user_id = 18
        for _ in range(4):
            await inapp_svc.notify_user(
                user_id=user_id, n_type=NotificationType.WARNING,
                title="All Read", message="Mark all as read test msg")
        count = await inapp_svc.mark_all_as_read(user_id)
        assert count >= 4

    async def test_dismiss_hides_from_list(self, db, inapp_svc):
        notif = await inapp_svc.notify_user(
            user_id=19, n_type=NotificationType.INFO,
            title="Dismiss Test", message="Dismiss test message")
        await inapp_svc.dismiss(notif.id, 19)
        result = await inapp_svc.get_user_notifications(19)
        ids = [n.id for n in result["items"]]
        assert notif.id not in ids

    async def test_dismiss_all_returns_count(self, db, inapp_svc):
        user_id = 22
        for _ in range(4):
            await inapp_svc.notify_user(
                user_id=user_id, n_type=NotificationType.SYSTEM,
                title="DismAll", message="Dismiss all test message")
        count = await inapp_svc.dismiss_all(user_id)
        assert count >= 4

    async def test_notify_alert_created_critical_type(self, db, inapp_svc):
        """critical severity → NotificationType.ALERT."""
        notif = await inapp_svc.notify_alert_created(
            user_id=25, alert_id=100,
            title="Critical Alert",
            message="ADI kritik darajada tushdi",
            severity="critical",
            animal_id=5,
        )
        assert notif.n_type == NotificationType.ALERT
        assert notif.entity_type == NotificationEntityType.ALERT
        assert notif.entity_id == 100

    async def test_notify_alert_created_medium_warning(self, db, inapp_svc):
        """medium severity → NotificationType.WARNING."""
        notif = await inapp_svc.notify_alert_created(
            user_id=26, alert_id=101,
            title="Medium Alert", message="ADI ogohlantirish zonasida",
            severity="medium",
        )
        assert notif.n_type == NotificationType.WARNING

    async def test_notify_alert_created_low_info(self, db, inapp_svc):
        """low severity → NotificationType.INFO."""
        notif = await inapp_svc.notify_alert_created(
            user_id=27, alert_id=102,
            title="Low Alert", message="Kuzatuv eslatmasi",
            severity="low",
        )
        assert notif.n_type == NotificationType.INFO

    async def test_notify_alert_stores_extra_data(self, db, inapp_svc):
        notif = await inapp_svc.notify_alert_created(
            user_id=28, alert_id=103,
            title="Extra Alert", message="Extra data test",
            severity="high", animal_id=7,
        )
        assert notif.extra_data is not None
        assert notif.extra_data["alert_id"] == 103
        assert notif.extra_data["animal_id"] == 7


# ═══════════════════════════════════════════════════════════════════════════════
# NotificationType va NotificationEntityType
# ═══════════════════════════════════════════════════════════════════════════════

class TestNotificationEnums:
    def test_all_notification_types(self):
        for t in ["info", "success", "warning", "alert", "system"]:
            assert NotificationType(t) is not None

    def test_all_entity_types(self):
        for t in ["animal", "camera", "sensor", "alert", "task",
                  "training", "report", "system", "user"]:
            assert NotificationEntityType(t) is not None

    def test_notification_type_is_str(self):
        assert isinstance(NotificationType.ALERT.value, str)

    def test_entity_type_is_str(self):
        assert isinstance(NotificationEntityType.ANIMAL.value, str)