"""
Export API Endpoints - Taurus Vision

REST API endpoints for data export (CSV, Excel).
Streams files directly to client for download.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.services.export_service import ExportService
from app.schemas.export import (
    AnimalsExportRequest,
    DetectionsExportRequest,
    WeightsExportRequest,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/export", tags=["Export"])

# Initialize service
export_service = ExportService()


# =============================================================================
# ANIMALS EXPORT (CSV)
# =============================================================================

@router.post(
    "/animals/csv",
    summary="Export animals to CSV",
    description="""
    Export animals data to CSV format with optional filters.
    
    Filters:
    - status: Filter by status (active/sold/deceased)
    - species: Filter by species (cattle/sheep/goat)
    - gender: Filter by gender (male/female)
    - tag_id: Filter by tag ID (partial match, case-insensitive)
    
    CSV columns:
    - id, tag_id, species, gender, status
    - breed, acquisition_date
    - total_detections, last_detected_at
    - notes
    
    Returns a CSV file ready for download.
    
    Use cases:
    - Spreadsheet analysis
    - Data backup
    - External system integration
    - Sharing with stakeholders
    """,
    responses={
        200: {
            "description": "CSV file generated successfully",
            "content": {
                "text/csv": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Export failed"}
    }
)
async def export_animals_csv(
    request: AnimalsExportRequest,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export animals to CSV file.
    
    Args:
        request: Export request with filters
        db: Database session
    
    Returns:
        StreamingResponse with CSV file
    
    The CSV uses UTF-8 encoding and includes headers.
    Compatible with Excel, Google Sheets, and pandas.
    
    Performance note: Large datasets (1000+ animals) may take
    a few seconds to generate. Consider pagination for very large farms.
    """
    logger.info(
        f"API call: POST /export/animals/csv",
        extra={
            "extra_data": {
                "filters": request.model_dump()
            }
        }
    )
    
    try:
        # Generate CSV
        csv_bytes = await export_service.export_animals_csv(
            db,
            filters=request.model_dump(exclude_none=True)
        )
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"animals_{timestamp}.csv"
        
        logger.info(
            f"Animals CSV exported successfully",
            extra={
                "extra_data": {
                    "file_size": len(csv_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(csv_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting animals CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export animals CSV"
        )


# =============================================================================
# DETECTIONS EXPORT (CSV)
# =============================================================================

@router.post(
    "/detections/csv",
    summary="Export detections to CSV",
    description="""
    Export detection logs to CSV format for a date range.
    
    Parameters:
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - animal_id: Optional animal filter
    
    CSV columns:
    - id, animal_id, animal_tag_id
    - camera_id, detected_at
    - confidence_score
    - bbox_x, bbox_y, bbox_width, bbox_height
    
    Returns a CSV file ready for download.
    
    Use cases:
    - Activity analysis
    - Detection validation
    - Camera performance analysis
    - Audit trails
    
    Performance note: Large date ranges (>90 days) may produce
    large files. Consider splitting into smaller ranges.
    """,
    responses={
        200: {
            "description": "CSV file generated successfully",
            "content": {
                "text/csv": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {"description": "Invalid date range"},
        500: {"description": "Export failed"}
    }
)
async def export_detections_csv(
    request: DetectionsExportRequest,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export detections to CSV file.
    
    Args:
        request: Export request with date range and optional animal filter
        db: Database session
    
    Returns:
        StreamingResponse with CSV file
    
    The CSV is ordered by detected_at (newest first).
    Confidence scores are rounded to 4 decimal places.
    
    Warning: Very large date ranges may produce files >100MB.
    Consider using pagination or smaller date ranges for better performance.
    """
    logger.info(
        f"API call: POST /export/detections/csv",
        extra={
            "extra_data": {
                "date_from": request.date_from.isoformat(),
                "date_to": request.date_to.isoformat(),
                "animal_id": request.animal_id
            }
        }
    )
    
    # Validate date range
    days_diff = (request.date_to - request.date_from).days
    if days_diff > 365:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 365 days"
        )
    
    try:
        # Generate CSV
        csv_bytes = await export_service.export_detections_csv(
            db,
            date_from=request.date_from,
            date_to=request.date_to,
            animal_id=request.animal_id
        )
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        animal_suffix = f"_animal{request.animal_id}" if request.animal_id else ""
        filename = f"detections_{request.date_from}_{request.date_to}{animal_suffix}_{timestamp}.csv"
        
        logger.info(
            f"Detections CSV exported successfully",
            extra={
                "extra_data": {
                    "file_size": len(csv_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(csv_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting detections CSV: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export detections CSV"
        )


# =============================================================================
# WEIGHTS EXPORT (EXCEL)
# =============================================================================

@router.post(
    "/weights/excel",
    summary="Export weights to Excel",
    description="""
    Export weight measurements to Excel format (multi-sheet).
    
    Parameters:
    - animal_ids: Optional list of specific animals (omit for all active animals)
    
    Excel structure:
    - **Sheet 1 (Summary)**: Overview of all animals
      - Tag ID, Species, Total Measurements
      - Latest Weight, Average, Min, Max
    - **Sheet 2+ (Animal_{tag})**: Detailed weight history per animal
      - Date, Time, Weight (kg), Confidence, Camera
    
    Features:
    - Multiple sheets (one per animal + summary)
    - Formatted headers
    - Number formatting
    - Date formatting
    - Easy to open in Excel/Google Sheets
    
    Returns an Excel (.xlsx) file ready for download.
    
    Use cases:
    - Weight trend analysis
    - Growth tracking
    - Data visualization
    - Reports for stakeholders
    """,
    responses={
        200: {
            "description": "Excel file generated successfully",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Export failed"}
    }
)
async def export_weights_excel(
    request: WeightsExportRequest,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export weights to Excel file (multi-sheet).
    
    Args:
        request: Export request with optional animal ID filter
        db: Database session
    
    Returns:
        StreamingResponse with Excel file
    
    The Excel file uses the modern .xlsx format (Office 2007+).
    Each animal gets its own sheet with detailed weight history.
    
    Performance note: Large numbers of animals or measurements
    may take longer to generate. Typical generation time: 2-5 seconds
    for 50 animals with 100 measurements each.
    """
    logger.info(
        f"API call: POST /export/weights/excel",
        extra={
            "extra_data": {
                "animal_ids": request.animal_ids
            }
        }
    )
    
    try:
        # Generate Excel
        excel_bytes = await export_service.export_weights_excel(
            db,
            animal_ids=request.animal_ids
        )
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"weights_{timestamp}.xlsx"
        
        logger.info(
            f"Weights Excel exported successfully",
            extra={
                "extra_data": {
                    "file_size": len(excel_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting weights Excel: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export weights Excel"
        )


# =============================================================================
# ALL DATA EXPORT (EXCEL - COMPREHENSIVE)
# =============================================================================

@router.get(
    "/all/excel",
    summary="Export all farm data to Excel",
    description="""
    Export comprehensive farm data to multi-sheet Excel workbook.
    
    **This is a complete data export including:**
    - All animals (Sheet 1)
    - All detections - last 30 days (Sheet 2)
    - All weight measurements (Sheet 3)
    - Summary statistics (Sheet 4)
    
    **Use cases:**
    - Complete data backup
    - External analysis
    - Archival
    - Sharing with stakeholders
    
    **Warning:** This export can be large (10-100+ MB) for farms
    with extensive data. Consider using filtered exports for
    regular operations.
    
    Returns an Excel (.xlsx) file ready for download.
    """,
    responses={
        200: {
            "description": "Excel file generated successfully",
            "content": {
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        500: {"description": "Export failed"}
    }
)
async def export_all_data_excel(
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Export all farm data to comprehensive Excel workbook.
    
    Args:
        db: Database session
    
    Returns:
        StreamingResponse with Excel file
    
    This is a heavy operation that exports all available data.
    It includes limits to prevent excessive file sizes:
    - Detections: Last 30 days (max 10,000 records)
    - Weights: All measurements (max 10,000 records)
    
    For complete historical data, consider using database backups
    or periodic exports instead.
    
    Performance note: Generation time varies based on data volume.
    Typical: 10-30 seconds for a medium-sized farm (100 animals,
    10,000 detections).
    """
    logger.info("API call: GET /export/all/excel")
    
    try:
        # Generate Excel
        excel_bytes = await export_service.export_all_data_excel(db)
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"farm_data_complete_{timestamp}.xlsx"
        
        logger.info(
            f"Complete data Excel exported successfully",
            extra={
                "extra_data": {
                    "file_size": len(excel_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(excel_bytes),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(excel_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error exporting all data Excel: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export complete data Excel"
        )


# =============================================================================
# EXPORT TEMPLATES (Optional - for future)
# =============================================================================

@router.get(
    "/templates",
    summary="Get available export templates",
    description="""
    Get list of available export templates and formats.
    
    Returns information about:
    - Available export types
    - Supported formats
    - Required parameters
    - Example requests
    
    **Note:** This endpoint is informational only.
    """
)
async def get_export_templates() -> dict:
    """
    Get available export templates.
    
    This is an informational endpoint that describes
    available export options without actually generating files.
    """
    logger.info("API call: GET /export/templates")
    
    return {
        "templates": [
            {
                "name": "Animals CSV",
                "endpoint": "/api/v1/export/animals/csv",
                "format": "CSV",
                "description": "Export animals with optional filters",
                "example": {
                    "status": "active",
                    "species": "cattle"
                }
            },
            {
                "name": "Detections CSV",
                "endpoint": "/api/v1/export/detections/csv",
                "format": "CSV",
                "description": "Export detections for date range",
                "example": {
                    "date_from": "2026-02-01",
                    "date_to": "2026-02-16"
                }
            },
            {
                "name": "Weights Excel",
                "endpoint": "/api/v1/export/weights/excel",
                "format": "Excel (.xlsx)",
                "description": "Export weight measurements (multi-sheet)",
                "example": {
                    "animal_ids": [1, 2, 3]
                }
            },
            {
                "name": "Complete Data Excel",
                "endpoint": "/api/v1/export/all/excel",
                "format": "Excel (.xlsx)",
                "description": "Export all farm data (comprehensive)",
                "example": {}
            }
        ]
    }
