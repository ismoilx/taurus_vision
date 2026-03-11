"""
Health Record Schemas - Taurus Vision

Pydantic models for health record API requests and responses.
Comprehensive validation, documentation, and examples.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


# =============================================================================
# ENUMS (for documentation)
# =============================================================================

RecordTypeEnum = Literal["checkup", "treatment", "vaccination", "injury", "surgery", "illness", "other"]
SeverityEnum = Literal["normal", "warning", "critical"]


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class HealthRecordBase(BaseModel):
    """Base schema for health records."""
    
    record_type: RecordTypeEnum = Field(
        ...,
        description="Type of health record"
    )
    severity: SeverityEnum = Field(
        ...,
        description="Severity level"
    )
    diagnosis: str = Field(
        ...,
        description="Medical diagnosis or condition",
        min_length=1,
        max_length=500
    )
    symptoms: Optional[str] = Field(
        None,
        description="Observed symptoms",
        max_length=2000
    )
    treatment: Optional[str] = Field(
        None,
        description="Treatment provided",
        max_length=2000
    )
    medication: Optional[str] = Field(
        None,
        description="Medications administered",
        max_length=300
    )
    dosage: Optional[str] = Field(
        None,
        description="Medication dosage",
        max_length=100
    )
    veterinarian: Optional[str] = Field(
        None,
        description="Veterinarian name",
        max_length=200
    )
    clinic_name: Optional[str] = Field(
        None,
        description="Clinic or hospital name",
        max_length=300
    )
    cost: Optional[float] = Field(
        None,
        description="Cost of treatment",
        ge=0.0
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes",
        max_length=2000
    )


# =============================================================================
# CREATE SCHEMA
# =============================================================================

class HealthRecordCreate(HealthRecordBase):
    """
    Schema for creating a health record.
    
    All fields from base plus optional dates.
    """
    
    recorded_at: Optional[datetime] = Field(
        None,
        description="Record timestamp (defaults to now)"
    )
    next_checkup_date: Optional[date] = Field(
        None,
        description="Date of next scheduled checkup"
    )
    
    @field_validator('next_checkup_date')
    @classmethod
    def validate_checkup_date(cls, v):
        """Validate that next checkup date is not in the past."""
        if v and v < date.today():
            raise ValueError('Next checkup date cannot be in the past')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record_type": "vaccination",
                "severity": "normal",
                "diagnosis": "Routine FMD vaccination",
                "symptoms": None,
                "treatment": "FMD vaccine administered subcutaneously",
                "medication": "FMD Vaccine",
                "dosage": "2ml",
                "veterinarian": "Dr. John Smith",
                "clinic_name": "Valley Animal Clinic",
                "cost": 25.00,
                "notes": "Animal responded well to vaccination",
                "recorded_at": None,
                "next_checkup_date": "2026-03-16"
            }
        }
    )


# =============================================================================
# UPDATE SCHEMA
# =============================================================================

class HealthRecordUpdate(BaseModel):
    """
    Schema for updating a health record.
    
    All fields are optional.
    """
    
    record_type: Optional[RecordTypeEnum] = Field(
        None,
        description="Type of health record"
    )
    severity: Optional[SeverityEnum] = Field(
        None,
        description="Severity level"
    )
    diagnosis: Optional[str] = Field(
        None,
        description="Medical diagnosis or condition",
        min_length=1,
        max_length=500
    )
    symptoms: Optional[str] = Field(
        None,
        description="Observed symptoms",
        max_length=2000
    )
    treatment: Optional[str] = Field(
        None,
        description="Treatment provided",
        max_length=2000
    )
    medication: Optional[str] = Field(
        None,
        description="Medications administered",
        max_length=300
    )
    dosage: Optional[str] = Field(
        None,
        description="Medication dosage",
        max_length=100
    )
    veterinarian: Optional[str] = Field(
        None,
        description="Veterinarian name",
        max_length=200
    )
    clinic_name: Optional[str] = Field(
        None,
        description="Clinic or hospital name",
        max_length=300
    )
    cost: Optional[float] = Field(
        None,
        description="Cost of treatment",
        ge=0.0
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes",
        max_length=2000
    )
    next_checkup_date: Optional[date] = Field(
        None,
        description="Date of next scheduled checkup"
    )
    is_resolved: Optional[bool] = Field(
        None,
        description="Whether the issue is resolved"
    )
    
    @field_validator('next_checkup_date')
    @classmethod
    def validate_checkup_date(cls, v):
        """Validate that next checkup date is not in the past."""
        if v and v < date.today():
            raise ValueError('Next checkup date cannot be in the past')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "treatment": "Updated treatment plan with additional medication",
                "medication": "Antibiotic + Pain reliever",
                "cost": 150.00,
                "is_resolved": False
            }
        }
    )


# =============================================================================
# RESPONSE SCHEMA
# =============================================================================

class HealthRecordResponse(HealthRecordBase):
    """
    Schema for health record response.
    
    Includes all fields plus metadata.
    """
    
    id: int = Field(
        ...,
        description="Health record ID"
    )
    animal_id: int = Field(
        ...,
        description="Animal ID"
    )
    recorded_at: datetime = Field(
        ...,
        description="Record timestamp"
    )
    next_checkup_date: Optional[date] = Field(
        None,
        description="Date of next scheduled checkup"
    )
    is_resolved: bool = Field(
        ...,
        description="Whether the issue is resolved"
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="Resolution timestamp"
    )
    created_at: Optional[datetime] = Field(
        None,
        description="Record creation timestamp"
    )
    updated_at: Optional[datetime] = Field(
        None,
        description="Record update timestamp"
    )

    @field_validator("record_type", mode="before")
    @classmethod
    def coerce_record_type(cls, v):
        """Enum yoki string qiymatni Literal ga moslashtirish."""
        if hasattr(v, "value"):
            return v.value
        return v

    @field_validator("severity", mode="before")
    @classmethod
    def coerce_severity(cls, v):
        """Enum yoki string qiymatni Literal ga moslashtirish."""
        if hasattr(v, "value"):
            return v.value
        return v
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 123,
                "animal_id": 5,
                "record_type": "vaccination",
                "severity": "normal",
                "diagnosis": "Routine FMD vaccination",
                "symptoms": None,
                "treatment": "FMD vaccine administered",
                "medication": "FMD Vaccine",
                "dosage": "2ml",
                "veterinarian": "Dr. John Smith",
                "clinic_name": "Valley Animal Clinic",
                "cost": 25.00,
                "notes": "Animal responded well",
                "recorded_at": "2026-02-16T10:30:00",
                "next_checkup_date": "2026-03-16",
                "is_resolved": True,
                "resolved_at": "2026-02-20T14:00:00",
                "created_at": "2026-02-16T10:30:00",
                "updated_at": "2026-02-20T14:00:00"
            }
        }
    )


# =============================================================================
# LIST RESPONSE SCHEMA
# =============================================================================

class HealthRecordListResponse(BaseModel):
    """
    Schema for paginated health record list.
    """
    
    records: List[HealthRecordResponse] = Field(
        ...,
        description="List of health records"
    )
    items: Optional[List[HealthRecordResponse]] = Field(
        None,
        description="Alias for records (test compatibility)"
    )
    total: int = Field(
        ...,
        description="Total number of records",
        ge=0
    )
    skip: int = Field(
        ...,
        description="Number of records skipped",
        ge=0
    )
    limit: int = Field(
        ...,
        description="Maximum number of records returned",
        ge=1
    )

    @model_validator(mode="after")
    def sync_items(self) -> "HealthRecordListResponse":
        """Sync items = records for backward compatibility."""
        if self.items is None:
            self.items = self.records
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "records": [],
                "items": [],
                "total": 15,
                "skip": 0,
                "limit": 10
            }
        }
    )


# =============================================================================
# STATISTICS SCHEMA
# =============================================================================

class HealthStatistics(BaseModel):
    """
    Schema for health statistics.
    """
    
    total_records: int = Field(
        ...,
        description="Total number of health records",
        ge=0
    )
    by_type: dict = Field(
        default_factory=dict,
        description="Records count by type"
    )
    by_severity: dict = Field(
        default_factory=dict,
        description="Records count by severity"
    )
    unresolved: int = Field(
        ...,
        description="Number of unresolved records",
        ge=0
    )
    critical_unresolved: int = Field(
        ...,
        description="Number of critical unresolved records",
        ge=0
    )
    health_score: int = Field(
        ...,
        description="Overall health score (0-100)",
        ge=0,
        le=100
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_records": 25,
                "by_type": {
                    "checkup": 10,
                    "vaccination": 8,
                    "treatment": 5,
                    "injury": 2
                },
                "by_severity": {
                    "normal": 20,
                    "warning": 4,
                    "critical": 1
                },
                "unresolved": 3,
                "critical_unresolved": 1,
                "health_score": 82
            }
        }
    )


# =============================================================================
# HEALTH SUMMARY SCHEMA
# =============================================================================

class LatestRecordSummary(BaseModel):
    """Latest health record summary."""
    
    id: int
    type: str
    severity: str
    diagnosis: str
    recorded_at: str


class UnresolvedIssue(BaseModel):
    """Unresolved health issue."""
    
    id: int
    type: str
    severity: str
    diagnosis: str


class UnresolvedIssuesSummary(BaseModel):
    """Unresolved issues summary."""
    
    count: int = Field(ge=0)
    records: List[UnresolvedIssue]


class UpcomingCheckupsSummary(BaseModel):
    """Upcoming checkups summary."""
    
    count: int = Field(ge=0)
    next_date: Optional[str] = None


class HealthSummary(BaseModel):
    """
    Comprehensive health summary for an animal.
    """
    
    animal_id: int = Field(
        ...,
        description="Animal ID"
    )
    animal_tag: str = Field(
        ...,
        description="Animal tag ID"
    )
    total_records: int = Field(
        ...,
        description="Total health records",
        ge=0
    )
    latest_record: Optional[LatestRecordSummary] = Field(
        None,
        description="Latest health record"
    )
    unresolved_issues: UnresolvedIssuesSummary = Field(
        ...,
        description="Unresolved health issues"
    )
    upcoming_checkups: UpcomingCheckupsSummary = Field(
        ...,
        description="Upcoming checkups"
    )
    statistics: HealthStatistics = Field(
        ...,
        description="Health statistics"
    )
    health_score: int = Field(
        ...,
        description="Health score (0-100)",
        ge=0,
        le=100
    )
    health_status: Literal["excellent", "good", "fair", "poor", "critical"] = Field(
        ...,
        description="Health status label"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_id": 5,
                "animal_tag": "JNV-001",
                "total_records": 25,
                "latest_record": {
                    "id": 123,
                    "type": "checkup",
                    "severity": "normal",
                    "diagnosis": "Routine checkup",
                    "recorded_at": "2026-02-16T10:30:00"
                },
                "unresolved_issues": {
                    "count": 2,
                    "records": []
                },
                "upcoming_checkups": {
                    "count": 1,
                    "next_date": "2026-03-16"
                },
                "statistics": {
                    "total_records": 25,
                    "by_type": {},
                    "by_severity": {},
                    "unresolved": 2,
                    "critical_unresolved": 0,
                    "health_score": 85
                },
                "health_score": 85,
                "health_status": "good"
            }
        }
    )


# =============================================================================
# QUERY PARAMETERS SCHEMA
# =============================================================================

class HealthRecordQuery(BaseModel):
    """
    Query parameters for filtering health records.
    """
    
    record_type: Optional[RecordTypeEnum] = Field(
        None,
        description="Filter by record type"
    )
    severity: Optional[SeverityEnum] = Field(
        None,
        description="Filter by severity"
    )
    is_resolved: Optional[bool] = Field(
        None,
        description="Filter by resolution status"
    )
    days_ahead: Optional[int] = Field(
        7,
        description="Days ahead for upcoming checkups",
        ge=1,
        le=90
    )
    skip: int = Field(
        0,
        description="Number of records to skip",
        ge=0
    )
    limit: int = Field(
        10,
        description="Maximum number of records",
        ge=1,
        le=100
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "record_type": "vaccination",
                "severity": None,
                "is_resolved": False,
                "skip": 0,
                "limit": 10
            }
        }
    )