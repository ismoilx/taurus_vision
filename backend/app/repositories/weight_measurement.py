"""
Weight Measurement repository for time-series data access.

Optimized for high-frequency writes and time-series queries.
"""

from typing import Optional, Sequence
from datetime import datetime, timedelta
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.models.weight_measurement import WeightMeasurement
from app.schemas.weight_measurement import WeightMeasurementCreate
from app.core.exceptions import DatabaseError

logger = logging.getLogger(__name__)


class WeightMeasurementRepository:
    """
    Repository for WeightMeasurement time-series data.
    
    Optimized for:
    - High-frequency inserts (from multiple cameras)
    - Time-range queries
    - Aggregations (statistics, trends)
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(
        self,
        measurement_data: WeightMeasurementCreate,
    ) -> WeightMeasurement:
        """
        Create new weight measurement record.
        
        Optimized for high-throughput inserts.
        
        Args:
            measurement_data: Validated measurement data
            
        Returns:
            Created measurement instance
            
        Raises:
            DatabaseError: If insert fails
        """
        try:
            measurement = WeightMeasurement(**measurement_data.model_dump())
            
            self.db.add(measurement)
            await self.db.flush()
            await self.db.refresh(measurement)
            
            logger.debug(
                f"Created measurement: Animal {measurement.animal_id}, "
                f"Weight {measurement.estimated_weight_kg:.2f}kg"
            )
            
            return measurement
            
        except Exception as e:
            logger.error(f"Failed to create weight measurement: {e}")
            raise DatabaseError(
                message="Failed to create weight measurement",
                details={"error": str(e)},
            )
    
    async def get_by_id(self, measurement_id: int) -> Optional[WeightMeasurement]:
        """Get single measurement by ID."""
        try:
            stmt = select(WeightMeasurement).where(
                WeightMeasurement.id == measurement_id
            )
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get measurement {measurement_id}: {e}")
            raise DatabaseError(
                message="Failed to retrieve measurement",
                details={"measurement_id": measurement_id, "error": str(e)},
            )
    
    async def get_by_animal(
        self,
        animal_id: int,
        skip: int = 0,
        limit: int = 100,
        min_confidence: Optional[float] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Sequence[WeightMeasurement]:
        """
        Get measurements for a specific animal with time filtering.
        
        Args:
            animal_id: Animal primary key
            skip: Pagination offset
            limit: Maximum results
            min_confidence: Filter by minimum confidence score
            start_date: Filter measurements after this date
            end_date: Filter measurements before this date
            
        Returns:
            List of measurements ordered by timestamp (newest first)
        """
        try:
            stmt = select(WeightMeasurement).where(
                WeightMeasurement.animal_id == animal_id
            )
            
            # Apply filters
            if min_confidence is not None:
                stmt = stmt.where(
                    WeightMeasurement.confidence_score >= min_confidence
                )
            
            if start_date:
                stmt = stmt.where(WeightMeasurement.timestamp >= start_date)
            
            if end_date:
                stmt = stmt.where(WeightMeasurement.timestamp <= end_date)
            
            # Order by timestamp (newest first)
            stmt = stmt.order_by(WeightMeasurement.timestamp.desc())
            
            # Pagination
            stmt = stmt.offset(skip).limit(limit)
            
            result = await self.db.execute(stmt)
            measurements = result.scalars().all()
            
            return measurements
            
        except Exception as e:
            logger.error(f"Failed to get measurements for animal {animal_id}: {e}")
            raise DatabaseError(
                message="Failed to retrieve measurements",
                details={"animal_id": animal_id, "error": str(e)},
            )
    
    async def count_by_animal(
        self,
        animal_id: int,
        min_confidence: Optional[float] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> int:
        """Count measurements for an animal with filters."""
        try:
            stmt = select(func.count()).select_from(WeightMeasurement).where(
                WeightMeasurement.animal_id == animal_id
            )
            
            if min_confidence is not None:
                stmt = stmt.where(
                    WeightMeasurement.confidence_score >= min_confidence
                )
            
            if start_date:
                stmt = stmt.where(WeightMeasurement.timestamp >= start_date)
            
            if end_date:
                stmt = stmt.where(WeightMeasurement.timestamp <= end_date)
            
            result = await self.db.execute(stmt)
            return result.scalar_one()
            
        except Exception as e:
            logger.error(f"Failed to count measurements: {e}")
            raise DatabaseError(
                message="Failed to count measurements",
                details={"error": str(e)},
            )
    
    async def get_latest_by_animal(
        self,
        animal_id: int,
    ) -> Optional[WeightMeasurement]:
        """
        Get most recent measurement for an animal.
        
        Useful for displaying current weight.
        """
        try:
            stmt = (
                select(WeightMeasurement)
                .where(WeightMeasurement.animal_id == animal_id)
                .order_by(WeightMeasurement.timestamp.desc())
                .limit(1)
            )
            
            result = await self.db.execute(stmt)
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Failed to get latest measurement: {e}")
            raise DatabaseError(
                message="Failed to retrieve latest measurement",
                details={"animal_id": animal_id, "error": str(e)},
            )
    
    async def get_weight_stats(
        self,
        animal_id: int,
        days: int = 30,
        min_confidence: float = 0.7,
    ) -> dict:
        """
        Calculate weight statistics for an animal.
        
        Args:
            animal_id: Animal primary key
            days: Number of days to analyze
            min_confidence: Minimum confidence threshold
            
        Returns:
            Dictionary with statistics:
            - total_measurements
            - average_weight
            - min_weight
            - max_weight
            - weight_change (vs first measurement)
            - confidence_average
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            stmt = select(
                func.count(WeightMeasurement.id).label("total"),
                func.avg(WeightMeasurement.estimated_weight_kg).label("avg_weight"),
                func.min(WeightMeasurement.estimated_weight_kg).label("min_weight"),
                func.max(WeightMeasurement.estimated_weight_kg).label("max_weight"),
                func.avg(WeightMeasurement.confidence_score).label("avg_confidence"),
            ).where(
                and_(
                    WeightMeasurement.animal_id == animal_id,
                    WeightMeasurement.timestamp >= cutoff_date,
                    WeightMeasurement.confidence_score >= min_confidence,
                )
            )
            
            result = await self.db.execute(stmt)
            row = result.first()
            
            if not row or row.total == 0:
                return {
                    "total_measurements": 0,
                    "average_weight": None,
                    "min_weight": None,
                    "max_weight": None,
                    "weight_change": None,
                    "confidence_average": None,
                }
            
            # Get first and last measurements for trend
            first_stmt = (
                select(WeightMeasurement.estimated_weight_kg)
                .where(
                    and_(
                        WeightMeasurement.animal_id == animal_id,
                        WeightMeasurement.timestamp >= cutoff_date,
                        WeightMeasurement.confidence_score >= min_confidence,
                    )
                )
                .order_by(WeightMeasurement.timestamp.asc())
                .limit(1)
            )
            first_result = await self.db.execute(first_stmt)
            first_weight = first_result.scalar_one_or_none()
            
            weight_change = None
            if first_weight and row.avg_weight:
                weight_change = row.max_weight - first_weight
            
            return {
                "total_measurements": row.total,
                "average_weight": float(row.avg_weight) if row.avg_weight else None,
                "min_weight": float(row.min_weight) if row.min_weight else None,
                "max_weight": float(row.max_weight) if row.max_weight else None,
                "weight_change": float(weight_change) if weight_change else None,
                "confidence_average": float(row.avg_confidence) if row.avg_confidence else None,
            }
            
        except Exception as e:
            logger.error(f"Failed to calculate weight stats: {e}")
            raise DatabaseError(
                message="Failed to calculate statistics",
                details={"animal_id": animal_id, "error": str(e)},
            )
    
    async def get_recent_global(
        self,
        limit: int = 50,
        min_confidence: float = 0.7,
    ) -> Sequence[WeightMeasurement]:
        """
        Get most recent measurements across all animals.
        
        Useful for live feed dashboard.
        
        Args:
            limit: Maximum number of measurements
            min_confidence: Minimum confidence threshold
            
        Returns:
            Recent measurements ordered by timestamp (newest first)
        """
        try:
            stmt = (
                select(WeightMeasurement)
                .where(WeightMeasurement.confidence_score >= min_confidence)
                .order_by(WeightMeasurement.timestamp.desc())
                .limit(limit)
            )
            
            result = await self.db.execute(stmt)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to get recent global measurements: {e}")
            raise DatabaseError(
                message="Failed to retrieve recent measurements",
                details={"error": str(e)},
            )