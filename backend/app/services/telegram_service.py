"""
Taurus Vision — Telegram Notification Service

Ferma egasiga Telegram Bot orqali real-time alert xabarnomalari.

SOZLASH (.env):
    TELEGRAM_BOT_TOKEN=7123456789:AABcDeFgHiJkLmNoPqRsTuVwXyZ
    TELEGRAM_CHAT_IDS=123456789,987654321

XABAR FORMATI:
    🔴 KRITIK OGOHLANTIRISH
    ━━━━━━━━━━━━━━━━━━━
    Ferma: Toshkent Fermasi
    Jonivor: JNV-023
    Muammo: ADI 18 — Faollik keskin tushdi
    ...

ARXITEKTURA:
    TelegramService  — xabar yuborish, sozlamalar
    send_telegram()  — global helper funksiya

BOT YARATISH:
    1. @BotFather ga /newbot yuboring
    2. Bot token ni oling
    3. Bot bilan /start yozing (chat ID kerak bo'ladi)
    4. https://api.telegram.org/bot{TOKEN}/getUpdates — chat_id ni toping
"""

import logging
import asyncio
from typing import Optional
import urllib.request
import urllib.error
import json

from app.models.alert import Alert

logger = logging.getLogger(__name__)


# =============================================================================
# SEVERITY KONFIGURATSIYA
# =============================================================================

SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "medium":   "🟡",
    "low":      "🟢",
}

SEVERITY_LABEL = {
    "critical": "KRITIK",
    "high":     "YUQORI",
    "medium":   "O'RTA",
    "low":      "PAST",
}

# Faqat shu severity lar uchun Telegram yuboriladi
SEND_FOR_SEVERITIES = {"critical", "high", "medium"}


# =============================================================================
# MESSAGE BUILDER
# =============================================================================

def build_telegram_message(
    alert: Alert,
    animal_tag: Optional[str] = None,
    farm_name: Optional[str] = None,
) -> str:
    """
    Alert uchun Telegram xabari matnini yaratadi.

    Markdown format — Telegram MarkdownV2 uchun.

    Args:
        alert:      Alert ORM instance
        animal_tag: Jonivor teg raqami (ko'rsatish uchun)
        farm_name:  Ferma nomi

    Returns:
        Telegram Markdown matn
    """
    emoji   = SEVERITY_EMOJI.get(alert.severity, "⚠️")
    label   = SEVERITY_LABEL.get(alert.severity, "OGOHLANTIRISH")

    # Alert type uchun insoniy nom
    alert_type_labels = {
        "adi_critical":        "ADI Kritik holat",
        "adi_warning":         "ADI Ogohlantirish",
        "adi_sharp_drop":      "ADI Keskin pasayish",
        "animal_missing":      "Jonivor ko'rinmayapti",
        "animal_missing_long": "Jonivor uzoq vaqt ko'rinmadi",
        "feeding_stopped":     "Oziqlanish to'xtadi",
        "high_temperature":    "Yuqori harorat",
        "low_heart_rate":      "Past yurak urishi",
        "high_heart_rate":     "Yuqori yurak urishi",
        "growth_stagnation":   "O'sish to'xtadi",
        "camera_offline":      "Kamera offline",
        "weight_drop":         "Vazn keskin tushdi",
        "health_risk":         "Sog'liq xavfi",
    }
    type_label = alert_type_labels.get(alert.alert_type, alert.alert_type)

    lines = [
        f"{emoji} *{label} OGOHLANTIRISH*",
        "━━━━━━━━━━━━━━━━━━━━",
        f"*{_escape(alert.title)}*",
        "",
        f"_{_escape(alert.description)}_",
        "",
        "📋 *Tafsilotlar:*",
        f"  • Tur: {_escape(type_label)}",
    ]

    if farm_name:
        lines.append(f"  • Ferma: {_escape(farm_name)}")
    if animal_tag:
        lines.append(f"  • Jonivor: `{_escape(animal_tag)}`")
    if alert.camera_id:
        lines.append(f"  • Kamera: `{_escape(alert.camera_id)}`")

    lines += [
        f"  • Alert ID: `#{alert.id}`",
        "",
        "🔗 [Alertni ko'rish](http://localhost:5173/alerts)",
    ]

    return "\n".join(lines)


def _escape(text: str) -> str:
    """Telegram MarkdownV2 uchun maxsus belgilarni qochirish."""
    # Asosiy maxsus belgilar
    special = r"_*[]()~`>#+-=|{}.!"
    result = ""
    for ch in str(text):
        if ch in special:
            result += "\\" + ch
        else:
            result += ch
    return result


# =============================================================================
# TELEGRAM SERVICE
# =============================================================================

