"""
Pydantic schemas for Weight Measurement API.

Defines data structures for weight measurement operations.
"""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator, ConfigDict


class WeightMeasurementBase(BaseModel):
    """Base schema for weight measurement."""
    
    animal_id: int = Field(
        ...,
        gt=0,
        description="ID of the animal being measured",
    )
    
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the measurement was captured",
    )
    
    estimated_weight_kg: float = Field(
        ...,
        gt=0,
        description="Estimated weight in kilograms",
    )
    
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="AI model confidence (0.0 - 1.0)",
    )
    
    camera_id: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="Camera identifier",
    )
    
    raw_ai_data: Optional[dict[str, Any]] = Field(
        None,
        description="Raw AI model output (bounding boxes, masks, etc.)",
    )
    
    image_path: Optional[str] = Field(
        None,
        max_length=500,
        description="Path to stored image frame",
    )
    
    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: datetime) -> datetime:
        """
        Ensure timestamp is not in the future.
        
        Allows up to 5 seconds in future to account for clock skew.
        """
        max_future = datetime.utcnow().timestamp() + 5  # 5 seconds tolerance
        if v.timestamp() > max_future:
            raise ValueError("Timestamp cannot be more than 5 seconds in the future")
        return v


class WeightMeasurementCreate(WeightMeasurementBase):
    """
    Schema for creating a weight measurement.
    
    Used when AI camera submits a new measurement.
    
    Example:
        {
            "animal_id": 1,
            "timestamp": "2026-02-10T10:30:00Z",
            "estimated_weight_kg": 245.5,
            "confidence_score": 0.92,
            "camera_id": "CAM-001",
            "raw_ai_data": {
                "bounding_box": {"x": 120, "y": 80, "w": 200, "h": 300},
                "model_version": "yolov8-weight-v1.0"
            }
        }
    """
    pass


class WeightMeasurementResponse(WeightMeasurementBase):
    """
    Schema for weight measurement responses.
    
    Includes database-generated fields.
    """
    
    id: int = Field(..., description="Primary key")
    
    created_at: datetime = Field(
        ...,
        description="When record was created in database",
    )
    
    updated_at: datetime = Field(
        ...,
        description="When record was last updated",
    )
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "animal_id": 1,
                "timestamp": "2026-02-10T10:30:00Z",
                "estimated_weight_kg": 245.5,
                "confidence_score": 0.92,
                "camera_id": "CAM-001",
                "raw_ai_data": {
                    "bounding_box": {"x": 120, "y": 80, "w": 200, "h": 300}
                },
                "image_path": None,
                "created_at": "2026-02-10T10:30:05Z",
                "updated_at": "2026-02-10T10:30:05Z",
            }
        },
    )


class WeightMeasurementListResponse(BaseModel):
    """Paginated list of weight measurements."""
    
    items: list[WeightMeasurementResponse] = Field(
        ...,
        description="List of measurements",
    )
    
    total: int = Field(
        ...,
        description="Total count (ignoring pagination)",
    )
    
    skip: int = Field(
        0,
        description="Number of items skipped",
    )
    
    limit: int = Field(
        10,
        description="Maximum items returned",
    )


class WeightStatsResponse(BaseModel):
    """
    Statistics for an animal's weight over time.
    
    Used for analytics and trend visualization.
    """
    
    animal_id: int
    
    total_measurements: int = Field(
        ...,
        description="Total number of measurements",
    )
    
    average_weight_kg: float = Field(
        ...,
        description="Average weight across all measurements",
    )
    
    latest_weight_kg: Optional[float] = Field(
        None,
        description="Most recent weight measurement",
    )
    
    weight_trend: Optional[str] = Field(
        None,
        description="Trend direction: 'increasing', 'decreasing', 'stable'",
    )
    
    confidence_average: float = Field(
        ...,
        description="Average AI confidence across measurements",
    )
    
    first_measurement_date: Optional[datetime] = None
    last_measurement_date: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)


class LiveWeightUpdate(BaseModel):
    """
    Real-time weight update for WebSocket broadcast.
    
    Lightweight schema optimized for real-time transmission.
    """
    
    measurement_id: int
    animal_id: int
    animal_tag_id: str = Field(..., description="Animal tag for display")
    estimated_weight_kg: float
    confidence_score: float
    camera_id: str
    timestamp: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "measurement_id": 123,
                "animal_id": 1,
                "animal_tag_id": "JNV-001",
                "estimated_weight_kg": 245.5,
                "confidence_score": 0.92,
                "camera_id": "CAM-001",
                "timestamp": "2026-02-10T10:30:00Z",
            }
        },
    )