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
from pydantic import BaseModel as _PydanticBase

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.core.logging_config import get_logger
from app.services.report_service import ReportService
from app.schemas.report import (
    AnimalReportRequest,
    FarmReportRequest,
    HealthReportRequest,
)

logger = get_logger(__name__)

# Create router
router = APIRouter(prefix="/reports", tags=["Reports"], dependencies=[Depends(get_current_active_user)])

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
# REPORT PREVIEW — Hisobot yaratishdan oldin ma'lumot tekshiruvi
# =============================================================================

_VALID_REPORT_TYPES = {"animal", "farm", "health"}


@router.get(
    "/preview/{report_type}",
    summary="Hisobot oldindan ko'rish metadatasi",
    description=(
        "Hisobot generatsiya qilmasdan avval ma'lumot mavjudligini va hajmini tekshiradi. "
        "Frontend da 'Hisobot yaratish' tugmasini faollashtirish/o'chirish uchun ishlatiladi. "
        "\n\n**report_type:** animal | farm | health"
        "\n\n**animal** uchun `animal_id` query parametri talab qilinadi."
    ),
)
async def preview_report(
    report_type: str,
    animal_id:   Optional[int] = None,
    days:        int           = 30,
    db:          AsyncSession  = Depends(get_db),
    current_user = Depends(get_current_active_user),
) -> dict:
    """
    Hisobot metadatasi — generatsiya qilmasdan ma'lumot tekshiruvi.

    Qaytariladi:
        - available: Hisobot yaratilishi mumkinmi
        - reason:    Agar yo'q bo'lsa — sababı
        - stats:     Ma'lumot ko'rsatkichlari (qancha yozuv bor)
        - estimated_pages: Taxminiy sahifalar soni
        - date_range: Ma'lumot oraliq sanasi
        - report_type: So'ralgan tur

    Raises:
        400: Noto'g'ri report_type
        400: animal hisoboti uchun animal_id yo'q
        404: Jonivor topilmadi
    """
    from datetime import timedelta, timezone
    from sqlalchemy import select, func, and_
    from app.models.animal import Animal, AnimalStatus
    from app.models.detection import Detection
    from app.models.weight_measurement import WeightMeasurement
    from app.models.alert import Alert, AlertStatus
    from app.models.health_record import HealthRecord
    from app.models.health_prediction import HealthPrediction
    from app.models.adi_log import ADILog

    logger.info(f"Report preview: type={report_type}, animal_id={animal_id}, days={days}")

    # ── Validatsiya ───────────────────────────────────────────────────────────
    if report_type not in _VALID_REPORT_TYPES:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=400,
            detail=f"Noto'g'ri report_type: '{report_type}'. "
                   f"To'g'ri qiymatlar: {sorted(_VALID_REPORT_TYPES)}",
        )

    date_from = datetime.now(timezone.utc) - timedelta(days=days)
    date_to   = datetime.now(timezone.utc)

    # ── ANIMAL REPORT ─────────────────────────────────────────────────────────
    if report_type == "animal":
        if not animal_id:
            from fastapi import HTTPException
            raise HTTPException(
                status_code=400,
                detail="animal hisoboti uchun animal_id parametri talab qilinadi.",
            )

        animal_result = await db.execute(
            select(Animal).where(Animal.id == animal_id)
        )
        animal = animal_result.scalar_one_or_none()
        if not animal:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail=f"Jonivor #{animal_id} topilmadi")

        # Ma'lumot soni
        det_count = await db.scalar(
            select(func.count(Detection.id)).where(
                Detection.animal_id  == animal_id,
                Detection.timestamp  >= date_from,
            )
        ) or 0

        weight_count = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id  == animal_id,
                WeightMeasurement.measured_at >= date_from,
            )
        ) or 0

        health_count = await db.scalar(
            select(func.count(HealthRecord.id)).where(
                HealthRecord.animal_id == animal_id,
            )
        ) or 0

        adi_count = await db.scalar(
            select(func.count(ADILog.id)).where(
                ADILog.animal_id == animal_id,
                ADILog.date      >= date_from.date(),
            )
        ) or 0

        has_data    = det_count > 0 or weight_count > 0
        est_pages   = 2 + (1 if weight_count > 0 else 0) + (1 if det_count > 0 else 0)

        return {
            "available":       has_data or health_count > 0,
            "reason":          None if has_data else "Bu jonivor uchun ma'lumot topilmadi",
            "report_type":     report_type,
            "animal_id":       animal_id,
            "animal_tag":      animal.tag_id,
            "animal_name":     animal.name or animal.tag_id,
            "date_range": {
                "from":  date_from.strftime("%Y-%m-%d"),
                "to":    date_to.strftime("%Y-%m-%d"),
                "days":  days,
            },
            "stats": {
                "detections":    det_count,
                "weight_records": weight_count,
                "health_records": health_count,
                "adi_records":    adi_count,
            },
            "estimated_pages": est_pages,
            "sections": [
                {"name": "Asosiy ma'lumotlar",    "available": True},
                {"name": "Og'irlik tarixi",        "available": weight_count > 0},
                {"name": "Deteksiya statistikasi", "available": det_count > 0},
                {"name": "Sog'liq yozuvlari",      "available": health_count > 0},
            ],
        }

    # ── FARM REPORT ───────────────────────────────────────────────────────────
    elif report_type == "farm":
        total_animals = await db.scalar(
            select(func.count(Animal.id)).where(
                Animal.status == AnimalStatus.ACTIVE
            )
        ) or 0

        recent_detections = await db.scalar(
            select(func.count(Detection.id)).where(
                Detection.timestamp >= date_from
            )
        ) or 0

        open_alerts = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.status == AlertStatus.OPEN
            )
        ) or 0

        weight_records = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.measured_at >= date_from
            )
        ) or 0

        has_data  = total_animals > 0
        est_pages = 3 + (1 if recent_detections > 0 else 0) + (1 if open_alerts > 0 else 0)

        return {
            "available":   has_data,
            "reason":      None if has_data else "Fermada hali jonivorlar yo'q",
            "report_type": report_type,
            "date_range": {
                "from": date_from.strftime("%Y-%m-%d"),
                "to":   date_to.strftime("%Y-%m-%d"),
                "days": days,
            },
            "stats": {
                "active_animals":    total_animals,
                "recent_detections": recent_detections,
                "open_alerts":       open_alerts,
                "weight_records":    weight_records,
            },
            "estimated_pages": est_pages,
            "sections": [
                {"name": "Ferma xulosasi",         "available": True},
                {"name": "Jonivorlar ro'yxati",    "available": total_animals > 0},
                {"name": "Deteksiya statistikasi", "available": recent_detections > 0},
                {"name": "Aktiv ogohlantirishlar",  "available": open_alerts > 0},
                {"name": "Og'irlik trendlari",     "available": weight_records > 0},
            ],
        }

    # ── HEALTH REPORT ─────────────────────────────────────────────────────────
    else:  # health
        total_animals = await db.scalar(
            select(func.count(Animal.id)).where(Animal.status == AnimalStatus.ACTIVE)
        ) or 0

        critical_alerts = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.status   == AlertStatus.OPEN,
                Alert.severity == "critical",
            )
        ) or 0

        health_records = await db.scalar(
            select(func.count(HealthRecord.id)).where(
                HealthRecord.created_at >= date_from
            )
        ) or 0

        predictions = await db.scalar(
            select(func.count(HealthPrediction.id)).where(
                HealthPrediction.created_at >= date_from
            )
        ) or 0

        has_data  = total_animals > 0
        est_pages = 3 + (1 if critical_alerts > 0 else 0) + (1 if predictions > 0 else 0)

        return {
            "available":   has_data,
            "reason":      None if has_data else "Fermada hali jonivorlar yo'q",
            "report_type": report_type,
            "date_range": {
                "from": date_from.strftime("%Y-%m-%d"),
                "to":   date_to.strftime("%Y-%m-%d"),
                "days": days,
            },
            "stats": {
                "total_animals":   total_animals,
                "critical_alerts": critical_alerts,
                "health_records":  health_records,
                "predictions":     predictions,
            },
            "estimated_pages": est_pages,
            "sections": [
                {"name": "Sog'liq xulosasi",     "available": True},
                {"name": "Kritik holat hayvonlar","available": critical_alerts > 0},
                {"name": "Veterinar yozuvlari",  "available": health_records > 0},
                {"name": "ML bashoratlari",       "available": predictions > 0},
                {"name": "Tavsiyalar",            "available": True},
            ],
        }

# =============================================================================
# SHORT PATH ALIASES — tests use /reports/animal/{id}, /reports/farm, etc.
# =============================================================================

@router.post(
    "/animal/{animal_id}",
    summary="Generate animal report (short alias)",
)
async def generate_animal_report_alias(
    animal_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Short alias for /generate/animal/{animal_id}."""
    return await generate_animal_report(animal_id=animal_id, db=db)


class _FarmReportBody(_PydanticBase):
    format: Optional[str] = None


@router.post(
    "/farm",
    summary="Generate farm report (short alias)",
)
async def generate_farm_report_alias(
    body: Optional[_FarmReportBody] = None,
    db: AsyncSession = Depends(get_db),
):
    """Short alias for /generate/farm."""
    return await generate_farm_report(db=db)


@router.post(
    "/health",
    summary="Generate health report (short alias)",
)
async def generate_health_report_alias(
    db: AsyncSession = Depends(get_db),
):
    """Short alias for /generate/health."""
    return await generate_health_report(db=db)