class TelegramService:
    """
    Telegram Bot API orqali xabar yuborish servisi.

    FOYDALANISH:
        svc = TelegramService()
        await svc.send_alert(alert, animal_tag="JNV-001")

    SOZLASH:
        .env da TELEGRAM_BOT_TOKEN va TELEGRAM_CHAT_IDS bo'lishi shart.
        Sozlanmagan bo'lsa — log ga yozadi (development mode).
    """

    def __init__(self) -> None:
        self._settings = self._load_settings()

    def _load_settings(self) -> dict:
        from app.config import settings as app_settings
        return {
            "bot_token": app_settings.TELEGRAM_BOT_TOKEN,
            "chat_ids":  app_settings.telegram_chat_ids,
        }

    @property
    def is_configured(self) -> bool:
        """Telegram bot sozlanganmi?"""
        return bool(
            self._settings["bot_token"]
            and self._settings["chat_ids"]
        )

    def get_settings_info(self) -> dict:
        """Sozlamalar ma'lumoti (token yashirin)."""
        token = self._settings["bot_token"]
        masked = f"{token[:8]}...{token[-4:]}" if len(token) > 12 else "***" if token else ""
        return {
            "configured":    self.is_configured,
            "bot_token_set": bool(token),
            "bot_token_masked": masked,
            "chat_ids":      self._settings["chat_ids"],
            "total_chats":   len(self._settings["chat_ids"]),
        }

    async def send_message(
        self,
        text:    str,
        chat_id: str,
        parse_mode: str = "MarkdownV2",
    ) -> dict:
        """
        Bitta chat ga xabar yuboradi.

        Args:
            text:       Xabar matni
            chat_id:    Telegram chat ID
            parse_mode: "MarkdownV2" yoki "HTML"

        Returns:
            {"ok": bool, "message_id": int | None, "error": str | None}
        """
        if not self._settings["bot_token"]:
            return {"ok": False, "error": "Bot token sozlanmagan"}

        url = f"https://api.telegram.org/bot{self._settings['bot_token']}/sendMessage"
        payload = json.dumps({
            "chat_id":    chat_id,
            "text":       text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }).encode("utf-8")

        def _send_sync():
            req = urllib.request.Request(
                url,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=10) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="replace")
                return {"ok": False, "error": f"HTTP {e.code}: {body}"}
            except Exception as ex:
                return {"ok": False, "error": str(ex)}

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, _send_sync)

        return {
            "ok":         result.get("ok", False),
            "message_id": result.get("result", {}).get("message_id") if result.get("ok") else None,
            "error":      result.get("description") if not result.get("ok") else None,
        }

    async def send_alert(
        self,
        alert:      Alert,
        animal_tag: Optional[str] = None,
        farm_name:  Optional[str] = None,
        chat_ids:   Optional[list[str]] = None,
    ) -> dict:
        """
        Alert uchun barcha chat larga xabar yuboradi.

        LOW severity uchun Telegram yuborilmaydi.

        Args:
            alert:      Alert ORM instance
            animal_tag: Jonivor teg raqami
            farm_name:  Ferma nomi
            chat_ids:   Override chat ID ro'yxati (None = settings dan)

        Returns:
            {
                "sent": bool,
                "results": [{"chat_id": ..., "ok": ..., "error": ...}],
                "mode": "telegram" | "log" | "skip"
            }
        """
        # LOW uchun yuborilmaydi
        if alert.severity not in SEND_FOR_SEVERITIES:
            return {
                "sent":   False,
                "mode":   "skip",
                "reason": f"Severity '{alert.severity}' uchun Telegram yuborilmaydi",
            }

        targets = chat_ids or self._settings["chat_ids"]
        if not targets:
            return {"sent": False, "mode": "skip", "reason": "Chat ID sozlanmagan"}

        text = build_telegram_message(alert, animal_tag, farm_name)

        # Sozlanmagan bo'lsa — log
        if not self.is_configured:
            logger.info(
                f"📱 [DEV MODE] Telegram yuborilmadi (sozlanmagan). "
                f"Alert #{alert.id} | {alert.severity} | {', '.join(targets)}"
            )
            return {"sent": True, "mode": "log", "results": []}

        # Yuborish
        results = []
        all_ok  = True
        for chat_id in targets:
            res = await self.send_message(text, chat_id)
            results.append({"chat_id": chat_id, **res})
            if not res["ok"]:
                all_ok = False
                logger.error(
                    f"📱 Telegram xato: alert #{alert.id} → chat {chat_id}: {res['error']}"
                )
            else:
                logger.info(
                    f"📱 Telegram yuborildi: alert #{alert.id} → chat {chat_id}"
                )

        return {
            "sent":    all_ok,
            "mode":    "telegram",
            "results": results,
        }

    async def send_test_message(self, chat_id: str) -> dict:
        """
        Test xabari yuboradi — sozlamalarni tekshirish uchun.

        Args:
            chat_id: Telegram chat ID

        Returns:
            {"ok": bool, "message": str}
        """
        if not self.is_configured:
            return {
                "ok":      False,
                "message": "TELEGRAM_BOT_TOKEN yoki TELEGRAM_CHAT_IDS sozlanmagan",
            }

        test_text = (
            "✅ *Taurus Vision — Test Xabari*\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Telegram bildirishnomalar muvaffaqiyatli sozlandi\\!\n\n"
            "Endi ferma alertlari shu chatga yuboriladi\\."
        )

        result = await self.send_message(test_text, chat_id)
        return {
            "ok":      result["ok"],
            "message": "Test xabari yuborildi" if result["ok"] else result.get("error", "Xato"),
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_telegram_service: Optional[TelegramService] = None


def get_telegram_service() -> TelegramService:
    """Global TelegramService instance (singleton)."""
    global _telegram_service
    if _telegram_service is None:
        _telegram_service = TelegramService()
    return _telegram_service