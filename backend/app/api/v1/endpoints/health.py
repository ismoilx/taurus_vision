"""
Health Record API Endpoints - Taurus Vision

REST API endpoints for health records management.
Comprehensive CRUD operations plus analytics and reporting.

Author: Taurus Vision Team  
Date: 2026-02-16
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.services.health_record_service import HealthRecordService
from app.models.health_record import HealthRecordType, HealthRecordSeverity
from app.schemas.health_record import (
    HealthRecordCreate,
    HealthRecordUpdate,
    HealthRecordResponse,
    HealthRecordListResponse,
    HealthStatistics,
    HealthSummary,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/health", tags=["Health Records"])

# Initialize service
health_service = HealthRecordService()


# =============================================================================
# CREATE HEALTH RECORD
# =============================================================================

@router.post(
    "/animals/{animal_id}/records",
    response_model=HealthRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create health record",
    description="Create a new health record for an animal with full validation"
)
async def create_health_record(
    animal_id: int = Path(..., gt=0),
    record: HealthRecordCreate = ...,
    db: AsyncSession = Depends(get_db)
) -> HealthRecordResponse:
    """Create health record for an animal."""
    logger.info(f"API call: POST /health/animals/{animal_id}/records")
    
    try:
        created = await health_service.create_health_record(
            db,
            animal_id=animal_id,
            record_type=HealthRecordType(record.record_type),
            severity=HealthRecordSeverity(record.severity),
            diagnosis=record.diagnosis,
            symptoms=record.symptoms,
            treatment=record.treatment,
            medication=record.medication,
            dosage=record.dosage,
            veterinarian=record.veterinarian,
            clinic_name=record.clinic_name,
            cost=record.cost,
            notes=record.notes,
            recorded_at=record.recorded_at,
            next_checkup_date=record.next_checkup_date
        )
        
        return HealthRecordResponse.model_validate(created)
        
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating health record: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create health record")


@router.get("/records/{record_id}", response_model=HealthRecordResponse)
async def get_health_record(
    record_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordResponse:
    """Get health record by ID."""
    record = await health_service.get_record_by_id(db, record_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Health record {record_id} not found")
    return HealthRecordResponse.model_validate(record)


@router.get("/animals/{animal_id}/records", response_model=HealthRecordListResponse)
async def get_animal_health_records(
    animal_id: int = Path(..., gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordListResponse:
    """Get all health records for an animal."""
    try:
        records, total = await health_service.get_animal_records(db, animal_id, skip, limit)
        return HealthRecordListResponse(
            records=[HealthRecordResponse.model_validate(r) for r in records],
            total=total, skip=skip, limit=limit
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.patch("/records/{record_id}", response_model=HealthRecordResponse)
async def update_health_record(
    record_id: int = Path(..., gt=0),
    update: HealthRecordUpdate = ...,
    db: AsyncSession = Depends(get_db)
) -> HealthRecordResponse:
    """Update health record."""
    try:
        update_data = update.model_dump(exclude_unset=True)
        if 'record_type' in update_data:
            update_data['record_type'] = HealthRecordType(update_data['record_type'])
        if 'severity' in update_data:
            update_data['severity'] = HealthRecordSeverity(update_data['severity'])
        
        updated = await health_service.update_health_record(db, record_id, **update_data)
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Health record {record_id} not found")
        return HealthRecordResponse.model_validate(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/records/{record_id}/resolve", response_model=HealthRecordResponse)
async def resolve_health_record(
    record_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordResponse:
    """Mark health record as resolved."""
    resolved = await health_service.resolve_health_record(db, record_id)
    if not resolved:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Health record {record_id} not found")
    return HealthRecordResponse.model_validate(resolved)


@router.delete("/records/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_health_record(
    record_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db)
) -> None:
    """Delete health record."""
    deleted = await health_service.delete_health_record(db, record_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Health record {record_id} not found")


@router.get("/unresolved", response_model=HealthRecordListResponse)
async def get_unresolved_records(
    animal_id: Optional[int] = Query(None, gt=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordListResponse:
    """Get unresolved health records."""
    records, total = await health_service.get_unresolved_records(db, animal_id, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total, skip=skip, limit=limit
    )


@router.get("/critical", response_model=HealthRecordListResponse)
async def get_critical_records(
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordListResponse:
    """Get critical unresolved health records."""
    records, total = await health_service.get_critical_records(db, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total, skip=skip, limit=limit
    )


@router.get("/upcoming-checkups", response_model=HealthRecordListResponse)
async def get_upcoming_checkups(
    days_ahead: int = Query(7, ge=1, le=90),
    skip: int = Query(0, ge=0),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
) -> HealthRecordListResponse:
    """Get upcoming scheduled checkups."""
    records, total = await health_service.get_upcoming_checkups(db, days_ahead, skip, limit)
    return HealthRecordListResponse(
        records=[HealthRecordResponse.model_validate(r) for r in records],
        total=total, skip=skip, limit=limit
    )


@router.get("/animals/{animal_id}/summary", response_model=HealthSummary)
async def get_health_summary(
    animal_id: int = Path(..., gt=0),
    db: AsyncSession = Depends(get_db)
) -> HealthSummary:
    """Get comprehensive health summary for an animal."""
    try:
        summary = await health_service.get_health_summary(db, animal_id)
        return HealthSummary(**summary)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/statistics", response_model=HealthStatistics)
async def get_health_statistics(
    animal_id: Optional[int] = Query(None, gt=0),
    db: AsyncSession = Depends(get_db)
) -> HealthStatistics:
    """Get health statistics."""
    stats = await health_service.get_health_statistics(db, animal_id)
    return HealthStatistics(**stats)
