"""
Celery Application Configuration.

Beat schedule — barcha scheduled tasklar shu yerda.
"""

from celery import Celery
from celery.schedules import crontab

celery_app = Celery("taurus_vision")

celery_app.config_from_object("workers.celery_config")

# ------------------------------------------------------------------ #
# BEAT SCHEDULE                                                        #
# ------------------------------------------------------------------ #

celery_app.conf.beat_schedule = {

    # ---- ADI ---------------------------------------------------- #

    # Kunlik ADI: har kecha 00:30 UTC
    "daily-adi-calculation": {
        "task":     "adi.calculate_daily",
        "schedule": crontab(hour=0, minute=30),
        "kwargs":   {
            "target_date":       None,   # None = bugun
            "force_recalculate": False,
        },
        "options": {"queue": "adi"},
    },

    # Ko'rinmayotganlar: har soat
    "check-missing-animals": {
        "task":     "adi.check_missing_animals",
        "schedule": crontab(minute=0),   # Har soat boshida
        "options":  {"queue": "adi"},
    },

    # O'sish tekshiruvi: har Dushanba 02:00 UTC
    "check-growth-stagnation": {
        "task":     "adi.check_growth_stagnation",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
        "options":  {"queue": "adi"},
    },

    # Alert tozalash: har Yakshanba 03:00 UTC
    "cleanup-old-alerts": {
        "task":     "adi.cleanup_old_alerts",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "kwargs":   {"keep_days": 90},
        "options":  {"queue": "maintenance"},
    },
}

celery_app.conf.task_routes = {
    "adi.*":         {"queue": "adi"},
    "detection.*":   {"queue": "detection"},
    "notification.*":{"queue": "notification"},
    "*.cleanup*":    {"queue": "maintenance"},
}

# Import tasks — Celery autodiscover uchun
celery_app.autodiscover_tasks([
    "workers.tasks.adi_tasks",
    "workers.tasks.detection_tasks",
    "workers.tasks.analysis_tasks",
    "workers.tasks.notification_tasks",
])
