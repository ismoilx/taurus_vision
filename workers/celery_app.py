"""
Taurus Vision — Celery Application

Barcha background task lari uchun markaziy Celery konfiguratsiyasi.

BEAT SCHEDULE (UTC vaqtida):
  00:30  — Kunlik ADI hisoblash (barcha aktiv jonivorlar)
  01:00  — Kunlik sog'liq bashorati (ADI dan keyin)
  02:00  — O'sish to'xtagan jonivorlar (Dushanba)
  03:00  — Eski alertlarni tozalash (Yakshanba)
  03:00  — Eski bashoratlarni tozalash (Yakshanba)
  05:00  — ML modellarini qayta o'rgatish
  07:00  — Kunlik digest email
  23:00  — Kunlik ferma xulosasi
  Har soat       — Ko'rinmayotgan jonivorlarni tekshirish
  Har 5 daqiqa   — Kamera sog'lig'ini tekshirish
  Har 6 soat     — Anomaliya aniqlash
  Har daqiqa     — Kamera statistikasini Redis ga cache qilish
  Hafta da bir   — Eski detection larni tozalash (Yakshanba)

QUEUE ARXITEKTURASI:
  default      — Umumiy vazifalar (behavior, stats, anomaly)
  adi          — ADI hisoblash (og'ir, DB intensive)
  detection    — Kamera va pipeline tasklari
  notification — Email xabarnomalar
  prediction   — ML bashorat va o'rgatish
  training     — YOLO fine-tuning (CPU intensive, concurrency=1)
  maintenance  — Tozalash va xizmat vazifalari

TRAINING WORKER BUYRUG'I (alohida worker, concurrency=1):
  celery -A workers.celery_app worker -Q training --concurrency=1 -n training@%h

ASOSIY WORKER BUYRUG'I:
  celery -A workers.celery_app worker -Q default,adi,detection,notification,prediction,maintenance
"""

from celery import Celery
from celery.schedules import crontab

celery_app = Celery("taurus_vision")
celery_app.config_from_object("workers.celery_config")


# =============================================================================
# TASK ROUTING
# =============================================================================

celery_app.conf.task_routes = {
    # ADI hisoblash — DB intensive, alohida queue
    "adi.*":          {"queue": "adi"},

    # Kamera va detection pipeline
    "detection.*":    {"queue": "detection"},

    # Email va xabarnomalar
    "notification.*": {"queue": "notification"},

    # ML bashorat va o'rgatish — CPU intensive
    "predictions.*":  {"queue": "prediction"},

    # Xulosa va anomaliya tahlili
    "analysis.*":     {"queue": "default"},

    # Sprint 15-16: YOLO fine-tuning — alohida worker, concurrency=1
    "training.*":     {"queue": "training"},

    # Tozalash vazifalari
    "*.cleanup*":     {"queue": "maintenance"},
    "*.cleanup_*":    {"queue": "maintenance"},
}


# =============================================================================
# BEAT SCHEDULE
# =============================================================================

celery_app.conf.beat_schedule = {

    # ── ADI (Sprint 1-5) ──────────────────────────────────────────────────

    "daily-adi-calculation": {
        "task":     "adi.calculate_daily",
        "schedule": crontab(hour=0, minute=30),
        "kwargs":   {"target_date": None, "force_recalculate": False},
        "options":  {"queue": "adi"},
    },
    "check-missing-animals": {
        "task":     "adi.check_missing_animals",
        "schedule": crontab(minute=0),
        "options":  {"queue": "adi"},
    },
    "check-growth-stagnation": {
        "task":     "adi.check_growth_stagnation",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
        "options":  {"queue": "adi"},
    },
    "cleanup-old-alerts": {
        "task":     "adi.cleanup_old_alerts",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
        "kwargs":   {"keep_days": 90},
        "options":  {"queue": "maintenance"},
    },

    # ── Notification (Sprint 11) ──────────────────────────────────────────

    "daily-digest-email": {
        "task":     "notification.send_daily_digest",
        "schedule": crontab(hour=7, minute=0),
        "options":  {"queue": "notification"},
    },

    # ── Detection / Camera (Sprint 9-10) ─────────────────────────────────

    "camera-health-check": {
        "task":     "detection.health_check_cameras",
        "schedule": crontab(minute="*/5"),
        "options":  {"queue": "detection"},
    },
    "camera-stats-cache": {
        "task":     "detection.aggregate_camera_stats",
        "schedule": crontab(minute="*"),
        "options":  {"queue": "detection"},
    },
    "cleanup-stale-detections": {
        "task":     "detection.cleanup_stale_detections",
        "schedule": crontab(hour=4, minute=0, day_of_week=0),
        "kwargs":   {"days_to_keep": 90},
        "options":  {"queue": "maintenance"},
    },

    # ── Analysis / Behavior (Sprint 9-12) ────────────────────────────────

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

    # ── Health Predictions (Sprint 13-14) ─────────────────────────────────

    "daily-predictions": {
        "task":     "predictions.run_daily",
        "schedule": crontab(hour=1, minute=0),
        "options":  {"queue": "prediction"},
    },
    "train-prediction-models": {
        "task":     "predictions.train_models",
        "schedule": crontab(hour=5, minute=0),
        "options":  {"queue": "prediction"},
    },
    "cleanup-old-predictions": {
        "task":     "predictions.cleanup_old",
        "schedule": crontab(hour=3, minute=30, day_of_week=0),
        "options":  {"queue": "maintenance"},
    },

    # ── Training (Sprint 15-16) ───────────────────────────────────────────
    # Training task beat schedule da yo'q — faqat API orqali qo'lda ishga tushiriladi.
    # Bu yerda faqat eski training run larni tozalash mavjud.

    "cleanup-old-training-runs": {
        "task":     "training.cleanup_old_runs",
        "schedule": crontab(hour=4, minute=30, day_of_week=0),   # Yakshanba 04:30
        "kwargs":   {"keep_days": 30},
        "options":  {"queue": "maintenance"},
    },
}


# =============================================================================
# TASK REGISTRATION
# =============================================================================

from workers.tasks import (  # noqa: E402, F401
    adi_tasks,
    analysis_tasks,
    detection_tasks,
    notification_tasks,
    prediction_tasks,
    training_tasks,        # Sprint 15-16
)