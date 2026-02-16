"""
Report API Endpoints - Taurus Vision

REST API endpoints for PDF report generation.
Streams PDF files directly to client for download.

Author: Taurus Vision Team
Date: 2026-02-16
"""

from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from io import BytesIO

from app.core.database import get_db
from app.core.logging_config import get_logger
from app.services.report_service import ReportService
from app.schemas.report import (
    AnimalReportRequest,
    FarmReportRequest,
    HealthReportRequest,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/reports", tags=["Reports"])

# Initialize service
report_service = ReportService()


# =============================================================================
# ANIMAL REPORT
# =============================================================================

@router.post(
    "/generate/animal/{animal_id}",
    summary="Generate animal report",
    description="""
    Generate comprehensive PDF report for a specific animal.
    
    The report includes:
    - Basic animal information
    - Weight history (table + trend analysis)
    - Detection timeline (last 30 days)
    - Health summary
    - Notes
    
    Returns a PDF file ready for download.
    
    Use cases:
    - Individual animal tracking
    - Veterinary records
    - Sales documentation
    - Health monitoring
    """,
    responses={
        200: {
            "description": "PDF report generated successfully",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        404: {"description": "Animal not found"},
        500: {"description": "Report generation failed"}
    }
)
async def generate_animal_report(
    animal_id: int,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Generate and download animal report PDF.
    
    Args:
        animal_id: Animal ID
        db: Database session
    
    Returns:
        StreamingResponse with PDF file
    
    The PDF is streamed directly to the client with proper headers
    for browser download. Filename format: animal_{id}_report_{date}.pdf
    
    Performance note: Report generation typically takes 1-3 seconds
    depending on the amount of data (weight measurements, detections).
    """
    logger.info(f"API call: POST /reports/generate/animal/{animal_id}")
    
    try:
        # Generate PDF
        pdf_bytes = await report_service.generate_animal_report(db, animal_id)
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        filename = f"animal_{animal_id}_report_{timestamp}.pdf"
        
        logger.info(
            f"Animal report generated successfully",
            extra={
                "extra_data": {
                    "animal_id": animal_id,
                    "file_size": len(pdf_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes))
            }
        )
        
    except ValueError as e:
        # Animal not found
        logger.warning(f"Animal not found: {animal_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error generating animal report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate animal report"
        )


# =============================================================================
# FARM REPORT
# =============================================================================

@router.post(
    "/generate/farm",
    summary="Generate farm report",
    description="""
    Generate comprehensive farm-wide summary report.
    
    Report types:
    - **summary**: High-level statistics and trends (recommended)
    - **detailed**: Comprehensive data with all animals
    - **health**: Health-focused with alerts and risk assessment
    
    The report includes:
    - Executive summary (animals, detections, average weight)
    - Animal statistics (by status, by species)
    - Detection summary
    - Weight trends
    - Top performers (most detected, highest weight gain)
    
    Returns a PDF file ready for download.
    
    Use cases:
    - Weekly/monthly farm reports
    - Management presentations
    - Performance tracking
    - Stakeholder updates
    """,
    responses={
        200: {
            "description": "PDF report generated successfully",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Report generation failed"}
    }
)
async def generate_farm_report(
    request: FarmReportRequest,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Generate and download farm summary report PDF.
    
    Args:
        request: Report request parameters
        db: Database session
    
    Returns:
        StreamingResponse with PDF file
    
    Date range recommendation:
    - Weekly reports: 7 days
    - Monthly reports: 30 days
    - Quarterly reports: 90 days
    - Annual reports: 365 days
    
    Performance note: Larger date ranges take longer to process.
    Consider using summary report type for ranges >90 days.
    """
    logger.info(
        f"API call: POST /reports/generate/farm",
        extra={
            "extra_data": {
                "date_from": request.date_from.isoformat(),
                "date_to": request.date_to.isoformat(),
                "report_type": request.report_type
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
        # Generate PDF
        pdf_bytes = await report_service.generate_farm_report(
            db,
            date_from=request.date_from,
            date_to=request.date_to,
            report_type=request.report_type
        )
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        filename = f"farm_{request.report_type}_report_{timestamp}.pdf"
        
        logger.info(
            f"Farm report generated successfully",
            extra={
                "extra_data": {
                    "report_type": request.report_type,
                    "file_size": len(pdf_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating farm report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate farm report"
        )


# =============================================================================
# HEALTH REPORT
# =============================================================================

@router.post(
    "/generate/health",
    summary="Generate health report",
    description="""
    Generate health-focused report with alerts and risk assessment.
    
    The report includes:
    - Health overview (monitored animals, active alerts)
    - Weight loss alerts (>5% loss in 7 days)
    - No detection alerts (not seen in 7+ days)
    - Risk assessment (overall health score)
    - Recommendations for action
    
    Parameters:
    - animal_ids: Optional list of specific animals (omit for all active animals)
    
    Returns a PDF file ready for download.
    
    Use cases:
    - Daily health checks
    - Veterinary consultations
    - Proactive health management
    - Alert documentation
    """,
    responses={
        200: {
            "description": "PDF report generated successfully",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {"description": "Invalid parameters"},
        500: {"description": "Report generation failed"}
    }
)
async def generate_health_report(
    request: HealthReportRequest,
    db: AsyncSession = Depends(get_db)
) -> StreamingResponse:
    """
    Generate and download health report PDF.
    
    Args:
        request: Report request parameters
        db: Database session
    
    Returns:
        StreamingResponse with PDF file
    
    This report is designed for daily review by farm managers
    and veterinarians. It highlights issues that require attention:
    
    Critical alerts (immediate action):
    - Animals never detected by system
    - Severe weight loss (>10% in 7 days)
    
    Warning alerts (monitor closely):
    - No recent detection (7+ days)
    - Moderate weight loss (5-10% in 7 days)
    
    Best practice: Generate this report daily and review all
    critical alerts immediately.
    """
    logger.info(
        f"API call: POST /reports/generate/health",
        extra={
            "extra_data": {
                "animal_ids": request.animal_ids
            }
        }
    )
    
    try:
        # Generate PDF
        pdf_bytes = await report_service.generate_health_report(
            db,
            animal_ids=request.animal_ids
        )
        
        # Create filename
        timestamp = datetime.utcnow().strftime('%Y%m%d')
        filename = f"health_report_{timestamp}.pdf"
        
        logger.info(
            f"Health report generated successfully",
            extra={
                "extra_data": {
                    "file_size": len(pdf_bytes),
                    "filename": filename
                }
            }
        )
        
        # Return as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Length": str(len(pdf_bytes))
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating health report: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate health report"
        )


# =============================================================================
# REPORT PREVIEW (Optional - for future)
# =============================================================================

@router.get(
    "/preview/{report_type}",
    summary="Preview report metadata",
    description="""
    Get metadata about what would be included in a report
    without actually generating it.
    
    Useful for:
    - Estimating report size before generation
    - Checking data availability
    - UI progress indicators
    
    **Note:** This endpoint is optional and not yet fully implemented.
    """
)
async def preview_report(
    report_type: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Preview report metadata.
    
    This is a placeholder for future functionality to preview
    report contents before generating the full PDF.
    """
    logger.info(f"API call: GET /reports/preview/{report_type}")
    
    return {
        "message": "Report preview not yet implemented",
        "report_type": report_type,
        "status": "coming_soon"
    }
