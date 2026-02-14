"""
Detection model — raw YOLO event log.

Every frame where YOLO fires goes here as an immutable record.
Separate from WeightMeasurement by design:

  Detection        → raw, high-frequency, all events (audit trail)
  WeightMeasurement → processed, quality-filtered (business data)

Optimised for time-series inserts and camera/animal analytics.
"""

from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    String,
    Float,
    Integer,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
    JSON,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class Detection(BaseModel):
    """
    Raw YOLO detection event.

    One row = one bounding box in one camera frame.

    Attributes:
        animal_id:          FK → Animal (NULL if unidentified)
        camera_id:          Camera that fired (e.g. "CAM-NORTH-01")
        timestamp:          UTC time of the frame
        confidence:         YOLO score 0.0–1.0
        class_id:           COCO class id (19 = cow, 17 = horse …)
        class_name:         Human-readable label ("cow")
        bbox:               Normalised bounding box {"x","y","w","h"}
        estimated_weight:   Weight estimate in kg (optional)
        frame_number:       Frame counter from the camera stream
        inference_time_ms:  YOLO wall-clock latency

    Indexes:
        - (animal_id, timestamp) — per-animal history
        - (camera_id, timestamp) — per-camera analytics
        - (class_id,  timestamp) — species-level queries
        - timestamp              — global time-range scans
    """

    __tablename__ = "detections"

    # ------------------------------------------------------------------
    # Columns
    # ------------------------------------------------------------------

    animal_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("animals.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Identified animal; NULL when animal could not be matched",
    )

    camera_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Camera identifier",
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="UTC timestamp of the captured frame",
    )

    confidence: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="YOLO detection confidence (0.0–1.0)",
    )

    class_id: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="COCO dataset class id",
    )

    class_name: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Human-readable COCO class name",
    )

    # Normalised bounding box: all values in [0, 1] relative to frame size
    # {"x": cx, "y": cy, "w": width, "h": height}
    bbox: Mapped[dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        comment="Normalised bounding box (cx, cy, w, h) in [0,1]",
    )

    estimated_weight: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Weight estimate in kg (if calculated at detection time)",
    )

    frame_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Sequential frame number from the camera stream",
    )

    inference_time_ms: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="YOLO inference latency in milliseconds",
    )

    # ------------------------------------------------------------------
    # Relationships
    # ------------------------------------------------------------------

    animal: Mapped[Optional["Animal"]] = relationship(  # type: ignore[name-defined]
        "Animal",
        back_populates="detections",
        lazy="selectin",
    )

    # ------------------------------------------------------------------
    # Constraints & composite indexes
    # ------------------------------------------------------------------

    __table_args__ = (
        CheckConstraint(
            "confidence >= 0.0 AND confidence <= 1.0",
            name="ck_detection_confidence_range",
        ),
        CheckConstraint(
            "estimated_weight IS NULL OR estimated_weight > 0",
            name="ck_detection_weight_positive",
        ),
        Index("ix_detections_animal_time",  "animal_id",  "timestamp"),
        Index("ix_detections_camera_time",  "camera_id",  "timestamp"),
        Index("ix_detections_class_time",   "class_id",   "timestamp"),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<Detection(id={self.id}, "
            f"camera={self.camera_id!r}, "
            f"class={self.class_name!r}, "
            f"conf={self.confidence:.2f})>"
        )

    @property
    def is_high_confidence(self) -> bool:
        """True when confidence ≥ 0.80 (threshold for reliable data)."""
        return self.confidence >= 0.80

    @property
    def bbox_area(self) -> float:
        """Normalised bounding-box area (0–1).  Useful for size-based filters."""
        return self.bbox.get("w", 0.0) * self.bbox.get("h", 0.0)
