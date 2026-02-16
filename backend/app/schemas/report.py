"""
Report Schemas - Taurus Vision

Pydantic models for report generation API.
Defines request/response schemas for PDF report generation.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import date
from typing import Optional, List, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# REPORT REQUEST SCHEMAS
# =============================================================================

class AnimalReportRequest(BaseModel):
    """
    Request for animal-specific report.
    
    Animal report includes:
    - Basic information
    - Weight history (table + chart)
    - Detection timeline
    - Health summary
    """
    
    animal_id: int = Field(
        ...,
        description="Animal ID",
        gt=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_id": 5
            }
        }
    )


class FarmReportRequest(BaseModel):
    """
    Request for farm-wide summary report.
    
    Farm report includes:
    - Executive summary
    - Animal statistics
    - Detection summary
    - Weight trends
    - Top performers
    """
    
    date_from: date = Field(
        ...,
        description="Start date (YYYY-MM-DD)"
    )
    date_to: date = Field(
        ...,
        description="End date (YYYY-MM-DD)"
    )
    report_type: Literal["summary", "detailed", "health"] = Field(
        "summary",
        description="Report type (summary/detailed/health)"
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
                "report_type": "summary"
            }
        }
    )


class HealthReportRequest(BaseModel):
    """
    Request for health-focused report.
    
    Health report includes:
    - Health overview
    - Active alerts
    - Weight loss detection
    - Risk assessment
    - Recommendations
    """
    
    animal_ids: Optional[List[int]] = Field(
        None,
        description="Specific animal IDs (None = all active animals)"
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
# REPORT RESPONSE SCHEMAS
# =============================================================================

class ReportMetadata(BaseModel):
    """
    Report metadata returned after generation.
    
    Contains information about the generated report:
    - File size
    - Generation time
    - Report type
    - Parameters used
    """
    
    report_type: str = Field(
        ...,
        description="Type of report generated"
    )
    file_size_bytes: int = Field(
        ...,
        description="PDF file size in bytes",
        ge=0
    )
    generated_at: str = Field(
        ...,
        description="Generation timestamp (ISO 8601)"
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Parameters used to generate the report"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_type": "animal_report",
                "file_size_bytes": 45678,
                "generated_at": "2026-02-16T10:30:45.123456",
                "parameters": {
                    "animal_id": 5
                }
            }
        }
    )


class ReportResponse(BaseModel):
    """
    Report generation response.
    
    Returns metadata about the generated report.
    The actual PDF is returned as binary data in the response body.
    """
    
    message: str = Field(
        ...,
        description="Success message"
    )
    metadata: ReportMetadata = Field(
        ...,
        description="Report metadata"
    )
    filename: str = Field(
        ...,
        description="Suggested filename for download"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "message": "Report generated successfully",
                "metadata": {
                    "report_type": "animal_report",
                    "file_size_bytes": 45678,
                    "generated_at": "2026-02-16T10:30:45.123456",
                    "parameters": {
                        "animal_id": 5
                    }
                },
                "filename": "animal_5_report_20260216.pdf"
            }
        }
    )


# =============================================================================
# REPORT LIST SCHEMAS (for future use)
# =============================================================================

class ReportListItem(BaseModel):
    """
    Report item in list view.
    
    Used when implementing report history/archive functionality.
    """
    
    report_id: str = Field(
        ...,
        description="Unique report identifier"
    )
    report_type: str = Field(
        ...,
        description="Type of report"
    )
    generated_at: str = Field(
        ...,
        description="Generation timestamp (ISO 8601)"
    )
    file_size_bytes: int = Field(
        ...,
        description="File size in bytes",
        ge=0
    )
    parameters: dict = Field(
        default_factory=dict,
        description="Generation parameters"
    )
    download_url: Optional[str] = Field(
        None,
        description="Download URL (if stored)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "report_id": "rep_1234567890",
                "report_type": "farm_report",
                "generated_at": "2026-02-16T10:30:45.123456",
                "file_size_bytes": 125000,
                "parameters": {
                    "date_from": "2026-02-01",
                    "date_to": "2026-02-16"
                },
                "download_url": "/api/v1/reports/rep_1234567890/download"
            }
        }
    )


class ReportListResponse(BaseModel):
    """
    List of generated reports.
    
    For future implementation of report archive.
    """
    
    reports: List[ReportListItem] = Field(
        ...,
        description="List of reports"
    )
    total: int = Field(
        ...,
        description="Total number of reports",
        ge=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reports": [],
                "total": 0
            }
        }
    )
