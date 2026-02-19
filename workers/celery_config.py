"""
Celery Configuration.
"""
import os

# Broker va Backend
broker_url = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/1")

# Serialization
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "UTC"
enable_utc = True

# Task settings
task_track_started = True
task_acks_late = True
worker_prefetch_multiplier = 1

# Queues
task_queues = {
    "default":     {"exchange": "default"},
    "adi":         {"exchange": "adi"},
    "detection":   {"exchange": "detection"},
    "notification":{"exchange": "notification"},
    "maintenance": {"exchange": "maintenance"},
}
task_default_queue = "default"

# Retry settings
task_max_retries = 3
task_default_retry_delay = 60  # 1 daqiqa

# Result expiry
result_expires = 60 * 60 * 24  # 24 soat
