"""
Health Record Service - Taurus Vision

Business logic layer for health records.
Handles complex operations, validations, and orchestrates repository calls.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health_record import (
    HealthRecord,
    HealthRecordType,
    HealthRecordSeverity
)
from app.repositories.health_record import HealthRecordRepository
from app.repositories.animal import AnimalRepository
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class HealthRecordService:
    """
    Service layer for health record operations.
    
    Provides high-level business logic for:
    - Creating and managing health records
    - Scheduling checkups
    - Tracking critical issues
    - Generating health reports
    - Statistics and analytics
    
    Validates data and coordinates between repositories.
    """
    
    def __init__(self):
        """Initialize service with repositories."""
        self.health_repo = HealthRecordRepository()
        self.animal_repo = AnimalRepository()
    
    # =========================================================================
    # CREATE HEALTH RECORD
    # =========================================================================
    
    async def create_health_record(
        self,
        db: AsyncSession,
        animal_id: int,
        record_type: HealthRecordType,
        severity: HealthRecordSeverity,
        diagnosis: str,
        symptoms: Optional[str] = None,
        treatment: Optional[str] = None,
        medication: Optional[str] = None,
        dosage: Optional[str] = None,
        veterinarian: Optional[str] = None,
        clinic_name: Optional[str] = None,
        cost: Optional[float] = None,
        notes: Optional[str] = None,
        recorded_at: Optional[datetime] = None,
        next_checkup_date: Optional[date] = None
    ) -> HealthRecord:
        """
        Create a new health record with validation.
        
        Args:
            db: Database session
            animal_id: Animal ID
            record_type: Type of health record
            severity: Severity level
            diagnosis: Medical diagnosis
            symptoms: Observed symptoms
            treatment: Treatment provided
            medication: Medications administered
            dosage: Medication dosage
            veterinarian: Veterinarian name
            clinic_name: Clinic name
            cost: Treatment cost
            notes: Additional notes
            recorded_at: Record timestamp (defaults to now)
            next_checkup_date: Next checkup date
        
        Returns:
            Created HealthRecord
        
        Raises:
            ValueError: If animal not found or validation fails
        
        Example:
            >>> service = HealthRecordService()
            >>> record = await service.create_health_record(
            ...     db,
            ...     animal_id=5,
            ...     record_type=HealthRecordType.VACCINATION,
            ...     severity=HealthRecordSeverity.NORMAL,
            ...     diagnosis="Routine FMD vaccination",
            ...     treatment="FMD vaccine administered"
            ... )
        """
        logger.info(f"Creating health record: animal_id={animal_id}, type={record_type.value}")
        
        # Validate animal exists
        animal = await self.animal_repo.get_by_id(db, animal_id)
        if not animal:
            raise ValueError(f"Animal with id {animal_id} not found")
        
        # Validate dates
        if recorded_at is None:
            recorded_at = datetime.utcnow()
        
        if next_checkup_date and next_checkup_date < date.today():
            raise ValueError("Next checkup date cannot be in the past")
        
        # Validate cost
        if cost is not None and cost < 0:
            raise ValueError("Cost cannot be negative")
        
        # Create record
        health_record = HealthRecord(
            animal_id=animal_id,
            record_type=record_type,
            severity=severity,
            diagnosis=diagnosis,
            symptoms=symptoms,
            treatment=treatment,
            medication=medication,
            dosage=dosage,
            veterinarian=veterinarian,
            clinic_name=clinic_name,
            cost=cost,
            notes=notes,
            recorded_at=recorded_at,
            next_checkup_date=next_checkup_date,
            is_resolved=False
        )
        
        created = await self.health_repo.create(db, health_record)
        
        logger.info(
            f"Health record created successfully: id={created.id}, "
            f"animal_id={animal_id}, type={record_type.value}, severity={severity.value}"
        )
        
        return created
    
    # =========================================================================
    # GET HEALTH RECORDS
    # =========================================================================
    
    async def get_record_by_id(
        self,
        db: AsyncSession,
        record_id: int
    ) -> Optional[HealthRecord]:
        """
        Get health record by ID.
        
        Args:
            db: Database session
            record_id: Health record ID
        
        Returns:
            HealthRecord if found, None otherwise
        """
        logger.debug(f"Fetching health record: id={record_id}")
        return await self.health_repo.get_by_id(db, record_id)
    
    async def get_animal_records(
        self,
        db: AsyncSession,
        animal_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get all health records for an animal.
        
        Args:
            db: Database session
            animal_id: Animal ID
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        
        Raises:
            ValueError: If animal not found
        """
        logger.debug(f"Fetching health records for animal_id={animal_id}")
        
        # Validate animal exists
        animal = await self.animal_repo.get_by_id(db, animal_id)
        if not animal:
            raise ValueError(f"Animal with id {animal_id} not found")
        
        return await self.health_repo.get_by_animal(db, animal_id, skip, limit)
    
    async def get_records_by_type(
        self,
        db: AsyncSession,
        record_type: HealthRecordType,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get health records by type.
        
        Args:
            db: Database session
            record_type: Type of health record
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        """
        logger.debug(f"Fetching health records by type={record_type.value}")
        return await self.health_repo.get_by_type(db, record_type, skip, limit)
    
    async def get_records_by_severity(
        self,
        db: AsyncSession,
        severity: HealthRecordSeverity,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get health records by severity.
        
        Args:
            db: Database session
            severity: Severity level
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        """
        logger.debug(f"Fetching health records by severity={severity.value}")
        return await self.health_repo.get_by_severity(db, severity, skip, limit)
    
    async def get_unresolved_records(
        self,
        db: AsyncSession,
        animal_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get unresolved health records.
        
        Args:
            db: Database session
            animal_id: Optional animal filter
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        
        Use case:
            Dashboard showing active health issues
        """
        logger.debug(f"Fetching unresolved health records, animal_id={animal_id}")
        return await self.health_repo.get_unresolved(db, animal_id, skip, limit)
    
    async def get_critical_records(
        self,
        db: AsyncSession,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get critical unresolved health records.
        
        Args:
            db: Database session
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        
        Use case:
            Alert system for critical health issues
        """
        logger.debug("Fetching critical unresolved health records")
        records, total = await self.health_repo.get_critical_unresolved(db, skip, limit)
        
        if total > 0:
            logger.warning(f"Found {total} critical unresolved health records")
        
        return records, total
    
    async def get_upcoming_checkups(
        self,
        db: AsyncSession,
        days_ahead: int = 7,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get upcoming scheduled checkups.
        
        Args:
            db: Database session
            days_ahead: Number of days to look ahead
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        
        Use case:
            Reminder system for scheduled checkups
        """
        logger.debug(f"Fetching upcoming checkups (next {days_ahead} days)")
        return await self.health_repo.get_upcoming_checkups(db, days_ahead, skip, limit)
    
    # =========================================================================
    # UPDATE HEALTH RECORD
    # =========================================================================
    
    async def update_health_record(
        self,
        db: AsyncSession,
        record_id: int,
        **kwargs
    ) -> Optional[HealthRecord]:
        """
        Update health record.
        
        Args:
            db: Database session
            record_id: Health record ID
            **kwargs: Fields to update
        
        Returns:
            Updated HealthRecord if found, None otherwise
        
        Validations:
        - Cost cannot be negative
        - Next checkup date cannot be in the past
        
        Example:
            >>> updated = await service.update_health_record(
            ...     db,
            ...     record_id=10,
            ...     treatment="Updated treatment plan",
            ...     cost=150.00
            ... )
        """
        logger.info(f"Updating health record: id={record_id}")
        
        # Validate cost
        if 'cost' in kwargs and kwargs['cost'] is not None:
            if kwargs['cost'] < 0:
                raise ValueError("Cost cannot be negative")
        
        # Validate next_checkup_date
        if 'next_checkup_date' in kwargs and kwargs['next_checkup_date']:
            if kwargs['next_checkup_date'] < date.today():
                raise ValueError("Next checkup date cannot be in the past")
        
        updated = await self.health_repo.update(db, record_id, **kwargs)
        
        if updated:
            logger.info(f"Health record updated successfully: id={record_id}")
        else:
            logger.warning(f"Health record not found: id={record_id}")
        
        return updated
    
    async def resolve_health_record(
        self,
        db: AsyncSession,
        record_id: int,
        resolved_at: Optional[datetime] = None
    ) -> Optional[HealthRecord]:
        """
        Mark health record as resolved.
        
        Args:
            db: Database session
            record_id: Health record ID
            resolved_at: Resolution timestamp (defaults to now)
        
        Returns:
            Updated HealthRecord if found, None otherwise
        """
        logger.info(f"Resolving health record: id={record_id}")
        
        resolved = await self.health_repo.mark_resolved(db, record_id, resolved_at)
        
        if resolved:
            logger.info(f"Health record resolved: id={record_id}")
        else:
            logger.warning(f"Health record not found: id={record_id}")
        
        return resolved
    
    # =========================================================================
    # DELETE HEALTH RECORD
    # =========================================================================
    
    async def delete_health_record(
        self,
        db: AsyncSession,
        record_id: int
    ) -> bool:
        """
        Delete health record.
        
        Args:
            db: Database session
            record_id: Health record ID
        
        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting health record: id={record_id}")
        
        deleted = await self.health_repo.delete(db, record_id)
        
        if deleted:
            logger.info(f"Health record deleted: id={record_id}")
        else:
            logger.warning(f"Health record not found: id={record_id}")
        
        return deleted
    
    # =========================================================================
    # STATISTICS & ANALYTICS
    # =========================================================================
    
    async def get_health_statistics(
        self,
        db: AsyncSession,
        animal_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get comprehensive health statistics.
        
        Args:
            db: Database session
            animal_id: Optional animal filter
        
        Returns:
            Dictionary with statistics
        
        Statistics include:
        - Total records
        - Records by type
        - Records by severity
        - Unresolved count
        - Critical count
        - Recent trends
        
        Example:
            >>> stats = await service.get_health_statistics(db, animal_id=5)
            >>> print(f"Total records: {stats['total_records']}")
            >>> print(f"Critical issues: {stats['critical_unresolved']}")
        """
        logger.debug(f"Calculating health statistics, animal_id={animal_id}")
        
        stats = await self.health_repo.get_statistics(db, animal_id)
        
        # Add additional computed statistics
        stats['health_score'] = self._calculate_health_score(stats)
        
        return stats
    
    async def get_health_summary(
        self,
        db: AsyncSession,
        animal_id: int
    ) -> Dict[str, Any]:
        """
        Get comprehensive health summary for an animal.
        
        Args:
            db: Database session
            animal_id: Animal ID
        
        Returns:
            Dictionary with health summary
        
        Summary includes:
        - Total records
        - Latest record
        - Unresolved issues
        - Critical issues
        - Upcoming checkups
        - Health score
        
        Raises:
            ValueError: If animal not found
        """
        logger.debug(f"Generating health summary for animal_id={animal_id}")
        
        # Validate animal
        animal = await self.animal_repo.get_by_id(db, animal_id)
        if not animal:
            raise ValueError(f"Animal with id {animal_id} not found")
        
        # Get statistics
        stats = await self.health_repo.get_statistics(db, animal_id)
        
        # Get latest record
        records, _ = await self.health_repo.get_by_animal(db, animal_id, skip=0, limit=1)
        latest_record = records[0] if records else None
        
        # Get unresolved
        unresolved, unresolved_total = await self.health_repo.get_unresolved(
            db, animal_id, skip=0, limit=5
        )
        
        # Get upcoming checkups
        upcoming, upcoming_total = await self.health_repo.get_upcoming_checkups(
            db, days_ahead=30, skip=0, limit=5
        )
        
        # Calculate health score
        health_score = self._calculate_health_score(stats)
        
        summary = {
            "animal_id": animal_id,
            "animal_tag": animal.tag_id,
            "total_records": stats['total_records'],
            "latest_record": {
                "id": latest_record.id,
                "type": latest_record.record_type.value,
                "severity": latest_record.severity.value,
                "diagnosis": latest_record.diagnosis,
                "recorded_at": latest_record.recorded_at.isoformat()
            } if latest_record else None,
            "unresolved_issues": {
                "count": unresolved_total,
                "records": [
                    {
                        "id": r.id,
                        "type": r.record_type.value,
                        "severity": r.severity.value,
                        "diagnosis": r.diagnosis
                    }
                    for r in unresolved
                ]
            },
            "upcoming_checkups": {
                "count": upcoming_total,
                "next_date": upcoming[0].next_checkup_date.isoformat() if upcoming else None
            },
            "statistics": stats,
            "health_score": health_score,
            "health_status": self._get_health_status(health_score),
        }
        
        logger.info(
            f"Health summary generated: animal_id={animal_id}, "
            f"health_score={health_score}, status={summary['health_status']}"
        )
        
        return summary
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    def _calculate_health_score(self, stats: Dict[str, Any]) -> int:
        """
        Calculate health score (0-100) based on statistics.
        
        Higher score = better health
        
        Args:
            stats: Health statistics
        
        Returns:
            Health score (0-100)
        """
        score = 100
        
        # Deduct for unresolved issues
        unresolved = stats.get('unresolved', 0)
        score -= min(unresolved * 5, 30)  # Max -30 for unresolved
        
        # Deduct heavily for critical issues
        critical = stats.get('critical_unresolved', 0)
        score -= min(critical * 15, 40)  # Max -40 for critical
        
        # Deduct based on severity distribution
        by_severity = stats.get('by_severity', {})
        warning_count = by_severity.get('warning', 0)
        critical_count = by_severity.get('critical', 0)
        
        score -= min(warning_count * 2, 15)  # Max -15 for warnings
        score -= min(critical_count * 5, 20)  # Max -20 for critical history
        
        return max(0, score)
    
    def _get_health_status(self, health_score: int) -> str:
        """
        Get health status label based on score.
        
        Args:
            health_score: Health score (0-100)
        
        Returns:
            Status label (excellent/good/fair/poor/critical)
        """
        if health_score >= 90:
            return "excellent"
        elif health_score >= 75:
            return "good"
        elif health_score >= 60:
            return "fair"
        elif health_score >= 40:
            return "poor"
        else:
            return "critical"