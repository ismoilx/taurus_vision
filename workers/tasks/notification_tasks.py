"""
Notification Celery Tasks — placeholder.
Kelajakda email/SMS/push notification tasks shu yerga qo'shiladi.
"""
from workers.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="notification.send_alert", queue="notification")
def send_alert_notification(alert_id: int, channel: str = "email"):
    """Send alert notification. Placeholder."""
    logger.info(f"Notification task for alert: {alert_id}, channel: {channel}")
    return {"status": "ok", "alert_id": alert_id}
