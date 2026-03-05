"""
Weight Measurement model for AI-generated and scale-based weight measurements.

YANGILANISH (Q7 — Tarozi integratsiyasi):
  source          — o'lchovning manbai: camera_ai | manual | scale_serial | scale_api
  actual_weight_kg — tarozidan kelgan haqiqiy vazn (AI taxmin bilan taqqoslash uchun)
  scale_id        — qaysi tarozi qurilmadan kelgani
  notes           — foydalanuvchi izohi

DESIGN CONSIDERATIONS:
- High write volume (multiple cameras, frequent measurements)
- Time-series data (indexed by timestamp)
- Store raw AI data (JSONB) for future model improvements
- Relationship to Animal entity
"""

import enum
from datetime import datetime
from typing import Optional, Any
from sqlalchemy import (
    String,
    Float,
    DateTime,
    ForeignKey,
    Index,
    CheckConstraint,
    JSON,
    Enum as SQLEnum,
    Integer,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class WeightSource(str, enum.Enum):
    CAMERA_AI    = "camera_ai"    # YOLO + bbox area taxmini
    MANUAL       = "manual"       # Foydalanuvchi qo'lda kiritdi
    SCALE_SERIAL = "scale_serial" # USB/RS-232 tarozi
    SCALE_API    = "scale_api"    # Ethernet/Wi-Fi tarozi


class WeightMeasurement(BaseModel):
    """
    AI-generated weight measurement record.
    
    Each record represents a single weight estimation from a camera at a point in time.
    Designed for high-frequency inserts and time-series queries.
    
    Attributes:
        animal_id: Foreign key to Animal
        timestamp: When measurement was taken (indexed for time-series queries)
        estimated_weight_kg: AI-predicted weight in kilograms
        confidence_score: AI model confidence (0.0 - 1.0)
        camera_id: Identifier of the camera that captured this measurement
        raw_ai_data: JSONB field storing raw ML output for retraining
        
    Relationships:
        animal: The Animal this measurement belongs to
        
    Indexes:
        - animal_id + timestamp (for per-animal time-series queries)
        - timestamp only (for global time-series queries)
        - confidence_score (for filtering low-quality measurements)
    """
    
    __tablename__ = "weight_measurements"
    
    # Foreign Key to Animal
    animal_id: Mapped[int] = mapped_column(
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to the animal being measured",
    )
    
    # Measurement Data
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
        comment="When the measurement was captured (camera timestamp)",
    )
    
    estimated_weight_kg: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        comment="AI-estimated weight in kilograms",
    )
    
    confidence_score: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        index=True,
        comment="AI model confidence score (0.0 to 1.0)",
    )
    
    # Camera Information
    camera_id: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Identifier of the camera that captured this measurement",
    )
    
    # Raw AI Data (for model retraining and debugging)
    raw_ai_data: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment="""
        Raw AI model output stored as JSONB. May include:
        - bounding_box: {x, y, width, height}
        - segmentation_mask: compressed polygon coordinates
        - feature_vector: embedding from neural network
        - model_version: version of the AI model used
        - processing_time_ms: inference latency
        
        This data is crucial for:
        1. Model retraining (ground truth comparison)
        2. Debugging incorrect predictions
        3. A/B testing different model versions
        4. Performance monitoring
        """,
    )
    
    # Optional: Image reference (if we store frames)
    image_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Path to stored image frame (if enabled)",
    )

    # ------------------------------------------------------------------ #
    # Q7 — Tarozi integratsiyasi                                           #
    # ------------------------------------------------------------------ #

    source: Mapped[WeightSource] = mapped_column(
        SQLEnum(WeightSource, name="weight_source"),
        nullable=False,
        default=WeightSource.CAMERA_AI,
        index=True,
        comment="O'lchov manbai: camera_ai | manual | scale_serial | scale_api",
    )

    # Tarozidan kelgan haqiqiy vazn (AI taxmin bilan taqqoslash uchun)
    # NULL = faqat AI taxmini bor, haqiqiy vazn yo'q
    actual_weight_kg: Mapped[Optional[float]] = mapped_column(
        Float,
        nullable=True,
        comment="Tarozidan kelgan haqiqiy vazn (kg). NULL = faqat AI taxmini.",
    )

    # Qaysi tarozi qurilmadan kelgani (MANUAL uchun NULL bo'lishi mumkin)
    scale_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("scales.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Tarozi qurilma ID si (agar tarozidan kelgan bo'lsa)",
    )

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Foydalanuvchi izohi yoki tarozi xabari",
    )
    
    # Relationship to Animal
    animal: Mapped["Animal"] = relationship(
        "Animal",
        back_populates="weight_measurements",
        lazy="selectin",
    )

    # Relationship to Scale
    scale: Mapped[Optional["Scale"]] = relationship(  # type: ignore[name-defined]
        "Scale",
        back_populates="readings",
        lazy="noload",
        foreign_keys=[scale_id],
    )
    
    # Table-level constraints and indexes
    __table_args__ = (
        # Constraint: confidence_score must be between 0 and 1
        CheckConstraint(
            "confidence_score >= 0.0 AND confidence_score <= 1.0",
            name="check_confidence_range",
        ),
        # Constraint: weight must be positive
        CheckConstraint(
            "estimated_weight_kg > 0",
            name="check_weight_positive",
        ),
        # Composite index for time-series queries per animal
        Index(
            "ix_weight_measurements_animal_time",
            "animal_id",
            "timestamp",
        ),
        # Index for filtering high-confidence measurements
        Index(
            "ix_weight_measurements_confidence",
            "confidence_score",
        ),
        # Index for per-camera analytics
        Index(
            "ix_weight_measurements_camera_time",
            "camera_id",
            "timestamp",
        ),
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<WeightMeasurement(id={self.id}, "
            f"animal_id={self.animal_id}, "
            f"weight={self.estimated_weight_kg:.2f}kg, "
            f"confidence={self.confidence_score:.2f}, "
            f"camera={self.camera_id})>"
        )
    
    @property
    def is_high_confidence(self) -> bool:
        """
        Check if this is a high-confidence measurement.
        
        Returns:
            True if confidence >= 0.8 (configurable threshold)
        """
        return self.confidence_score >= 0.8
    
    @property
    def age_seconds(self) -> float:
        """
        Get age of measurement in seconds.
        
        Returns:
            Seconds since measurement was taken
        """
        return (datetime.utcnow() - self.timestamp).total_seconds()