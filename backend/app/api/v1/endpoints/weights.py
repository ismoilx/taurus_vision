"""
API endpoints for Weight Measurement resources.

Handles CRUD operations and statistics for weight measurements.
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.weight_measurement import WeightMeasurementService
from app.api.v1.websocket import get_ws_manager
from app.schemas.weight_measurement import (
    WeightMeasurementCreate,
    WeightMeasurementResponse,
    WeightMeasurementListResponse,
    WeightStatsResponse,
)

router = APIRouter(
    prefix="/weights",
    tags=["weights"],
)


def get_weight_service(
    db: AsyncSession = Depends(get_db),
) -> WeightMeasurementService:
    """
    Dependency injection for WeightMeasurementService.
    
    Automatically injects WebSocket manager for real-time updates.
    """
    try:
        ws_manager = get_ws_manager()
    except RuntimeError:
        # WebSocket not initialized (e.g., during tests)
        ws_manager = None
    
    return WeightMeasurementService(db, ws_manager)


@router.post(
    "/",
    response_model=WeightMeasurementResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create weight measurement",
    description="""
    Create a new weight measurement from AI camera.
    
    **Business Rules:**
    - Animal must exist
    - Confidence score should be >= 0.5 (warning if lower)
    - Automatically broadcasts to WebSocket clients
    
    **Real-time Broadcasting:**
    All connected dashboard clients will receive this measurement instantly.
    """,
    responses={
        201: {"description": "Measurement created and broadcasted"},
        404: {"description": "Animal not found"},
        422: {"description": "Invalid data"},
    },
)
async def create_measurement(
    measurement_data: WeightMeasurementCreate,
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementResponse:
    """
    Create new weight measurement.
    
    This endpoint is typically called by AI cameras or edge devices
    after performing weight estimation.
    """
    return await service.create_measurement(measurement_data)


@router.get(
    "/{measurement_id}",
    response_model=WeightMeasurementResponse,
    summary="Get measurement by ID",
    responses={
        200: {"description": "Measurement found"},
        404: {"description": "Measurement not found"},
    },
)
async def get_measurement(
    measurement_id: int = Path(..., gt=0),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementResponse:
    """Get a single measurement by ID."""
    return await service.get_measurement(measurement_id)


@router.get(
    "/animal/{animal_id}",
    response_model=WeightMeasurementListResponse,
    summary="Get measurements for an animal",
    description="""
    Get paginated list of weight measurements for a specific animal.
    
    **Filtering:**
    - `min_confidence`: Only return measurements above this confidence threshold
    - `days`: Only return measurements from the last N days
    
    **Pagination:**
    - `skip`: Number of records to skip
    - `limit`: Maximum records to return (max 1000)
    """,
)
async def get_animal_measurements(
    animal_id: int = Path(..., gt=0),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    min_confidence: Optional[float] = Query(
        default=None,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    days: Optional[int] = Query(
        default=None,
        ge=1,
        le=365,
        description="Only get measurements from last N days",
    ),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementListResponse:
    """
    Get weight measurements for a specific animal.
    
    Returns paginated list with time-series data.
    """
    return await service.get_animal_measurements(
        animal_id=animal_id,
        skip=skip,
        limit=limit,
        min_confidence=min_confidence,
        days=days,
    )


@router.get(
    "/animal/{animal_id}/stats",
    response_model=WeightStatsResponse,
    summary="Get weight statistics for an animal",
    description="""
    Calculate weight statistics and trends for an animal.
    
    **Metrics:**
    - Total measurements
    - Average weight
    - Latest weight
    - Weight trend (increasing/decreasing/stable)
    - Average confidence score
    
    **Parameters:**
    - `days`: Analysis period (default 30)
    - `min_confidence`: Only use measurements above this threshold
    """,
)
async def get_animal_stats(
    animal_id: int = Path(..., gt=0),
    days: int = Query(
        default=30,
        ge=1,
        le=365,
        description="Analysis period in days",
    ),
    min_confidence: float = Query(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightStatsResponse:
    """
    Get weight statistics and trend analysis.
    
    Useful for analytics dashboard and health monitoring.
    """
    return await service.get_animal_weight_stats(
        animal_id=animal_id,
        days=days,
        min_confidence=min_confidence,
    )


@router.get(
    "/recent",
    response_model=list[WeightMeasurementResponse],
    summary="Get recent measurements (all animals)",
    description="""
    Get most recent weight measurements across all animals.
    
    Useful for live feed dashboard showing all recent activity.
    """,
)
async def get_recent_measurements(
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum measurements to return",
    ),
    min_confidence: float = Query(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> list[WeightMeasurementResponse]:
    """
    Get recent measurements across all animals.
    
    Returns newest measurements first.
    """
    return await service.get_recent_measurements(
        limit=limit,
        min_confidence=min_confidence,
    )