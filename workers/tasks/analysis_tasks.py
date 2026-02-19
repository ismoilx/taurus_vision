"""
Analysis Celery Tasks — placeholder.
Kelajakda behavior analysis tasks shu yerga qo'shiladi.
"""
from workers.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


@celery_app.task(name="analysis.run_behavior", queue="default")
def run_behavior_analysis(animal_id: int):
    """Run behavior analysis for an animal. Placeholder."""
    logger.info(f"Behavior analysis task for animal: {animal_id}")
    return {"status": "ok", "animal_id": animal_id}
