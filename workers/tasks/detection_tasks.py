"""
Detection Celery Tasks — placeholder.
Kelajakda detection pipeline tasks shu yerga qo'shiladi.
"""
from workers.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="detection.process_frame", queue="detection")
def process_frame_task(camera_id: str, frame_data: dict):
    """Process a single camera frame. Placeholder."""
    logger.info(f"Detection task received for camera: {camera_id}")
    return {"status": "ok"}
