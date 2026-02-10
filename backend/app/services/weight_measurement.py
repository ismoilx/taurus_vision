"""
Weight Measurement service layer.

Handles business logic for weight measurements and coordinates
with WebSocket manager for real-time updates.
"""

from typing import Optional, TYPE_CHECKING
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.repositories.weight_measurement import WeightMeasurementRepository
from app.repositories.animal import AnimalRepository
from app.schemas.weight_measurement import (
    WeightMeasurementCreate,
    WeightMeasurementResponse,
    WeightMeasurementListResponse,
    WeightStatsResponse,
    LiveWeightUpdate,
)
from app.core.exceptions import (
    EntityNotFoundError,
    BusinessRuleViolationError,
)

# Avoid circular import for type hints
if TYPE_CHECKING:
    from app.api.v1.websocket import ConnectionManager

logger = logging.getLogger(__name__)


class WeightMeasurementService:
    """
    Service layer for weight measurement operations.
    
    BUSINESS RULES:
    1. Animal must exist before recording measurements
    2. Confidence score thresholds for data quality
    3. Real-time broadcasting to connected clients
    4. Time-series data validation
    
    Args:
        db: AsyncSession instance
        ws_manager: WebSocket connection manager (optional, for real-time updates)
    """
    
    def __init__(
        self,
        db: AsyncSession,
        ws_manager: Optional["ConnectionManager"] = None,
    ):
        self.db = db
        self.repository = WeightMeasurementRepository(db)
        self.animal_repository = AnimalRepository(db)
        self.ws_manager = ws_manager
    
    async def create_measurement(
        self,
        measurement_data: WeightMeasurementCreate,
    ) -> WeightMeasurementResponse:
        """
        Create new weight measurement with validation and broadcasting.
        
        BUSINESS RULES:
        1. Animal must exist
        2. Confidence score should be >= 0.5 (warning if lower)
        3. Broadcast to all connected WebSocket clients
        
        Args:
            measurement_data: Validated measurement data
            
        Returns:
            Created measurement response
            
        Raises:
            EntityNotFoundError: If animal doesn't exist
            BusinessRuleViolationError: If data quality is too poor
        """
        # RULE 1: Verify animal exists
        animal = await self.animal_repository.get_by_id(
            measurement_data.animal_id
        )
        
        if not animal:
            logger.warning(
                f"Attempted to create measurement for non-existent animal: "
                f"{measurement_data.animal_id}"
            )
            raise EntityNotFoundError(
                message=f"Animal with ID {measurement_data.animal_id} not found",
                details={"animal_id": measurement_data.animal_id},
            )
        
        # RULE 2: Check confidence threshold
        if measurement_data.confidence_score < 0.5:
            logger.warning(
                f"Low confidence measurement: {measurement_data.confidence_score:.2f} "
                f"for animal {measurement_data.animal_id}"
            )
            # We allow it but log warning
            # In production, you might reject measurements below threshold
        
        # Create measurement
        measurement = await self.repository.create(measurement_data)
        
        logger.info(
            f"Measurement created: Animal {animal.tag_id}, "
            f"Weight {measurement.estimated_weight_kg:.2f}kg, "
            f"Confidence {measurement.confidence_score:.2f}"
        )
        
        # RULE 3: Broadcast to WebSocket clients
        if self.ws_manager:
            await self._broadcast_measurement(measurement, animal.tag_id)
        
        return WeightMeasurementResponse.model_validate(measurement)
    
    async def _broadcast_measurement(
        self,
        measurement,
        animal_tag_id: str,
    ) -> None:
        """
        Broadcast measurement to all connected WebSocket clients.
        
        Creates lightweight update message optimized for real-time transmission.
        """
        try:
            update = LiveWeightUpdate(
                measurement_id=measurement.id,
                animal_id=measurement.animal_id,
                animal_tag_id=animal_tag_id,
                estimated_weight_kg=measurement.estimated_weight_kg,
                confidence_score=measurement.confidence_score,
                camera_id=measurement.camera_id,
                timestamp=measurement.timestamp,
            )
            
            await self.ws_manager.broadcast(update.model_dump())
            
            logger.debug(
                f"Broadcasted measurement {measurement.id} to "
                f"{self.ws_manager.active_connections} clients"
            )
            
        except Exception as e:
            # Don't fail the measurement creation if broadcast fails
            logger.error(f"Failed to broadcast measurement: {e}")
    
    async def get_measurement(
        self,
        measurement_id: int,
    ) -> WeightMeasurementResponse:
        """Get single measurement by ID."""
        measurement = await self.repository.get_by_id(measurement_id)
        
        if not measurement:
            raise EntityNotFoundError(
                message=f"Measurement with ID {measurement_id} not found",
                details={"measurement_id": measurement_id},
            )
        
        return WeightMeasurementResponse.model_validate(measurement)
    
    async def get_animal_measurements(
        self,
        animal_id: int,
        skip: int = 0,
        limit: int = 100,
        min_confidence: Optional[float] = None,
        days: Optional[int] = None,
    ) -> WeightMeasurementListResponse:
        """
        Get measurements for a specific animal.
        
        Args:
            animal_id: Animal primary key
            skip: Pagination offset
            limit: Maximum results (capped at 1000)
            min_confidence: Filter by minimum confidence
            days: Only get measurements from last N days
            
        Returns:
            Paginated list of measurements
        """
        # Verify animal exists
        animal = await self.animal_repository.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
        
        # Cap limit to prevent abuse
        if limit > 1000:
            limit = 1000
            logger.warning(f"Limit capped to 1000 (requested: {limit})")
        
        # Calculate date range
        start_date = None
        end_date = None
        if days:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)
        
        # Get measurements
        measurements = await self.repository.get_by_animal(
            animal_id=animal_id,
            skip=skip,
            limit=limit,
            min_confidence=min_confidence,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Get total count
        total = await self.repository.count_by_animal(
            animal_id=animal_id,
            min_confidence=min_confidence,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Convert to response
        items = [
            WeightMeasurementResponse.model_validate(m)
            for m in measurements
        ]
        
        return WeightMeasurementListResponse(
            items=items,
            total=total,
            skip=skip,
            limit=limit,
        )
    
    async def get_animal_weight_stats(
        self,
        animal_id: int,
        days: int = 30,
        min_confidence: float = 0.7,
    ) -> WeightStatsResponse:
        """
        Get weight statistics for an animal.
        
        BUSINESS LOGIC:
        - Calculate trend direction based on first vs last measurement
        - Only use high-confidence measurements (>= 0.7 by default)
        
        Args:
            animal_id: Animal primary key
            days: Analysis period (default 30 days)
            min_confidence: Confidence threshold
            
        Returns:
            Weight statistics including trend
        """
        # Verify animal exists
        animal = await self.animal_repository.get_by_id(animal_id)
        if not animal:
            raise EntityNotFoundError(
                message=f"Animal with ID {animal_id} not found",
                details={"animal_id": animal_id},
            )
        
        # Get stats from repository
        stats = await self.repository.get_weight_stats(
            animal_id=animal_id,
            days=days,
            min_confidence=min_confidence,
        )
        
        # Determine trend
        trend = None
        if stats["weight_change"] is not None:
            if stats["weight_change"] > 5:  # More than 5kg increase
                trend = "increasing"
            elif stats["weight_change"] < -5:  # More than 5kg decrease
                trend = "decreasing"
            else:
                trend = "stable"
        
        # Get date range
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Get first and last measurement dates
        measurements = await self.repository.get_by_animal(
            animal_id=animal_id,
            skip=0,
            limit=1,
            min_confidence=min_confidence,
            start_date=cutoff_date,
        )
        
        last_date = measurements[0].timestamp if measurements else None
        
        # Get oldest measurement
        oldest = await self.repository.get_by_animal(
            animal_id=animal_id,
            skip=0,
            limit=1,
            min_confidence=min_confidence,
            start_date=cutoff_date,
        )
        first_date = oldest[-1].timestamp if oldest else None
        
        # Get latest weight
        latest = await self.repository.get_latest_by_animal(animal_id)
        latest_weight = latest.estimated_weight_kg if latest else None
        
        return WeightStatsResponse(
            animal_id=animal_id,
            total_measurements=stats["total_measurements"],
            average_weight_kg=stats["average_weight"] or 0.0,
            latest_weight_kg=latest_weight,
            weight_trend=trend,
            confidence_average=stats["confidence_average"] or 0.0,
            first_measurement_date=first_date,
            last_measurement_date=last_date,
        )
    
    async def get_recent_measurements(
        self,
        limit: int = 50,
        min_confidence: float = 0.7,
    ) -> list[WeightMeasurementResponse]:
        """
        Get recent measurements across all animals.
        
        Useful for live feed dashboard.
        
        Args:
            limit: Maximum measurements to return
            min_confidence: Confidence threshold
            
        Returns:
            List of recent measurements
        """
        measurements = await self.repository.get_recent_global(
            limit=limit,
            min_confidence=min_confidence,
        )
        
        return [
            WeightMeasurementResponse.model_validate(m)
            for m in measurements
        ]