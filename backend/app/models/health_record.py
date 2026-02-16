"""
Health Record Model - Taurus Vision

Database model for animal health records and veterinary history.
Tracks checkups, treatments, vaccinations, injuries, and scheduled visits.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date
from typing import Optional
from enum import Enum as PyEnum
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Date,
    Float, Boolean, ForeignKey, Enum
)
from sqlalchemy.orm import relationship

from app.models.base import Base


class HealthRecordType(str, PyEnum):
    """
    Type of health record.
    
    Values:
    - checkup: Regular health checkup
    - treatment: Medical treatment
    - vaccination: Vaccination/immunization
    - injury: Injury or accident
    - surgery: Surgical procedure
    - illness: Illness or disease
    - other: Other health-related event
    """
    CHECKUP = "checkup"
    TREATMENT = "treatment"
    VACCINATION = "vaccination"
    INJURY = "injury"
    SURGERY = "surgery"
    ILLNESS = "illness"
    OTHER = "other"


class HealthRecordSeverity(str, PyEnum):
    """
    Severity level of health record.
    
    Values:
    - normal: Routine, no concern
    - warning: Requires monitoring
    - critical: Requires immediate attention
    """
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"


class HealthRecord(Base):
    """
    Health Record model.
    
    Tracks all health-related events for animals including:
    - Regular checkups
    - Treatments and medications
    - Vaccinations
    - Injuries and surgeries
    - Scheduled follow-ups
    
    Attributes:
        id: Primary key
        animal_id: Foreign key to Animal
        record_type: Type of health record (checkup, treatment, etc)
        severity: Severity level (normal, warning, critical)
        diagnosis: Medical diagnosis or condition
        symptoms: Observed symptoms
        treatment: Treatment provided
        medication: Medications administered
        dosage: Medication dosage
        veterinarian: Veterinarian name
        clinic_name: Clinic or hospital name
        cost: Cost of treatment
        notes: Additional notes
        recorded_at: Date/time of record
        next_checkup_date: Date of next scheduled checkup
        is_resolved: Whether the issue is resolved
        resolved_at: Date/time when resolved
        created_at: Record creation timestamp
        updated_at: Record update timestamp
        
        animal: Relationship to Animal model
    
    Example:
        >>> record = HealthRecord(
        ...     animal_id=5,
        ...     record_type=HealthRecordType.VACCINATION,
        ...     severity=HealthRecordSeverity.NORMAL,
        ...     diagnosis="Routine vaccination",
        ...     treatment="FMD vaccine administered",
        ...     veterinarian="Dr. Smith"
        ... )
    """
    
    __tablename__ = "health_records"
    
    # Primary Key
    id = Column(Integer, primary_key=True, index=True)
    
    # Foreign Key
    animal_id = Column(
        Integer,
        ForeignKey("animals.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Record Classification
    record_type = Column(
        Enum(HealthRecordType),
        nullable=False,
        index=True,
        comment="Type of health record"
    )
    severity = Column(
        Enum(HealthRecordSeverity),
        nullable=False,
        default=HealthRecordSeverity.NORMAL,
        index=True,
        comment="Severity level"
    )
    
    # Medical Information
    diagnosis = Column(
        String(500),
        nullable=False,
        comment="Medical diagnosis or condition"
    )
    symptoms = Column(
        Text,
        nullable=True,
        comment="Observed symptoms"
    )
    treatment = Column(
        Text,
        nullable=True,
        comment="Treatment provided"
    )
    medication = Column(
        String(300),
        nullable=True,
        comment="Medications administered"
    )
    dosage = Column(
        String(100),
        nullable=True,
        comment="Medication dosage"
    )
    
    # Medical Personnel
    veterinarian = Column(
        String(200),
        nullable=True,
        comment="Veterinarian name"
    )
    clinic_name = Column(
        String(300),
        nullable=True,
        comment="Clinic or hospital name"
    )
    
    # Financial
    cost = Column(
        Float,
        nullable=True,
        comment="Cost of treatment"
    )
    
    # Additional Information
    notes = Column(
        Text,
        nullable=True,
        comment="Additional notes"
    )
    
    # Timestamps
    recorded_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="Date/time of record"
    )
    next_checkup_date = Column(
        Date,
        nullable=True,
        index=True,
        comment="Date of next scheduled checkup"
    )
    
    # Resolution Status
    is_resolved = Column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether the issue is resolved"
    )
    resolved_at = Column(
        DateTime,
        nullable=True,
        comment="Date/time when resolved"
    )
    
    # Audit Fields
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        comment="Record creation timestamp"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        comment="Record update timestamp"
    )
    
    # Relationships
    animal = relationship(
        "Animal",
        back_populates="health_records",
        lazy="joined"
    )
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<HealthRecord(id={self.id}, "
            f"animal_id={self.animal_id}, "
            f"type={self.record_type.value}, "
            f"severity={self.severity.value}, "
            f"diagnosis='{self.diagnosis[:30]}...')>"
        )
    
    def to_dict(self) -> dict:
        """
        Convert to dictionary.
        
        Returns:
            Dictionary representation of the health record
        """
        return {
            "id": self.id,
            "animal_id": self.animal_id,
            "record_type": self.record_type.value,
            "severity": self.severity.value,
            "diagnosis": self.diagnosis,
            "symptoms": self.symptoms,
            "treatment": self.treatment,
            "medication": self.medication,
            "dosage": self.dosage,
            "veterinarian": self.veterinarian,
            "clinic_name": self.clinic_name,
            "cost": self.cost,
            "notes": self.notes,
            "recorded_at": self.recorded_at.isoformat() if self.recorded_at else None,
            "next_checkup_date": self.next_checkup_date.isoformat() if self.next_checkup_date else None,
            "is_resolved": self.is_resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
