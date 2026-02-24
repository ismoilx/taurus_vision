"""
Health Record Repository - Taurus Vision

Data access layer for health records.
Handles all database operations for health records using async SQLAlchemy.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime, date
from typing import Optional, List, Tuple
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.health_record import (
    HealthRecord,
    HealthRecordType,
    HealthRecordSeverity
)
from app.core.logging_config import get_logger

logger = get_logger(__name__)


class HealthRecordRepository:
    """
    Repository for HealthRecord database operations.
    
    Provides async methods for:
    - CRUD operations
    - Complex queries (by animal, by type, by severity)
    - Pagination and filtering
    - Upcoming checkups
    - Critical/unresolved records
    
    All methods are async and use AsyncSession.
    """
    
    # =========================================================================
    # CREATE
    # =========================================================================
    
    async def create(
        self,
        db: AsyncSession,
        health_record: HealthRecord
    ) -> HealthRecord:
        """
        Create a new health record.
        
        Args:
            db: Database session
            health_record: HealthRecord instance to create
        
        Returns:
            Created HealthRecord with ID
        
        Example:
            >>> repo = HealthRecordRepository()
            >>> record = HealthRecord(
            ...     animal_id=5,
            ...     record_type=HealthRecordType.VACCINATION,
            ...     severity=HealthRecordSeverity.NORMAL,
            ...     diagnosis="Routine vaccination",
            ...     treatment="FMD vaccine"
            ... )
            >>> created = await repo.create(db, record)
        """
        logger.debug(f"Creating health record for animal_id={health_record.animal_id}")
        
        db.add(health_record)
        await db.commit()
        await db.refresh(health_record)
        
        logger.info(f"Health record created: id={health_record.id}, animal_id={health_record.animal_id}")
        return health_record
    
    # =========================================================================
    # READ
    # =========================================================================
    
    async def get_by_id(
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
        
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(HealthRecord.id == record_id)
        
        result = await db.execute(query)
        return result.scalar_one_or_none()
    
    async def get_by_animal(
        self,
        db: AsyncSession,
        animal_id: int,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[HealthRecord], int]:
        """
        Get all health records for a specific animal.
        
        Args:
            db: Database session
            animal_id: Animal ID
            skip: Number of records to skip (pagination)
            limit: Maximum number of records to return
        
        Returns:
            Tuple of (records list, total count)
        
        Example:
            >>> records, total = await repo.get_by_animal(db, animal_id=5)
            >>> print(f"Found {total} records, showing {len(records)}")
        """
        logger.debug(f"Fetching health records for animal_id={animal_id}, skip={skip}, limit={limit}")
        
        # Count query
        count_query = select(func.count(HealthRecord.id)).where(
            HealthRecord.animal_id == animal_id
        )
        total = await db.scalar(count_query) or 0
        
        # Data query
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            HealthRecord.animal_id == animal_id
        ).order_by(
            desc(HealthRecord.recorded_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        logger.info(f"Found {len(records)} health records (total: {total}) for animal_id={animal_id}")
        return records, total
    
    async def get_by_type(
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
        
        # Count
        count_query = select(func.count(HealthRecord.id)).where(
            HealthRecord.record_type == record_type
        )
        total = await db.scalar(count_query) or 0
        
        # Data
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            HealthRecord.record_type == record_type
        ).order_by(
            desc(HealthRecord.recorded_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        return records, total
    
    async def get_by_severity(
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
        
        # Count
        count_query = select(func.count(HealthRecord.id)).where(
            HealthRecord.severity == severity
        )
        total = await db.scalar(count_query) or 0
        
        # Data
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            HealthRecord.severity == severity
        ).order_by(
            desc(HealthRecord.recorded_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        return records, total
    
    async def get_unresolved(
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
            Get all active health issues that need follow-up
        """
        logger.debug(f"Fetching unresolved health records, animal_id={animal_id}")
        
        conditions = [HealthRecord.is_resolved == False]
        if animal_id is not None:
            conditions.append(HealthRecord.animal_id == animal_id)
        
        # Count
        count_query = select(func.count(HealthRecord.id)).where(and_(*conditions))
        total = await db.scalar(count_query) or 0
        
        # Data
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            and_(*conditions)
        ).order_by(
            desc(HealthRecord.severity),  # Critical first
            desc(HealthRecord.recorded_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        logger.info(f"Found {len(records)} unresolved health records (total: {total})")
        return records, total
    
    async def get_critical_unresolved(
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
            Get all critical health issues requiring immediate attention
        """
        logger.debug("Fetching critical unresolved health records")
        
        conditions = [
            HealthRecord.is_resolved == False,
            HealthRecord.severity == HealthRecordSeverity.CRITICAL
        ]
        
        # Count
        count_query = select(func.count(HealthRecord.id)).where(and_(*conditions))
        total = await db.scalar(count_query) or 0
        
        # Data
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            and_(*conditions)
        ).order_by(
            desc(HealthRecord.recorded_at)
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        logger.warning(f"Found {len(records)} critical unresolved health records")
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
            days_ahead: Number of days to look ahead (default: 7)
            skip: Pagination offset
            limit: Maximum records
        
        Returns:
            Tuple of (records list, total count)
        
        Use case:
            Get all checkups scheduled in the next N days
        """
        logger.debug(f"Fetching upcoming checkups (next {days_ahead} days)")
        
        today = date.today()
        future_date = date.today() + timedelta(days=days_ahead)
        
        conditions = [
            HealthRecord.next_checkup_date.isnot(None),
            HealthRecord.next_checkup_date >= today,
            HealthRecord.next_checkup_date <= future_date
        ]
        
        # Count
        count_query = select(func.count(HealthRecord.id)).where(and_(*conditions))
        total = await db.scalar(count_query) or 0
        
        # Data
        query = select(HealthRecord).options(
            selectinload(HealthRecord.animal)
        ).where(
            and_(*conditions)
        ).order_by(
            HealthRecord.next_checkup_date
        ).offset(skip).limit(limit)
        
        result = await db.execute(query)
        records = list(result.scalars().all())
        
        logger.info(f"Found {len(records)} upcoming checkups (total: {total})")
        return records, total
    
    # =========================================================================
    # UPDATE
    # =========================================================================
    
    async def update(
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
        
        Example:
            >>> updated = await repo.update(
            ...     db,
            ...     record_id=10,
            ...     is_resolved=True,
            ...     resolved_at=datetime.utcnow()
            ... )
        """
        logger.debug(f"Updating health record: id={record_id}, fields={list(kwargs.keys())}")
        
        record = await self.get_by_id(db, record_id)
        if not record:
            logger.warning(f"Health record not found: id={record_id}")
            return None
        
        # Update fields
        for key, value in kwargs.items():
            if hasattr(record, key):
                setattr(record, key, value)
        
        await db.commit()
        await db.refresh(record)
        
        logger.info(f"Health record updated: id={record_id}")
        return record
    
    async def mark_resolved(
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
        if resolved_at is None:
            resolved_at = datetime.utcnow()
        
        logger.info(f"Marking health record as resolved: id={record_id}")
        
        return await self.update(
            db,
            record_id,
            is_resolved=True,
            resolved_at=resolved_at
        )
    
    # =========================================================================
    # DELETE
    # =========================================================================
    
    async def delete(
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
        logger.debug(f"Deleting health record: id={record_id}")
        
        record = await self.get_by_id(db, record_id)
        if not record:
            logger.warning(f"Health record not found: id={record_id}")
            return False
        
        await db.delete(record)
        await db.commit()
        
        logger.info(f"Health record deleted: id={record_id}")
        return True
    
    # =========================================================================
    # STATISTICS
    # =========================================================================
    
    async def get_statistics(
        self,
        db: AsyncSession,
        animal_id: Optional[int] = None
    ) -> dict:
        """
        Get health record statistics.
        
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
        """
        logger.debug(f"Calculating health record statistics, animal_id={animal_id}")
        
        base_conditions = []
        if animal_id is not None:
            base_conditions.append(HealthRecord.animal_id == animal_id)
        
        # Total records
        total_query = select(func.count(HealthRecord.id))
        if base_conditions:
            total_query = total_query.where(and_(*base_conditions))
        total = await db.scalar(total_query) or 0
        
        # By type
        type_query = select(
            HealthRecord.record_type,
            func.count(HealthRecord.id).label('count')
        ).group_by(HealthRecord.record_type)
        if base_conditions:
            type_query = type_query.where(and_(*base_conditions))
        
        type_result = await db.execute(type_query)
        by_type = {row.record_type.value: row.count for row in type_result.all()}
        
        # By severity
        severity_query = select(
            HealthRecord.severity,
            func.count(HealthRecord.id).label('count')
        ).group_by(HealthRecord.severity)
        if base_conditions:
            severity_query = severity_query.where(and_(*base_conditions))
        
        severity_result = await db.execute(severity_query)
        by_severity = {row.severity.value: row.count for row in severity_result.all()}
        
        # Unresolved
        unresolved_conditions = base_conditions + [HealthRecord.is_resolved == False]
        unresolved_query = select(func.count(HealthRecord.id)).where(and_(*unresolved_conditions))
        unresolved = await db.scalar(unresolved_query) or 0
        
        # Critical unresolved
        critical_conditions = unresolved_conditions + [HealthRecord.severity == HealthRecordSeverity.CRITICAL]
        critical_query = select(func.count(HealthRecord.id)).where(and_(*critical_conditions))
        critical = await db.scalar(critical_query) or 0
        
        stats = {
            "total_records": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "unresolved": unresolved,
            "critical_unresolved": critical,
        }
        
        logger.info(f"Health record statistics calculated: {stats}")
        return stats