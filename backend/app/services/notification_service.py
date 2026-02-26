"""
Taurus Vision — Notification Service

Email va In-app bildirishnomalar yuborish servisi.

ARXITEKTURA:
    NotificationService   — asosiy servis, email/in-app yuborish
    EmailTemplate         — HTML email shablonlari
    InAppNotification     — Frontend uchun real-time notification

EMAIL FLOW:
    1. Alert yaratiladi (AlertService)
    2. send_alert_notification() chaqiriladi
    3. Severity bo'yicha recipient filtrlanadi
    4. HTML email generatsiya qilinadi
    5. SMTP orqali yuboriladi (asinxron)

SMTP KONFIGURATSIYA (.env):
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=noreply@taurus-vision.uz
    SMTP_PASSWORD=your-app-password
    SMTP_FROM=Taurus Vision <noreply@taurus-vision.uz>
    NOTIFICATION_EMAILS=admin@farm.uz,vet@farm.uz

FALLBACK:
    SMTP sozlanmagan bo'lsa — email log ga yoziladi (development mode).
"""

import logging
import smtplib
import ssl
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from app.models.alert import Alert, AlertSeverity, AlertType

logger = logging.getLogger(__name__)


# =============================================================================
# SEVERITY RANG VA EMOJI MAPPING
# =============================================================================

SEVERITY_CONFIG = {
    "critical": {
        "emoji":     "🔴",
        "color":     "#DC2626",
        "bg":        "#FEF2F2",
        "border":    "#FECACA",
        "label":     "KRITIK",
        "send_email": True,
    },
    "high": {
        "emoji":     "🟠",
        "color":     "#EA580C",
        "bg":        "#FFF7ED",
        "border":    "#FED7AA",
        "label":     "YUQORI",
        "send_email": True,
    },
    "medium": {
        "emoji":     "🟡",
        "color":     "#D97706",
        "bg":        "#FFFBEB",
        "border":    "#FDE68A",
        "label":     "O'RTA",
        "send_email": True,
    },
    "low": {
        "emoji":     "🟢",
        "color":     "#059669",
        "bg":        "#F0FDF4",
        "border":    "#A7F3D0",
        "label":     "PAST",
        "send_email": False,   # Faqat HIGH+ email yuboriladi
    },
}


# =============================================================================
# EMAIL TEMPLATE
# =============================================================================

