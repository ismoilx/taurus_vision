"""
Animal database model.

This module defines the Animal model which represents individual animals
in the farm monitoring system.
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Enum as SQLEnum, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel


class AnimalSpecies(str, enum.Enum):
    """
    Supported animal species.
    
    Add new species as needed. Using enum ensures data consistency.
    """
    CATTLE = "cattle"       # Sigir
    SHEEP = "sheep"         # Qo'y
    GOAT = "goat"          # Echki
    HORSE = "horse"        # Ot
    OTHER = "other"        # Boshqa


class AnimalGender(str, enum.Enum):
    """Animal gender classification."""
    MALE = "male"          # Erkak
    FEMALE = "female"      # Urg'ochi
    UNKNOWN = "unknown"    # Noma'lum


class AnimalStatus(str, enum.Enum):
    """
    Current status of animal in the farm.
    
    This tracks the lifecycle of each animal.
    """
    ACTIVE = "active"              # Faol (ferma ichida)
    QUARANTINE = "quarantine"      # Karantin
    SICK = "sick"                  # Kasal
    SOLD = "sold"                  # Sotilgan
    DECEASED = "deceased"          # O'lgan
    TRANSFERRED = "transferred"    # Boshqaga o'tkazilgan


class Animal(BaseModel):
    """
    Animal entity model.
    
    Represents a single animal in the farm with all its attributes
    and tracking information.
    
    Attributes:
        tag_id: Unique identifier tag (e.g., "JNV-001")
        species: Type of animal (cattle, sheep, etc.)
        breed: Specific breed name (optional)
        gender: Male/Female/Unknown
        birth_date: Date of birth (if known)
        acquisition_date: When animal was added to farm
        status: Current lifecycle status
        notes: Additional information
        
    Relationships:
        detections: All detection events for this animal
        weight_logs: Weight measurement history
        health_records: Health checkup records
    """
    
    __tablename__ = "animals"
    
    # Basic Information
    tag_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique tag identifier (e.g., JNV-001)",
    )
    
    species: Mapped[AnimalSpecies] = mapped_column(
        SQLEnum(AnimalSpecies, name="animal_species"),
        nullable=False,
        index=True,
        comment="Species type",
    )
    
    breed: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        comment="Specific breed name",
    )
    
    gender: Mapped[AnimalGender] = mapped_column(
        SQLEnum(AnimalGender, name="animal_gender"),
        default=AnimalGender.UNKNOWN,
        nullable=False,
        comment="Gender classification",
    )
    
    # Dates
    birth_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Date of birth (if known)",
    )
    
    acquisition_date: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Date when animal was acquired/added to farm",
    )
    
    # Status
    status: Mapped[AnimalStatus] = mapped_column(
        SQLEnum(AnimalStatus, name="animal_status"),
        default=AnimalStatus.ACTIVE,
        nullable=False,
        index=True,
        comment="Current lifecycle status",
    )
    
    # Detection Tracking
    first_detected_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="First time detected by camera system",
    )
    
    last_detected_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
        comment="Most recent detection timestamp",
    )
    
    total_detections: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
        comment="Total number of times detected",
    )
    
    # Additional Information
    notes: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
        comment="Additional notes or observations",
    )
    
    # Relationships (qo'shilamiz keyinroq)
    # detections = relationship("Detection", back_populates="animal")
    # weight_logs = relationship("WeightLog", back_populates="animal")
    # health_records = relationship("HealthRecord", back_populates="animal")
    
    # Table-level constraints
    __table_args__ = (
        # Check: birth_date should be before acquisition_date
        CheckConstraint(
            "birth_date IS NULL OR birth_date <= acquisition_date",
            name="check_birth_before_acquisition",
        ),
        # Check: total_detections should be non-negative
        CheckConstraint(
            "total_detections >= 0",
            name="check_detections_non_negative",
        ),
        # Composite index for common queries
        Index("ix_animals_species_status", "species", "status"),
        Index("ix_animals_status_last_detected", "status", "last_detected_at"),
    )
    
    def __repr__(self) -> str:
        """String representation for debugging."""
        return (
            f"<Animal(id={self.id}, tag_id='{self.tag_id}', "
            f"species={self.species.value}, status={self.status.value})>"
        )
    
    @property
    def age_days(self) -> Optional[int]:
        """
        Calculate age in days.
        
        Returns:
            Age in days if birth_date is known, None otherwise
        """
        if not self.birth_date:
            return None
        return (datetime.utcnow() - self.birth_date).days
    
    @property
    def is_active(self) -> bool:
        """Check if animal is currently active in the farm."""
        return self.status == AnimalStatus.ACTIVE
    
    def mark_detected(self, detected_at: Optional[datetime] = None) -> None:
        """
        Mark animal as detected.
        
        Updates detection counters and timestamps.
        
        Args:
            detected_at: Detection timestamp (defaults to now)
        """
        if detected_at is None:
            detected_at = datetime.utcnow()
        
        if self.first_detected_at is None:
            self.first_detected_at = detected_at
        
        self.last_detected_at = detected_at
        self.total_detections += 1