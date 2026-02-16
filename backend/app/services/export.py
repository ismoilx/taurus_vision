"""
Export Schemas - Taurus Vision

Pydantic models for data export API.
Defines request/response schemas for CSV and Excel exports.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# ANIMALS EXPORT
# =============================================================================

class AnimalsExportRequest(BaseModel):
    """
    Request for animals CSV export.
    
    Allows filtering by status, species, gender, and tag ID.
    """
    
    status: Optional[str] = Field(
        None,
        description="Filter by status (active/sold/deceased)"
    )
    species: Optional[str] = Field(
        None,
        description="Filter by species (cattle/sheep/goat)"
    )
    gender: Optional[str] = Field(
        None,
        description="Filter by gender (male/female)"
    )
    tag_id: Optional[str] = Field(
        None,
        description="Filter by tag ID (partial match)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "active",
                "species": "cattle",
                "gender": None,
                "tag_id": None
            }
        }
    )


# =============================================================================
# DETECTIONS EXPORT
# =============================================================================

class DetectionsExportRequest(BaseModel):
    """
    Request for detections CSV export.
    
    Requires date range, optionally filter by specific animal.
    """
    
    date_from: date = Field(
        ...,
        description="Start date (YYYY-MM-DD)"
    )
    date_to: date = Field(
        ...,
        description="End date (YYYY-MM-DD)"
    )
    animal_id: Optional[int] = Field(
        None,
        description="Filter by specific animal ID",
        gt=0
    )
    
    @field_validator('date_to')
    @classmethod
    def validate_date_range(cls, v, info):
        """Validate that date_to >= date_from."""
        if 'date_from' in info.data and v < info.data['date_from']:
            raise ValueError('date_to must be >= date_from')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date_from": "2026-02-01",
                "date_to": "2026-02-16",
                "animal_id": None
            }
        }
    )


# =============================================================================
# WEIGHTS EXPORT
# =============================================================================

class WeightsExportRequest(BaseModel):
    """
    Request for weight measurements Excel export.
    
    Optionally filter by specific animal IDs.
    Creates multi-sheet Excel with per-animal details.
    """
    
    animal_ids: Optional[List[int]] = Field(
        None,
        description="Filter by specific animal IDs (None = all active animals)"
    )
    
    @field_validator('animal_ids')
    @classmethod
    def validate_animal_ids(cls, v):
        """Validate animal IDs are positive."""
        if v is not None:
            if len(v) == 0:
                raise ValueError('animal_ids cannot be empty list')
            if any(aid <= 0 for aid in v):
                raise ValueError('All animal IDs must be positive')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_ids": [1, 2, 3, 5, 8]
            }
        }
    )


# =============================================================================
# EXPORT RESPONSE (METADATA)
# =============================================================================

class ExportMetadata(BaseModel):
    """
    Export metadata returned after generation.
    
    Contains information about the exported file.
    """
    
    export_type: str = Field(
        ...,
        description="Type of export (animals_csv/detections_csv/weights_excel)"
    )
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes",
        ge=0
    )
    record_count: int = Field(
        ...,
        description="Number of records exported",
        ge=0
    )
    generated_at: str = Field(
        ...,
        description="Generation timestamp (ISO 8601)"
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Parameters used for export"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "export_type": "animals_csv",
                "file_size_bytes": 12345,
                "record_count": 45,
                "generated_at": "2026-02-16T10:30:45.123456",
                "parameters": {
                    "status": "active",
                    "species": None
                }
            }
        }
    )


class ExportResponse(BaseModel):
    """
    Export generation response.
    
    Returns metadata about the exported file.
    The actual file is returned as binary data in the response body.
    """
    
    message: str = Field(
        ...,
        description="Success message"
    )
    metadata: ExportMetadata = Field(
        ...,
        description="Export metadata"
    )
    filename: str = Field(
        ...,
        description="Suggested filename for download"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Export generated successfully",
                "metadata": {
                    "export_type": "animals_csv",
                    "file_size_bytes": 12345,
                    "record_count": 45,
                    "generated_at": "2026-02-16T10:30:45.123456",
                    "parameters": {}
                },
                "filename": "animals_20260216.csv"
            }
        }
    )
