"""
Detection repository — raw YOLO event log data access.

RESPONSIBILITY: Database access only. No business logic.
"""

from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection import Detection
from app.core.exceptions import DatabaseError
import logging

logger = logging.getLogger(__name__)


class DetectionRepository:
    """
    Repository for Detection entity.

    Args:
        db: AsyncSession injected via FastAPI Depends()
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------

    async def create(
        self,
        animal_id: Optional[int],
        camera_id: str,
        timestamp: datetime,
        confidence: float,
        class_id: int,
        class_name: str,
        bbox: dict,
        estimated_weight: Optional[float] = None,
        frame_number: Optional[int] = None,
        inference_time_ms: Optional[float] = None,
    ) -> Detection:
        """
        Insert a new detection event.

        Returns:
            Persisted Detection instance with generated id
        """
        try:
            detection = Detection(
                animal_id=animal_id,
                camera_id=camera_id,
                timestamp=timestamp,
                confidence=confidence,
                class_id=class_id,
                class_name=class_name,
                bbox=bbox,
                estimated_weight=estimated_weight,
                frame_number=frame_number,
                inference_time_ms=inference_time_ms,
            )
            self.db.add(detection)
            await self.db.flush()
            await self.db.refresh(detection)
            logger.debug(f"[repo] Detection created id={detection.id} camera={camera_id}")
            return detection
        except Exception as exc:
            logger.error(f"[repo] Detection.create failed: {exc}", exc_info=True)
            raise DatabaseError(
                message="Failed to create detection",
                details={"error": str(exc)},
            ) from exc

    # -------------------------------------------------------------------------
    # READ
    # -------------------------------------------------------------------------

    async def get_by_id(self, detection_id: int) -> Optional[Detection]:
        """Fetch single detection by PK."""
        try:
            result = await self.db.execute(
                select(Detection).where(Detection.id == detection_id)
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(
                message=f"Failed to fetch detection id={detection_id}",
                details={"error": str(exc)},
            ) from exc

    async def get_by_animal(
        self,
        animal_id: int,
        limit: int = 50,
    ) -> Sequence[Detection]:
        """
        Get recent detections for a specific animal.

        Args:
            animal_id: FK to animals table
            limit:     Max rows to return (newest first)
        """
        try:
            result = await self.db.execute(
                select(Detection)
                .where(Detection.animal_id == animal_id)
                .order_by(desc(Detection.timestamp))
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as exc:
            raise DatabaseError(
                message=f"Failed to fetch detections for animal {animal_id}",
                details={"error": str(exc)},
            ) from exc

    async def get_recent(
        self,
        limit: int = 100,
        camera_id: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> Sequence[Detection]:
        """
        Get most recent detections across all cameras.

        Args:
            limit:          Max rows
            camera_id:      Filter by camera (optional)
            min_confidence: Filter low-quality detections (optional)
        """
        try:
            conditions = []
            if camera_id:
                conditions.append(Detection.camera_id == camera_id)
            if min_confidence > 0:
                conditions.append(Detection.confidence >= min_confidence)

            stmt = select(Detection).order_by(desc(Detection.timestamp)).limit(limit)
            if conditions:
                stmt = stmt.where(and_(*conditions))

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as exc:
            raise DatabaseError(
                message="Failed to fetch recent detections",
                details={"error": str(exc)},
            ) from exc

    async def count_by_animal(self, animal_id: int) -> int:
        """Total detection count for one animal."""
        try:
            result = await self.db.execute(
                select(func.count())
                .select_from(Detection)
                .where(Detection.animal_id == animal_id)
            )
            return result.scalar_one()
        except Exception as exc:
            raise DatabaseError(
                message="Failed to count detections",
                details={"error": str(exc)},
            ) from exc

    async def count_in_range(
        self,
        start: datetime,
        end: datetime,
        camera_id: Optional[str] = None,
    ) -> int:
        """Count detections between two timestamps (for analytics)."""
        try:
            conditions = [
                Detection.timestamp >= start,
                Detection.timestamp <= end,
            ]
            if camera_id:
                conditions.append(Detection.camera_id == camera_id)

            result = await self.db.execute(
                select(func.count())
                .select_from(Detection)
                .where(and_(*conditions))
            )
            return result.scalar_one()
        except Exception as exc:
            raise DatabaseError(
                message="Failed to count detections in range",
                details={"error": str(exc)},
            ) from exc