def build_alert_email_html(alert: Alert, animal_tag: Optional[str] = None) -> str:
    """
    Alert uchun HTML email shabloni.

    Professional, mobile-friendly dizayn.
    Inline CSS — email klientlari uchun.

    Args:
        alert:      Alert ORM instance
        animal_tag: Jonivor teg raqami (ixtiyoriy)

    Returns:
        HTML string
    """
    cfg = SEVERITY_CONFIG.get(alert.severity, SEVERITY_CONFIG["medium"])

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # Jonivor va kamera ma'lumoti
    animal_info = ""
    if animal_tag:
        animal_info = f"""
        <tr>
            <td style="padding:8px 0; border-bottom:1px solid #F3F4F6;">
                <span style="color:#6B7280;font-size:13px;">Jonivor:</span>
                <strong style="float:right;font-size:13px;color:#0D1117;">{animal_tag}</strong>
            </td>
        </tr>"""

    camera_info = ""
    if alert.camera_id:
        camera_info = f"""
        <tr>
            <td style="padding:8px 0; border-bottom:1px solid #F3F4F6;">
                <span style="color:#6B7280;font-size:13px;">Kamera:</span>
                <strong style="float:right;font-size:13px;color:#0D1117;">{alert.camera_id}</strong>
            </td>
        </tr>"""

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
    }
    type_label = alert_type_labels.get(alert.alert_type, alert.alert_type)

    return f"""<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Taurus Vision — {cfg['label']} Alert</title>
</head>
<body style="margin:0;padding:0;background:#F9FAFB;font-family:'Segoe UI',Arial,sans-serif;">

<table width="100%" cellpadding="0" cellspacing="0" style="background:#F9FAFB;padding:32px 16px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">

  <!-- HEADER -->
  <tr>
    <td style="background:#1E3EB4;border-radius:12px 12px 0 0;padding:24px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <div style="color:#fff;font-size:11px;font-weight:600;letter-spacing:2px;text-transform:uppercase;margin-bottom:4px;">
              TAURUS VISION
            </div>
            <div style="color:rgba(255,255,255,0.85);font-size:13px;">
              Ferma Monitoring Tizimi
            </div>
          </td>
          <td align="right">
            <div style="font-size:28px;">{cfg['emoji']}</div>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- SEVERITY BADGE -->
  <tr>
    <td style="background:{cfg['bg']};border-left:4px solid {cfg['color']};padding:16px 32px;">
      <span style="display:inline-block;background:{cfg['color']};color:#fff;
                   font-size:11px;font-weight:700;letter-spacing:1px;
                   padding:4px 12px;border-radius:20px;">
        {cfg['label']} DARAJALI OGOHLANTIRISH
      </span>
    </td>
  </tr>

  <!-- MAIN CONTENT -->
  <tr>
    <td style="background:#fff;padding:28px 32px;">

      <h2 style="margin:0 0 8px;font-size:20px;font-weight:700;color:#0D1117;">
        {alert.title}
      </h2>

      <p style="margin:0 0 24px;font-size:14px;color:#4B5563;line-height:1.6;">
        {alert.description}
      </p>

      <!-- DETAILS TABLE -->
      <div style="background:#F9FAFB;border:1px solid #E5E7EB;border-radius:10px;padding:16px 20px;margin-bottom:24px;">
        <div style="font-size:12px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:1px;margin-bottom:12px;">
          Tafsilotlar
        </div>
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td style="padding:8px 0; border-bottom:1px solid #F3F4F6;">
              <span style="color:#6B7280;font-size:13px;">Alert turi:</span>
              <strong style="float:right;font-size:13px;color:#0D1117;">{type_label}</strong>
            </td>
          </tr>
          {animal_info}
          {camera_info}
          <tr>
            <td style="padding:8px 0; border-bottom:1px solid #F3F4F6;">
              <span style="color:#6B7280;font-size:13px;">Vaqt:</span>
              <strong style="float:right;font-size:13px;color:#0D1117;">{now_str}</strong>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 0;">
              <span style="color:#6B7280;font-size:13px;">Alert ID:</span>
              <strong style="float:right;font-size:13px;color:#0D1117;">#{alert.id}</strong>
            </td>
          </tr>
        </table>
      </div>

      <!-- CTA BUTTON -->
      <div style="text-align:center;">
        <a href="http://localhost:5173/alerts"
           style="display:inline-block;background:#1E3EB4;color:#fff;
                  text-decoration:none;padding:12px 32px;border-radius:8px;
                  font-size:14px;font-weight:700;">
          Alertni Ko'rish →
        </a>
      </div>

    </td>
  </tr>

  <!-- FOOTER -->
  <tr>
    <td style="background:#F9FAFB;border-radius:0 0 12px 12px;padding:16px 32px;
               border-top:1px solid #E5E7EB;">
      <p style="margin:0;font-size:12px;color:#9CA3AF;text-align:center;">
        Bu xabar Taurus Vision monitoring tizimi tomonidan avtomatik yuborildi.<br>
        Email bildirishnomalarni o'chirish uchun tizim sozlamalariga kiring.
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>

</body>
</html>"""


def build_alert_email_text(alert: Alert, animal_tag: Optional[str] = None) -> str:
    """Plain text email (HTML klientlar uchun fallback)."""
    cfg = SEVERITY_CONFIG.get(alert.severity, SEVERITY_CONFIG["medium"])
    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        f"TAURUS VISION — {cfg['label']} DARAJALI OGOHLANTIRISH",
        "=" * 50,
        "",
        f"Sarlavha: {alert.title}",
        "",
        f"Tavsif: {alert.description}",
        "",
        "Tafsilotlar:",
        f"  Alert turi:  {alert.alert_type}",
    ]
    if animal_tag:
        lines.append(f"  Jonivor:     {animal_tag}")
    if alert.camera_id:
        lines.append(f"  Kamera:      {alert.camera_id}")
    lines += [
        f"  Vaqt:        {now_str}",
        f"  Alert ID:    #{alert.id}",
        "",
        "Alertni ko'rish: http://localhost:5173/alerts",
        "",
        "---",
        "Bu xabar Taurus Vision tomonidan avtomatik yuborildi.",
    ]
    return "\n".join(lines)


