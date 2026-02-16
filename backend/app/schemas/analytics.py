"""
Analytics Schemas - Taurus Vision

Pydantic models for analytics API requests and responses.
All schemas include comprehensive validation and documentation.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# DASHBOARD OVERVIEW SCHEMAS
# =============================================================================

class AnimalStatistics(BaseModel):
    """Animal count statistics."""
    
    total: int = Field(
        ...,
        description="Total number of animals in the system",
        ge=0
    )
    active: int = Field(
        ...,
        description="Number of active animals",
        ge=0
    )
    by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Animal counts per status (active, sold, deceased)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 45,
                "active": 42,
                "by_status": {
                    "active": 42,
                    "sold": 2,
                    "deceased": 1
                }
            }
        }
    )


class DetectionStatistics(BaseModel):
    """Detection count statistics."""
    
    today: int = Field(
        ...,
        description="Detections today",
        ge=0
    )
    week: int = Field(
        ...,
        description="Detections in the past 7 days",
        ge=0
    )
    month: int = Field(
        ...,
        description="Detections in the past 30 days",
        ge=0
    )
    total: int = Field(
        ...,
        description="Total detections all time",
        ge=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "today": 156,
                "week": 1087,
                "month": 4523,
                "total": 15647
            }
        }
    )


class WeightStatistics(BaseModel):
    """Weight-related statistics."""
    
    average_kg: Optional[float] = Field(
        None,
        description="Current average weight in kilograms",
        ge=0
    )
    change_percentage_7d: Optional[float] = Field(
        None,
        description="Weight change percentage over last 7 days",
        ge=-100
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "average_kg": 245.7,
                "change_percentage_7d": 2.3
            }
        }
    )


class CameraSystemStatus(BaseModel):
    """Camera system status."""
    
    total: int = Field(
        ...,
        description="Total number of cameras",
        ge=0
    )
    running: int = Field(
        ...,
        description="Number of cameras currently running",
        ge=0
    )
    healthy: int = Field(
        ...,
        description="Number of healthy cameras",
        ge=0
    )
    status: Literal["healthy", "degraded", "down"] = Field(
        ...,
        description="Overall camera system health status"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 3,
                "running": 3,
                "healthy": 3,
                "status": "healthy"
            }
        }
    )


class SystemStatus(BaseModel):
    """Overall system status."""
    
    cameras: CameraSystemStatus = Field(
        ...,
        description="Camera system status"
    )


class RecentDetection(BaseModel):
    """Recent detection activity item."""
    
    animal_tag: str = Field(
        ...,
        description="Animal tag ID",
        min_length=1,
        max_length=50
    )
    camera_id: str = Field(
        ...,
        description="Camera identifier",
        min_length=1,
        max_length=100
    )
    confidence: float = Field(
        ...,
        description="Detection confidence score",
        ge=0.0,
        le=1.0
    )
    detected_at: str = Field(
        ...,
        description="Detection timestamp (ISO 8601)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_tag": "JNV-001",
                "camera_id": "camera_01",
                "confidence": 0.956,
                "detected_at": "2026-02-16T10:30:45.123456"
            }
        }
    )


class Alert(BaseModel):
    """System alert."""
    
    type: str = Field(
        ...,
        description="Alert type (e.g., no_detection, weight_loss, never_detected)",
        min_length=1
    )
    severity: Literal["info", "warning", "critical"] = Field(
        ...,
        description="Alert severity level"
    )
    animal_tag: str = Field(
        ...,
        description="Affected animal tag ID",
        min_length=1,
        max_length=50
    )
    message: str = Field(
        ...,
        description="Human-readable alert message",
        min_length=1
    )
    days: Optional[int] = Field(
        None,
        description="Days since last detection (for no_detection alerts)",
        ge=0
    )
    loss_percentage: Optional[float] = Field(
        None,
        description="Weight loss percentage (for weight_loss alerts)",
        ge=0
    )
    previous_weight: Optional[float] = Field(
        None,
        description="Previous weight in kg",
        ge=0
    )
    current_weight: Optional[float] = Field(
        None,
        description="Current weight in kg",
        ge=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "weight_loss",
                "severity": "warning",
                "animal_tag": "JNV-023",
                "message": "Weight loss of 7.2% in 7 days",
                "loss_percentage": 7.2,
                "previous_weight": 250.0,
                "current_weight": 232.0
            }
        }
    )


class DashboardOverview(BaseModel):
    """
    Complete dashboard overview response.
    
    Contains all key metrics and statistics for the dashboard.
    """
    
    timestamp: str = Field(
        ...,
        description="Response generation timestamp (ISO 8601)"
    )
    animals: AnimalStatistics = Field(
        ...,
        description="Animal statistics"
    )
    detections: DetectionStatistics = Field(
        ...,
        description="Detection statistics"
    )
    weight: WeightStatistics = Field(
        ...,
        description="Weight statistics"
    )
    system: SystemStatus = Field(
        ...,
        description="System status"
    )
    recent_activity: List[RecentDetection] = Field(
        default_factory=list,
        description="Recent detection activity (last 5)"
    )
    alerts: List[Alert] = Field(
        default_factory=list,
        description="Active system alerts"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-02-16T10:30:45.123456",
                "animals": {
                    "total": 45,
                    "active": 42,
                    "by_status": {"active": 42, "sold": 2, "deceased": 1}
                },
                "detections": {
                    "today": 156,
                    "week": 1087,
                    "month": 4523,
                    "total": 15647
                },
                "weight": {
                    "average_kg": 245.7,
                    "change_percentage_7d": 2.3
                },
                "system": {
                    "cameras": {
                        "total": 3,
                        "running": 3,
                        "healthy": 3,
                        "status": "healthy"
                    }
                },
                "recent_activity": [],
                "alerts": []
            }
        }
    )


# =============================================================================
# WEIGHT TRENDS SCHEMAS
# =============================================================================

class WeightTrendRequest(BaseModel):
    """Request parameters for weight trends."""
    
    animal_id: Optional[int] = Field(
        None,
        description="Specific animal ID (None = farm-wide average)",
        gt=0
    )
    days: int = Field(
        30,
        description="Number of days to look back",
        ge=1,
        le=365
    )
    aggregation: Literal["daily", "weekly", "monthly"] = Field(
        "daily",
        description="Data aggregation level"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_id": 5,
                "days": 30,
                "aggregation": "daily"
            }
        }
    )


class WeightTrendPoint(BaseModel):
    """Single data point in weight trend."""
    
    date: str = Field(
        ...,
        description="Date (YYYY-MM-DD)"
    )
    average_weight: float = Field(
        ...,
        description="Average weight in kg",
        ge=0
    )
    min_weight: float = Field(
        ...,
        description="Minimum weight in kg",
        ge=0
    )
    max_weight: float = Field(
        ...,
        description="Maximum weight in kg",
        ge=0
    )
    measurement_count: int = Field(
        ...,
        description="Number of measurements",
        ge=0
    )
    animal_count: int = Field(
        ...,
        description="Number of unique animals (if farm-wide)",
        ge=0
    )
    
    @field_validator('max_weight')
    @classmethod
    def validate_max_gte_min(cls, v, info):
        """Validate that max_weight >= min_weight."""
        if 'min_weight' in info.data and v < info.data['min_weight']:
            raise ValueError('max_weight must be >= min_weight')
        return v
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-02-16",
                "average_weight": 245.7,
                "min_weight": 220.3,
                "max_weight": 278.9,
                "measurement_count": 15,
                "animal_count": 12
            }
        }
    )


class WeightTrendsResponse(BaseModel):
    """Weight trends response."""
    
    data: List[WeightTrendPoint] = Field(
        ...,
        description="Time-series data points"
    )
    animal_id: Optional[int] = Field(
        None,
        description="Animal ID (if specific animal)"
    )
    period_days: int = Field(
        ...,
        description="Number of days in period"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "data": [
                    {
                        "date": "2026-02-16",
                        "average_weight": 245.7,
                        "min_weight": 220.3,
                        "max_weight": 278.9,
                        "measurement_count": 15,
                        "animal_count": 12
                    }
                ],
                "animal_id": None,
                "period_days": 30
            }
        }
    )


# =============================================================================
# DETECTION PATTERNS SCHEMAS
# =============================================================================

class DetectionPatternRequest(BaseModel):
    """Request parameters for detection patterns."""
    
    date_from: date = Field(
        ...,
        description="Start date (YYYY-MM-DD)"
    )
    date_to: date = Field(
        ...,
        description="End date (YYYY-MM-DD)"
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
                "date_to": "2026-02-16"
            }
        }
    )


class DailyDetectionCount(BaseModel):
    """Daily detection count."""
    
    date: str = Field(
        ...,
        description="Date (YYYY-MM-DD)"
    )
    count: int = Field(
        ...,
        description="Number of detections",
        ge=0
    )


class CameraDetectionStats(BaseModel):
    """Per-camera detection statistics."""
    
    camera_id: str = Field(
        ...,
        description="Camera identifier"
    )
    detections: int = Field(
        ...,
        description="Number of detections",
        ge=0
    )
    average_confidence: float = Field(
        ...,
        description="Average confidence score",
        ge=0.0,
        le=1.0
    )


class TopDetectedAnimal(BaseModel):
    """Top detected animal."""
    
    tag_id: str = Field(
        ...,
        description="Animal tag ID"
    )
    species: str = Field(
        ...,
        description="Animal species"
    )
    detections: int = Field(
        ...,
        description="Number of detections",
        ge=0
    )


class DetectionPatternStatistics(BaseModel):
    """Detection pattern statistics."""
    
    total_detections: int = Field(
        ...,
        description="Total detections in period",
        ge=0
    )
    detection_rate_per_hour: float = Field(
        ...,
        description="Average detections per hour",
        ge=0.0
    )
    peak_hour: Optional[int] = Field(
        None,
        description="Hour with most detections (0-23)",
        ge=0,
        le=23
    )


class DateRange(BaseModel):
    """Date range information."""
    
    from_: str = Field(
        ...,
        alias="from",
        description="Start date (YYYY-MM-DD)"
    )
    to: str = Field(
        ...,
        description="End date (YYYY-MM-DD)"
    )
    days: int = Field(
        ...,
        description="Number of days in range",
        ge=1
    )
    
    model_config = ConfigDict(populate_by_name=True)


class DetectionPatternsResponse(BaseModel):
    """Detection patterns analysis response."""
    
    date_range: DateRange = Field(
        ...,
        description="Analysis date range"
    )
    detections_by_hour: List[int] = Field(
        ...,
        description="24-hour heatmap data [0-23]",
        min_length=24,
        max_length=24
    )
    detections_by_day: List[DailyDetectionCount] = Field(
        ...,
        description="Daily detection counts"
    )
    detections_by_camera: List[CameraDetectionStats] = Field(
        ...,
        description="Per-camera statistics"
    )
    top_detected_animals: List[TopDetectedAnimal] = Field(
        ...,
        description="Top 10 most detected animals"
    )
    statistics: DetectionPatternStatistics = Field(
        ...,
        description="Overall statistics"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date_range": {
                    "from": "2026-02-01",
                    "to": "2026-02-16",
                    "days": 16
                },
                "detections_by_hour": [12, 8, 5, 3, 2, 4, 15, 45, 78, 92, 105, 98, 87, 76, 65, 58, 62, 71, 83, 67, 52, 38, 25, 18],
                "detections_by_day": [],
                "detections_by_camera": [],
                "top_detected_animals": [],
                "statistics": {
                    "total_detections": 1234,
                    "detection_rate_per_hour": 3.2,
                    "peak_hour": 10
                }
            }
        }
    )


# =============================================================================
# HEALTH METRICS SCHEMAS
# =============================================================================

class AlertSummary(BaseModel):
    """Alert summary counts."""
    
    total: int = Field(
        ...,
        description="Total number of alerts",
        ge=0
    )
    critical: int = Field(
        ...,
        description="Number of critical alerts",
        ge=0
    )
    warning: int = Field(
        ...,
        description="Number of warning alerts",
        ge=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 5,
                "critical": 1,
                "warning": 4
            }
        }
    )


class HealthMetricsResponse(BaseModel):
    """Health metrics response."""
    
    animals_by_status: Dict[str, int] = Field(
        ...,
        description="Animal counts per status"
    )
    weight_distribution: Dict[str, int] = Field(
        ...,
        description="Weight range distribution"
    )
    alerts: List[Alert] = Field(
        ...,
        description="Active health alerts"
    )
    alert_summary: AlertSummary = Field(
        ...,
        description="Alert counts by severity"
    )
    risk_score: int = Field(
        ...,
        description="Overall health risk score (0-100)",
        ge=0,
        le=100
    )
    timestamp: str = Field(
        ...,
        description="Calculation timestamp (ISO 8601)"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animals_by_status": {
                    "active": 42,
                    "sold": 2,
                    "deceased": 1
                },
                "weight_distribution": {
                    "0-100kg": 5,
                    "100-200kg": 12,
                    "200-300kg": 18,
                    "300-400kg": 8,
                    "400kg+": 2
                },
                "alerts": [],
                "alert_summary": {
                    "total": 5,
                    "critical": 1,
                    "warning": 4
                },
                "risk_score": 23,
                "timestamp": "2026-02-16T10:30:45.123456"
            }
        }
    )


# =============================================================================
# CAMERA PERFORMANCE SCHEMAS
# =============================================================================

class CameraPerformanceRequest(BaseModel):
    """Request parameters for camera performance."""
    
    camera_id: Optional[str] = Field(
        None,
        description="Specific camera ID (None = all cameras)",
        min_length=1,
        max_length=100
    )
    days: int = Field(
        7,
        description="Number of days to analyze",
        ge=1,
        le=90
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "camera_01",
                "days": 7
            }
        }
    )


class CameraPerformanceData(BaseModel):
    """Individual camera performance data."""
    
    camera_id: str = Field(
        ...,
        description="Camera identifier"
    )
    status: Literal["running", "stopped", "error"] = Field(
        ...,
        description="Current camera status"
    )
    uptime_percentage: float = Field(
        ...,
        description="Uptime percentage over period",
        ge=0.0,
        le=100.0
    )
    total_detections: int = Field(
        ...,
        description="Number of detections",
        ge=0
    )
    detections_per_hour: float = Field(
        ...,
        description="Detection rate per hour",
        ge=0.0
    )
    average_confidence: float = Field(
        ...,
        description="Average detection confidence",
        ge=0.0,
        le=1.0
    )
    fps: float = Field(
        ...,
        description="Current frames per second",
        ge=0.0
    )
    errors: int = Field(
        ...,
        description="Error count",
        ge=0
    )
    total_frames: int = Field(
        ...,
        description="Total frames processed",
        ge=0
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "camera_id": "camera_01",
                "status": "running",
                "uptime_percentage": 99.8,
                "total_detections": 523,
                "detections_per_hour": 3.1,
                "average_confidence": 0.892,
                "fps": 10.5,
                "errors": 2,
                "total_frames": 176400
            }
        }
    )


class PerformancePeriod(BaseModel):
    """Performance analysis period."""
    
    days: int = Field(
        ...,
        description="Number of days analyzed",
        ge=1
    )
    from_: str = Field(
        ...,
        alias="from",
        description="Start timestamp (ISO 8601)"
    )
    to: str = Field(
        ...,
        description="End timestamp (ISO 8601)"
    )
    
    model_config = ConfigDict(populate_by_name=True)


class PerformanceSummary(BaseModel):
    """Overall performance summary."""
    
    total_cameras: int = Field(
        ...,
        description="Total number of cameras",
        ge=0
    )
    running_cameras: int = Field(
        ...,
        description="Number of running cameras",
        ge=0
    )
    total_detections: int = Field(
        ...,
        description="Total detections across all cameras",
        ge=0
    )
    average_fps: float = Field(
        ...,
        description="Average FPS across all cameras",
        ge=0.0
    )


class CameraPerformanceResponse(BaseModel):
    """Camera performance analysis response."""
    
    period: PerformancePeriod = Field(
        ...,
        description="Analysis period"
    )
    cameras: List[CameraPerformanceData] = Field(
        ...,
        description="Per-camera performance data"
    )
    summary: PerformanceSummary = Field(
        ...,
        description="Overall summary"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period": {
                    "days": 7,
                    "from": "2026-02-09T10:30:45.123456",
                    "to": "2026-02-16T10:30:45.123456"
                },
                "cameras": [],
                "summary": {
                    "total_cameras": 3,
                    "running_cameras": 3,
                    "total_detections": 1523,
                    "average_fps": 10.2
                }
            }
        }
    )

