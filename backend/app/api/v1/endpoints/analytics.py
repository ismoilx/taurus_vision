"""
Analytics API Endpoints - Taurus Vision

REST API endpoints for analytics and statistics.
Provides comprehensive data for dashboards, charts, and reports.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import date, datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    DashboardOverview,
    WeightTrendsResponse,
    WeightTrendPoint,
    DetectionPatternsResponse,
    HealthMetricsResponse,
    CameraPerformanceResponse,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/analytics", tags=["analytics"])

# Initialize service (singleton pattern would be better in production)
analytics_service = AnalyticsService()


# =============================================================================
# DASHBOARD OVERVIEW
# =============================================================================

@router.get(
    "/overview",
    response_model=DashboardOverview,
    summary="Get dashboard overview",
    description="""
    Get comprehensive dashboard overview statistics.
    
    Returns:
    - Animal counts (total, active, by status)
    - Detection counts (today, week, month, total)
    - Weight statistics (average, change percentage)
    - Camera system status
    - Recent activity
    - Active alerts
    
    This endpoint is optimized for dashboard rendering and provides
    all key metrics in a single request.
    """,
    responses={
        200: {
            "description": "Dashboard overview retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "timestamp": "2026-02-16T10:30:45.123456",
                        "animals": {
                            "total": 45,
                            "active": 42,
                            "by_status": {
                                "active": 42,
                                "sold": 2,
                                "deceased": 1
                            }
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
            }
        },
        500: {"description": "Internal server error"}
    },
    tags=["Analytics"]
)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db)
) -> DashboardOverview:
    """
    Get comprehensive dashboard overview.
    
    This is the main endpoint for populating the dashboard UI.
    It aggregates data from multiple sources to provide a complete
    snapshot of the farm's current state.
    
    Performance note: This endpoint executes multiple database queries
    but is optimized with proper indexing and query optimization.
    Typical response time: 100-300ms.
    """
    logger.info("API call: GET /analytics/overview")
    
    try:
        overview = await analytics_service.get_dashboard_overview(db)
        
        logger.info(
            "Dashboard overview generated",
            extra={
                "extra_data": {
                    "total_animals": overview["animals"]["total"],
                    "detections_today": overview["detections"]["today"],
                    "active_alerts": len(overview["alerts"])
                }
            }
        )
        
        return DashboardOverview(**overview)
        
    except Exception as e:
        logger.error(f"Error generating dashboard overview: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate dashboard overview"
        )


# =============================================================================
# WEIGHT TRENDS
# =============================================================================

@router.get(
    "/trends/weight",
    response_model=WeightTrendsResponse,
    summary="Get weight trends",
    description="""
    Get weight trend data for charting and analysis.
    
    Parameters:
    - animal_id: Specific animal (optional, omit for farm-wide average)
    - days: Number of days to look back (default: 30, max: 365)
    - aggregation: Data granularity (daily/weekly/monthly)
    
    Returns time-series data suitable for line charts, showing:
    - Average weight over time
    - Min/max weight (useful for error bars)
    - Measurement counts
    - Animal counts (for farm-wide trends)
    
    Use cases:
    - Individual animal weight tracking
    - Farm-wide weight trends
    - Growth rate analysis
    - Health monitoring
    """,
    responses={
        200: {
            "description": "Weight trends retrieved successfully",
            "content": {
                "application/json": {
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
            }
        },
        400: {"description": "Invalid parameters"},
        404: {"description": "Animal not found"},
        500: {"description": "Internal server error"}
    },
    tags=["Analytics"]
)
async def get_weight_trends(
    animal_id: Optional[int] = Query(
        None,
        description="Specific animal ID (omit for farm-wide average)",
        gt=0
    ),
    days: int = Query(
        30,
        description="Number of days to look back",
        ge=1,
        le=365
    ),
    aggregation: str = Query(
        "daily",
        description="Data aggregation level",
        regex="^(daily|weekly|monthly)$"
    ),
    db: AsyncSession = Depends(get_db)
) -> WeightTrendsResponse:
    """
    Get weight trend data for charting.
    
    This endpoint is optimized for frontend chart libraries.
    The data format is compatible with Chart.js, Recharts, and similar.
    
    Frontend usage example:
    ```javascript
    const response = await fetch('/api/v1/analytics/trends/weight?days=30');
    const { data } = await response.json();
    
    // Use in Chart.js
    const chartData = {
      labels: data.map(point => point.date),
      datasets: [{
        label: 'Average Weight (kg)',
        data: data.map(point => point.average_weight)
      }]
    };
    ```
    """
    logger.info(
        f"API call: GET /analytics/trends/weight",
        extra={
            "extra_data": {
                "animal_id": animal_id,
                "days": days,
                "aggregation": aggregation
            }
        }
    )
    
    try:
        # Validate animal exists if specified
        if animal_id is not None:
            from app.repositories.animal import AnimalRepository
            animal_repo = AnimalRepository()
            animal = await animal_repo.get_by_id(db, animal_id)
            if not animal:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Animal with id {animal_id} not found"
                )
        
        # Get trends
        trends = await analytics_service.get_weight_trends(
            db,
            animal_id=animal_id,
            days=days,
            aggregation=aggregation
        )
        
        logger.info(
            f"Weight trends generated: {len(trends)} data points",
            extra={
                "extra_data": {
                    "animal_id": animal_id,
                    "data_points": len(trends)
                }
            }
        )
        
        return WeightTrendsResponse(
            data=[WeightTrendPoint(**point) for point in trends],
            animal_id=animal_id,
            period_days=days
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating weight trends: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate weight trends"
        )


# =============================================================================
# DETECTION PATTERNS
# =============================================================================

@router.get(
    "/patterns/detection",
    response_model=DetectionPatternsResponse,
    summary="Analyze detection patterns",
    description="""
    Analyze detection patterns over a date range.
    
    Returns comprehensive detection analytics:
    - 24-hour heatmap (detections per hour)
    - Daily detection counts
    - Per-camera statistics
    - Top detected animals
    - Peak detection times
    - Detection rate metrics
    
    Use cases:
    - Identify peak activity times
    - Compare camera performance
    - Detect behavioral patterns
    - Optimize camera placement
    - Schedule maintenance windows
    """,
    responses={
        200: {
            "description": "Detection patterns analyzed successfully",
            "content": {
                "application/json": {
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
            }
        },
        400: {"description": "Invalid date range"},
        500: {"description": "Internal server error"}
    },
    tags=["Analytics"]
)
async def get_detection_patterns(
    date_from: date = Query(
        ...,
        description="Start date (YYYY-MM-DD)"
    ),
    date_to: date = Query(
        ...,
        description="End date (YYYY-MM-DD)"
    ),
    db: AsyncSession = Depends(get_db)
) -> DetectionPatternsResponse:
    """
    Analyze detection patterns over a date range.
    
    The 24-hour heatmap is particularly useful for understanding
    animal activity patterns throughout the day. This can help:
    - Optimize feeding schedules
    - Identify unusual behavior
    - Schedule farm activities
    - Detect health issues (reduced activity)
    
    Performance note: Large date ranges (>90 days) may take longer.
    Consider using smaller ranges for real-time dashboards.
    """
    logger.info(
        f"API call: GET /analytics/patterns/detection",
        extra={
            "extra_data": {
                "date_from": date_from.isoformat(),
                "date_to": date_to.isoformat()
            }
        }
    )
    
    # Validate date range
    if date_to < date_from:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date_to must be >= date_from"
        )
    
    # Limit range to 1 year
    days_diff = (date_to - date_from).days
    if days_diff > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    try:
        patterns = await analytics_service.get_detection_patterns(
            db,
            date_from=date_from,
            date_to=date_to
        )
        
        logger.info(
            "Detection patterns analyzed",
            extra={
                "extra_data": {
                    "total_detections": patterns["statistics"]["total_detections"],
                    "days_analyzed": days_diff + 1
                }
            }
        )
        
        return DetectionPatternsResponse(**patterns)
        
    except Exception as e:
        logger.error(f"Error analyzing detection patterns: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze detection patterns"
        )


# =============================================================================
# HEALTH METRICS
# =============================================================================

@router.get(
    "/health/metrics",
    response_model=HealthMetricsResponse,
    summary="Get health metrics",
    description="""
    Calculate comprehensive health metrics and indicators.
    
    Returns:
    - Animal distribution by status
    - Weight distribution across ranges
    - Active health alerts (weight loss, no detection)
    - Overall risk score (0-100)
    
    The risk score is calculated based on:
    - Inactive/deceased animal ratios
    - Number of critical alerts
    - Number of warning alerts
    - Detection frequency issues
    
    Risk score interpretation:
    - 0-20: Low risk (healthy farm)
    - 21-50: Medium risk (monitor closely)
    - 51-80: High risk (action recommended)
    - 81-100: Critical risk (immediate action required)
    """,
    responses={
        200: {
            "description": "Health metrics calculated successfully",
            "content": {
                "application/json": {
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
            }
        },
        500: {"description": "Internal server error"}
    },
    tags=["Analytics"]
)
async def get_health_metrics(
    db: AsyncSession = Depends(get_db)
) -> HealthMetricsResponse:
    """
    Calculate comprehensive health metrics.
    
    This endpoint is crucial for proactive farm management.
    It identifies potential health issues before they become serious:
    
    Alert types:
    - never_detected: Animal has never been seen by cameras
    - no_recent_detection: Not detected in 7+ days
    - weight_loss: Significant weight loss (>5% in 7 days)
    
    Best practices:
    - Check this endpoint daily
    - Investigate all critical alerts immediately
    - Monitor risk score trends over time
    - Set up automated notifications for critical scores
    """
    logger.info("API call: GET /analytics/health/metrics")
    
    try:
        metrics = await analytics_service.get_health_metrics(db)
        
        logger.info(
            "Health metrics calculated",
            extra={
                "extra_data": {
                    "risk_score": metrics["risk_score"],
                    "total_alerts": metrics["alert_summary"]["total"],
                    "critical_alerts": metrics["alert_summary"]["critical"]
                }
            }
        )
        
        return HealthMetricsResponse(**metrics)
        
    except Exception as e:
        logger.error(f"Error calculating health metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate health metrics"
        )


# =============================================================================
# CAMERA PERFORMANCE
# =============================================================================

@router.get(
    "/cameras/performance",
    response_model=CameraPerformanceResponse,
    summary="Analyze camera performance",
    description="""
    Analyze camera performance metrics over a period.
    
    Parameters:
    - camera_id: Specific camera (optional, omit for all cameras)
    - days: Number of days to analyze (default: 7, max: 90)
    
    Returns per-camera:
    - Current status (running/stopped/error)
    - Uptime percentage
    - Detection statistics
    - Detection rate (per hour)
    - Average confidence score
    - Current FPS
    - Error counts
    
    Use cases:
    - Monitor camera health
    - Identify failing cameras
    - Optimize camera placement
    - Compare camera performance
    - Schedule maintenance
    """,
    responses={
        200: {
            "description": "Camera performance analyzed successfully",
            "content": {
                "application/json": {
                    "example": {
                        "period": {
                            "days": 7,
                            "from": "2026-02-09T10:30:45.123456",
                            "to": "2026-02-16T10:30:45.123456"
                        },
                        "cameras": [
                            {
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
                        ],
                        "summary": {
                            "total_cameras": 3,
                            "running_cameras": 3,
                            "total_detections": 1523,
                            "average_fps": 10.2
                        }
                    }
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Internal server error"}
    },
    tags=["Analytics"]
)
async def get_camera_performance(
    camera_id: Optional[str] = Query(
        None,
        description="Specific camera ID (omit for all cameras)",
        min_length=1,
        max_length=100
    ),
    days: int = Query(
        7,
        description="Number of days to analyze",
        ge=1,
        le=90
    ),
    db: AsyncSession = Depends(get_db)
) -> CameraPerformanceResponse:
    """
    Analyze camera performance metrics.
    
    This endpoint helps identify camera issues before they impact
    the system. Key metrics to monitor:
    
    - Uptime: Should be >95% for healthy cameras
    - Detection rate: Compare across cameras (similar positions should have similar rates)
    - Confidence: Low average confidence may indicate dirty lens or poor positioning
    - FPS: Should match configured FPS (default: 10)
    - Errors: High error count requires investigation
    
    Troubleshooting:
    - Low uptime: Check network connectivity, power supply
    - Low detection rate: Check camera angle, lighting
    - Low confidence: Clean lens, adjust position
    - High errors: Check logs for specific error messages
    """
    logger.info(
        f"API call: GET /analytics/cameras/performance",
        extra={
            "extra_data": {
                "camera_id": camera_id,
                "days": days
            }
        }
    )
    
    # Validate days range
    if days < 1 or days > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="days must be between 1 and 90"
        )
    
    try:
        performance = await analytics_service.get_camera_performance(
            db,
            camera_id=camera_id,
            days=days
        )
        
        logger.info(
            "Camera performance analyzed",
            extra={
                "extra_data": {
                    "cameras_analyzed": performance["summary"]["total_cameras"],
                    "running_cameras": performance["summary"]["running_cameras"]
                }
            }
        )
        
        return CameraPerformanceResponse(**performance)
        
    except Exception as e:
        logger.error(f"Error analyzing camera performance: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze camera performance"
        )