# =============================================================================
# NOTIFICATION SERVICE
# =============================================================================

class NotificationService:
    """
    Email va bildirishnoma yuborish servisi.

    SMTP sozlanmagan bo'lsa — log ga yozadi (development mode).
    Bu tizimni test muhitida ham ishlashini ta'minlaydi.

    FOYDALANISH:
        service = NotificationService()

        # Alert yuborish
        await service.send_alert_email(alert, recipients=["admin@farm.uz"])

        # Sozlamalarni tekshirish
        ok = await service.test_smtp_connection()
    """

    def __init__(self) -> None:
        self._settings = self._load_smtp_settings()

    def _load_smtp_settings(self) -> dict:
        """
        SMTP sozlamalarini environment o'zgaruvchilardan yuklaydi.

        .env da bo'lmasa — development mode (faqat log).
        """
        import os
        return {
            "host":       os.getenv("SMTP_HOST", ""),
            "port":       int(os.getenv("SMTP_PORT", "587")),
            "user":       os.getenv("SMTP_USER", ""),
            "password":   os.getenv("SMTP_PASSWORD", ""),
            "from_addr":  os.getenv("SMTP_FROM", "Taurus Vision <noreply@taurus-vision.uz>"),
            "recipients": [
                e.strip()
                for e in os.getenv("NOTIFICATION_EMAILS", "").split(",")
                if e.strip()
            ],
            "enabled":    bool(os.getenv("SMTP_HOST", "")),
        }

    @property
    def is_configured(self) -> bool:
        """SMTP to'liq sozlanganmi?"""
        return bool(
            self._settings["host"]
            and self._settings["user"]
            and self._settings["password"]
            and self._settings["recipients"]
        )

    def get_recipients(
        self,
        alert: Alert,
        extra_recipients: Optional[list[str]] = None,
    ) -> list[str]:
        """
        Alert uchun recipient ro'yxatini qaytaradi.

        LOW severity uchun email yuborilmaydi (SEVERITY_CONFIG ga qarang).

        Args:
            alert:             Alert instance
            extra_recipients:  Qo'shimcha recipient emaillar

        Returns:
            Email address ro'yxati
        """
        cfg = SEVERITY_CONFIG.get(alert.severity, SEVERITY_CONFIG["medium"])
        if not cfg.get("send_email", True):
            return []

        recipients = list(self._settings["recipients"])
        if extra_recipients:
            recipients += [e for e in extra_recipients if e not in recipients]

        return recipients

    async def send_alert_email(
        self,
        alert:      Alert,
        animal_tag: Optional[str]   = None,
        recipients: Optional[list[str]] = None,
    ) -> dict:
        """
        Alert uchun email yuboradi.

        SMTP sozlanmagan bo'lsa — log ga yozadi va muvaffaqiyat qaytaradi.
        Bu development muhitida tizimni buzmaslikni ta'minlaydi.

        Args:
            alert:      Alert ORM instance
            animal_tag: Jonivor teg raqami (ko'rsatish uchun)
            recipients: Override recipients (None = settings dan)

        Returns:
            {
                "sent": bool,
                "recipients": [...],
                "mode": "smtp" | "log",
                "error": str | None,
            }
        """
        # Recipient aniqlash
        to_list = recipients or self.get_recipients(alert)
        if not to_list:
            return {
                "sent":       False,
                "recipients": [],
                "mode":       "skip",
                "reason":     f"Severity '{alert.severity}' uchun email yuborilmaydi",
            }

        # Email kontent
        html_body = build_alert_email_html(alert, animal_tag)
        text_body = build_alert_email_text(alert, animal_tag)
        cfg       = SEVERITY_CONFIG.get(alert.severity, SEVERITY_CONFIG["medium"])
        subject   = f"{cfg['emoji']} [{cfg['label']}] {alert.title} — Taurus Vision"

        # SMTP sozlanmagan → log ga yoz
        if not self.is_configured:
            logger.info(
                "📧 [DEV MODE] Email yuborilmadi (SMTP sozlanmagan). Log:\n"
                f"  To:      {', '.join(to_list)}\n"
                f"  Subject: {subject}\n"
                f"  Alert:   #{alert.id} | {alert.alert_type} | {alert.severity}"
            )
            return {
                "sent":       True,
                "recipients": to_list,
                "mode":       "log",
                "message":    "SMTP sozlanmagan — log ga yozildi",
            }

        # SMTP orqali yuborish
        try:
            result = await self._send_via_smtp(
                to_list   = to_list,
                subject   = subject,
                html_body = html_body,
                text_body = text_body,
            )
            logger.info(
                f"📧 Email yuborildi: alert #{alert.id} → {', '.join(to_list)}"
            )
            return {
                "sent":       True,
                "recipients": to_list,
                "mode":       "smtp",
                **result,
            }

        except Exception as exc:
            logger.error(
                f"📧 Email yuborishda xato: alert #{alert.id}: {exc}",
                exc_info=True,
            )
            return {
                "sent":       False,
                "recipients": to_list,
                "mode":       "smtp",
                "error":      str(exc),
            }

    async def _send_via_smtp(
        self,
        to_list:   list[str],
        subject:   str,
        html_body: str,
        text_body: str,
    ) -> dict:
        """
        Haqiqiy SMTP orqali email yuborish.

        TLS (port 587) va SSL (port 465) ikkalasini ham qo'llab-quvvatlaydi.

        Args:
            to_list:   Recipient emaillar
            subject:   Email mavzusi
            html_body: HTML kontent
            text_body: Plain text fallback

        Returns:
            {"message_id": str}

        Raises:
            smtplib.SMTPException: Yuborishda xato
        """
        import asyncio

        s = self._settings

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = s["from_addr"]
        msg["To"]      = ", ".join(to_list)
        msg["X-Mailer"] = "Taurus Vision Notification System"

        msg.attach(MIMEText(text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html",  "utf-8"))

        def _send_sync():
            if s["port"] == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(s["host"], s["port"], context=context) as server:
                    server.login(s["user"], s["password"])
                    server.sendmail(s["from_addr"], to_list, msg.as_string())
            else:
                # Port 587 — STARTTLS
                with smtplib.SMTP(s["host"], s["port"]) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(s["user"], s["password"])
                    server.sendmail(s["from_addr"], to_list, msg.as_string())

        # Sync SMTP ni thread pool da ishga tushiramiz
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _send_sync)

        return {"message_id": msg.get("Message-ID", "unknown")}

    async def test_smtp_connection(self) -> dict:
        """
        SMTP ulanishini test qiladi.

        Returns:
            {"ok": bool, "message": str}
        """
        if not self.is_configured:
            return {
                "ok":      False,
                "message": "SMTP sozlanmagan (SMTP_HOST, SMTP_USER, SMTP_PASSWORD kerak)",
            }

        s = self._settings
        try:
            import asyncio

            def _test():
                if s["port"] == 465:
                    context = ssl.create_default_context()
                    with smtplib.SMTP_SSL(s["host"], s["port"], context=context) as server:
                        server.login(s["user"], s["password"])
                else:
                    with smtplib.SMTP(s["host"], s["port"]) as server:
                        server.ehlo()
                        server.starttls()
                        server.login(s["user"], s["password"])

            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _test)

            return {"ok": True, "message": f"SMTP ulanish muvaffaqiyatli: {s['host']}:{s['port']}"}

        except Exception as exc:
            return {"ok": False, "message": f"SMTP xato: {exc}"}

    def get_settings_info(self) -> dict:
        """
        Hozirgi SMTP sozlamalarini (parolsiz) qaytaradi.

        Frontend settings sahifasi uchun.
        """
        s = self._settings
        return {
            "configured":   self.is_configured,
            "smtp_host":    s["host"] or "(sozlanmagan)",
            "smtp_port":    s["port"],
            "smtp_user":    s["user"] or "(sozlanmagan)",
            "from_address": s["from_addr"],
            "recipients":   s["recipients"],
            "total_recipients": len(s["recipients"]),
        }


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_notification_service: Optional[NotificationService] = None


def get_notification_service() -> NotificationService:
    """Global NotificationService instance (singleton)."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service