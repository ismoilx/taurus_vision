"""
API endpoints for Weight Measurement resources.

Handles CRUD operations and statistics for weight measurements.

ENDPOINTS:
    POST /weights/              — Yangi o'lchov yaratish (kamera/AI dan)
    GET  /weights/              — Barcha o'lchovlar ro'yxati (paginated)
    GET  /weights/recent        — Oxirgi o'lchovlar (barcha jonivorlar)
    GET  /weights/{id}          — Bitta o'lchov
    GET  /weights/animal/{id}   — Jonivor o'lchovlari
    GET  /weights/animal/{id}/stats — Jonivor statistikasi
"""

from typing import Optional
from fastapi import APIRouter, Depends, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
import logging

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.models.weight_measurement import WeightMeasurement
from app.models.animal import Animal
from app.services.weight_measurement import WeightMeasurementService
from app.api.v1.websocket import get_ws_manager
from app.schemas.weight_measurement import (
    WeightMeasurementCreate,
    WeightMeasurementResponse,
    WeightMeasurementListResponse,
    WeightStatsResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/weights",
    tags=["weights"],
    dependencies=[Depends(get_current_active_user)],
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
        ws_manager = None

    return WeightMeasurementService(db, ws_manager)


# ============================================================================
# CREATE
# ============================================================================

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
    """,
)
async def create_measurement(
    measurement_data: WeightMeasurementCreate,
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementResponse:
    """Create new weight measurement and broadcast via WebSocket."""
    result = await service.create_measurement(measurement_data)

    # WebSocket broadcast
    try:
        ws_manager = get_ws_manager()
        broadcast_data = {
            "animal_id":           result.animal_id,
            "animal_tag_id":       getattr(result, "animal_tag_id", "UNKNOWN"),
            "estimated_weight_kg": result.estimated_weight_kg,
            "confidence_score":    result.confidence_score,
            "camera_id":           result.camera_id,
            "timestamp":           result.timestamp.isoformat() if result.timestamp else None,
        }
        await ws_manager.broadcast(broadcast_data)
        logger.info(f"📡 Broadcast sent for Animal {broadcast_data['animal_tag_id']}")
    except Exception as e:
        logger.error(f"⚠️ WebSocket broadcast failed: {e}")

    return result


# ============================================================================
# LIST ALL (Dashboard uchun)
# ============================================================================

@router.get(
    "/",
    response_model=WeightMeasurementListResponse,
    summary="List all weight measurements",
    description="""
    Get paginated list of ALL weight measurements across all animals.

    **Sorted by:** timestamp descending (newest first)

    **Use case:** Dashboard "Oxirgi O'lchovlar" widget.
    """,
)
async def list_measurements(
    skip:  int = Query(default=0,   ge=0,  description="Offset"),
    limit: int = Query(default=20,  ge=1,  le=200, description="Max results"),
    animal_id: Optional[int] = Query(default=None, description="Filter by animal"),
    db: AsyncSession = Depends(get_db),
) -> WeightMeasurementListResponse:
    """
    Return paginated weight measurements with animal tag info.

    Args:
        skip:      Pagination offset
        limit:     Max results to return
        animal_id: Optional animal filter
        db:        Database session

    Returns:
        WeightMeasurementListResponse with items list and total count
    """
    # Base query
    count_q = select(func.count(WeightMeasurement.id))
    items_q = (
        select(WeightMeasurement)
        .order_by(desc(WeightMeasurement.timestamp))
        .offset(skip)
        .limit(limit)
    )

    if animal_id is not None:
        count_q = count_q.where(WeightMeasurement.animal_id == animal_id)
        items_q = items_q.where(WeightMeasurement.animal_id == animal_id)

    total  = await db.scalar(count_q) or 0
    result = await db.execute(items_q)
    rows   = result.scalars().all()

    return WeightMeasurementListResponse(
        items=list(rows),
        total=total,
        skip=skip,
        limit=limit,
    )


# ============================================================================
# RECENT (LiveFeed uchun)
# ============================================================================

@router.get(
    "/recent",
    response_model=list[WeightMeasurementResponse],
    summary="Get recent measurements (all animals)",
    description="Get most recent weight measurements across all animals. Useful for live feed.",
)
async def get_recent_measurements(
    limit: int = Query(default=50, ge=1, le=200),
    min_confidence: float = Query(default=0.0, ge=0.0, le=1.0),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> list[WeightMeasurementResponse]:
    """Get recent measurements across all animals, newest first."""
    return await service.get_recent_measurements(
        limit=limit,
        min_confidence=min_confidence,
    )


# ============================================================================
# GET ONE
# ============================================================================

@router.get(
    "/{measurement_id}",
    response_model=WeightMeasurementResponse,
    summary="Get measurement by ID",
)
async def get_measurement(
    measurement_id: int = Path(..., gt=0),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementResponse:
    """Get a single measurement by ID."""
    return await service.get_measurement(measurement_id)


# ============================================================================
# BY ANIMAL
# ============================================================================

@router.get(
    "/animal/{animal_id}",
    response_model=WeightMeasurementListResponse,
    summary="Get measurements for an animal",
)
async def get_animal_measurements(
    animal_id: int = Path(..., gt=0),
    skip:  int = Query(default=0,   ge=0),
    limit: int = Query(default=100, ge=1, le=1000),
    min_confidence: Optional[float] = Query(default=None, ge=0.0, le=1.0),
    days: Optional[int] = Query(default=None, ge=1, le=365),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightMeasurementListResponse:
    """Get weight measurements for a specific animal (paginated)."""
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
)
async def get_animal_stats(
    animal_id: int = Path(..., gt=0),
    days: int = Query(default=30, ge=1, le=365),
    min_confidence: float = Query(default=0.7, ge=0.0, le=1.0),
    service: WeightMeasurementService = Depends(get_weight_service),
) -> WeightStatsResponse:
    """Get weight statistics and trend analysis for an animal."""
    return await service.get_animal_weight_stats(
        animal_id=animal_id,
        days=days,
        min_confidence=min_confidence,
    )