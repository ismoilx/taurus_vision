"""
Celery Application Configuration — Sprint 9-10

Beat schedule:
  00:30 UTC        — Kunlik ADI hisoblash (barcha aktiv jonivorlar)
  Har soat         — Ko'rinmayotgan jonivorlarni tekshirish
  Dushanba 02:00   — O'sish to'xtagan jonivorlar
  Yakshanba 03:00  — Eski alertlarni tozalash

  Sprint 9-10 (yangi):
  Har 5 daqiqa     — Kamera sog'lig'ini tekshirish (health_check_cameras)
  Har 1 daqiqa     — Kamera statistikasini cache qilish (aggregate_camera_stats)
  Har 6 soat       — Anomaliya aniqlash (detect_anomalies)
  Har kuni 23:00   — Kunlik ferma xulosasi (generate_daily_summary)
  Hafta da bir     — Eski detection larni tozalash (cleanup_stale_detections)
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
# ── Sprint 9-10 tasklar qo'shildi ─────────────────────────────────────────────
_sprint910_tasks = {
    "camera-health-check": {
        "task":     "detection.health_check_cameras",
        "schedule": crontab(minute="*/5"),
        "options":  {"queue": "default"},
    },
    "camera-stats-cache": {
        "task":     "detection.aggregate_camera_stats",
        "schedule": crontab(minute="*"),
        "options":  {"queue": "default"},
    },
    "anomaly-detection": {
        "task":     "analysis.detect_anomalies",
        "schedule": crontab(minute=0, hour="*/6"),
        "options":  {"queue": "default"},
    },
    "daily-farm-summary": {
        "task":     "analysis.generate_daily_summary",
        "schedule": crontab(hour=23, minute=0),
        "options":  {"queue": "default"},
    },
    "cleanup-stale-detections": {
        "task":     "detection.cleanup_stale_detections",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "kwargs":   {"days_to_keep": 90},
        "options":  {"queue": "maintenance"},
    },
}
celery_app.conf.beat_schedule.update(_sprint910_tasks)
