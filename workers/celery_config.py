"""
Taurus Vision — Celery Worker Konfiguratsiyasi

Barcha sozlamalar environment variable orqali override qilinadi.
Har bir queue alohida exchange bilan izolyatsiyalangan.

QUEUE IERARXIYASI (prioritet yuqoridan pastga):
  notification  — Email (foydalanuvchi kutmoqda, eng tez)
  adi           — ADI hisoblash (kech. sog'liq qarorlari)
  detection     — Kamera monitoring
  prediction    — ML bashorat (og'ir, kecha bajarilishi mumkin)
  training      — YOLO fine-tuning (CPU intensive, concurrency=1 !)
  default       — Umumiy vazifalar
  maintenance   — Tozalash (eng past prioritet)

MUHIM: training queue ni alohida worker da ishlatish kerak:
  celery -A workers.celery_app worker -Q training --concurrency=1 -n training@%h
"""

import os

# =============================================================================
# BROKER & BACKEND
# =============================================================================

broker_url              = os.getenv("CELERY_BROKER_URL",     "redis://redis:6379/0")
result_backend          = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# =============================================================================
# SERIALIZATION
# =============================================================================

task_serializer   = "json"
result_serializer = "json"
accept_content    = ["json"]
timezone          = "UTC"
enable_utc        = True

# =============================================================================
# TASK EXECUTION
# =============================================================================

task_track_started         = True
task_acks_late             = True
worker_prefetch_multiplier = 1     # Bir vaqtda faqat 1 task (og'ir tasklarda muhim)

# =============================================================================
# QUEUE DEFINITIONS
# =============================================================================

task_queues = {
    "default":      {"exchange": "default",      "routing_key": "default"},
    "adi":          {"exchange": "adi",           "routing_key": "adi"},
    "detection":    {"exchange": "detection",     "routing_key": "detection"},
    "notification": {"exchange": "notification",  "routing_key": "notification"},
    "prediction":   {"exchange": "prediction",    "routing_key": "prediction"},
    "training":     {"exchange": "training",      "routing_key": "training"},   # Sprint 15-16
    "maintenance":  {"exchange": "maintenance",   "routing_key": "maintenance"},
}

task_default_queue = "default"

# =============================================================================
# RETRY
# =============================================================================

task_max_retries         = 3
task_default_retry_delay = 60   # 1 daqiqa

# =============================================================================
# RESULT STORE
# =============================================================================

result_expires = 60 * 60 * 24   # 24 soat

# =============================================================================
# BROKER
# =============================================================================

broker_connection_retry_on_startup = True
broker_transport_options = {
    "visibility_timeout": 14400,   # 4 soat — YOLO training uzoq davom etishi mumkin
}