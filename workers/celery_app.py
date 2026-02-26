"""
Celery Application Configuration — Sprint 6

Beat schedule:
  00:30 UTC  — Kunlik ADI hisoblash (barcha aktiv jonivorlar)
  Har soat   — Ko'rinmayotgan jonivorlarni tekshirish
  Dushanba 02:00 — O'sish to'xtagan jonivorlar
  Yakshanba 03:00 — Eski alertlarni tozalash
"""

from celery import Celery
from celery.schedules import crontab

celery_app = Celery("taurus_vision")
celery_app.config_from_object("workers.celery_config")

# ── Beat Schedule ─────────────────────────────────────────────────────────────

celery_app.conf.beat_schedule = {

    "daily-adi-calculation": {
        "task":     "adi.calculate_daily",
        "schedule": crontab(hour=0, minute=30),
        "kwargs":   {"target_date": None, "force_recalculate": False},
        "options":  {"queue": "adi"},
    },

    "check-missing-animals": {
        "task":     "adi.check_missing_animals",
        "schedule": crontab(minute=0),        # Har soat
        "options":  {"queue": "adi"},
    },

    "check-growth-stagnation": {
        "task":     "adi.check_growth_stagnation",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),  # Dushanba
        "options":  {"queue": "adi"},
    },

    "cleanup-old-alerts": {
        "task":     "adi.cleanup_old_alerts",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),  # Yakshanba
        "kwargs":   {"keep_days": 90},
        "options":  {"queue": "maintenance"},
    },

    "daily-digest-email": {
        "task":     "notification.send_daily_digest",
        "schedule": crontab(hour=7, minute=0),   # Har kuni 07:00 UTC
        "options":  {"queue": "notification"},
    },
}

celery_app.conf.task_routes = {
    "adi.*":          {"queue": "adi"},
    "detection.*":    {"queue": "detection"},
    "notification.*": {"queue": "notification"},
    "*.cleanup*":     {"queue": "maintenance"},
}

# ── Task Registration ─────────────────────────────────────────────────────────
# autodiscover_tasks() paketlar uchun mo'ljallangan.
# Biz modul yo'llarini to'g'ridan-to'g'ri import qilamiz.

from workers.tasks import (  # noqa: E402, F401
    adi_tasks,
    analysis_tasks,
    detection_tasks,
    notification_tasks,
)