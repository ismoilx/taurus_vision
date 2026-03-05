"""
Taurus Vision — Scale (Tarozi) API Endpoints

ROUTES:
    GET    /scales                         — Tarozlar ro'yxati
    POST   /scales                         — Yangi tarozi (ADMIN)
    GET    /scales/{id}                    — Tarozi tafsiloti
    PUT    /scales/{id}                    — Tarozi yangilash (ADMIN)
    DELETE /scales/{id}                    — Tarozi o'chirish (ADMIN)

    POST   /scales/weights/manual          — Qo'lda vazn kiritish (MANAGER)
    POST   /scales/{id}/webhook            — Tarozi webhook (token auth)
    POST   /scales/weights/{id}/actual     — AI o'lchoviga haqiqiy vazn biriktirish
    POST   /scales/{id}/calibrate          — Kalibratsiya hisoblash (MANAGER)
    GET    /scales/comparison              — AI vs haqiqiy taqqoslash hisoboti
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Path, Body
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager, CurrentAdmin
from app.services.scale_service import ScaleService
from app.schemas.scale import (
    ScaleCreate,
    ScaleUpdate,
    ScaleResponse,
    ScaleListResponse,
    ManualWeightCreate,
    ScaleWebhookPayload,
    CalibrationDataPoint,
    CalibrationResponse,
    WeightComparisonResponse,
    WeightMeasurementExtended,
)

router = APIRouter(prefix="/scales", tags=["Scales"])


def _svc(db: AsyncSession = Depends(get_db)) -> ScaleService:
    return ScaleService(db)


# =============================================================================
# TAROZI CRUD
# =============================================================================

@router.get("", response_model=ScaleListResponse)
async def list_scales(
    active_only:  bool = Query(False),
    current_user: CurrentUser = None,
    svc:          ScaleService = Depends(_svc),
):
    """Barcha tarozlar ro'yxati."""
    return await svc.list_scales(active_only=active_only)


@router.post("", response_model=ScaleResponse, status_code=201)
async def create_scale(
    data:         ScaleCreate,
    current_user: CurrentAdmin = None,
    svc:          ScaleService = Depends(_svc),
):
    """Yangi tarozi qo'shish — faqat ADMIN."""
    return await svc.create_scale(data)


@router.get("/comparison", response_model=WeightComparisonResponse)
async def get_comparison_report(
    limit:        int = Query(50, ge=1, le=200),
    current_user: CurrentUser = None,
    svc:          ScaleService = Depends(_svc),
):
    """AI taxmin vs haqiqiy vazn taqqoslash hisoboti."""
    return await svc.get_comparison_report(limit=limit)


@router.get("/{scale_id}", response_model=ScaleResponse)
async def get_scale(
    scale_id:     int = Path(..., gt=0),
    current_user: CurrentUser = None,
    svc:          ScaleService = Depends(_svc),
):
    """Tarozi tafsiloti."""
    return await svc.get_scale(scale_id)


@router.put("/{scale_id}", response_model=ScaleResponse)
async def update_scale(
    scale_id:     int = Path(..., gt=0),
    data:         ScaleUpdate = Body(...),
    current_user: CurrentAdmin = None,
    svc:          ScaleService = Depends(_svc),
):
    """Tarozi ma'lumotlarini yangilash — faqat ADMIN."""
    return await svc.update_scale(scale_id, data)


@router.delete("/{scale_id}", status_code=204)
async def delete_scale(
    scale_id:     int = Path(..., gt=0),
    current_user: CurrentAdmin = None,
    svc:          ScaleService = Depends(_svc),
):
    """Tarozi o'chirish — faqat ADMIN."""
    await svc.delete_scale(scale_id)


# =============================================================================
# VAZN O'LCHOVLARI
# =============================================================================

@router.post("/weights/manual", response_model=WeightMeasurementExtended, status_code=201)
async def record_manual_weight(
    data:         ManualWeightCreate,
    current_user: CurrentManager = None,
    svc:          ScaleService = Depends(_svc),
):
    """
    Foydalanuvchi tarozidan o'qib qo'lda kiritadigan vazn.

    Confidence: 1.0 (manual = to'liq ishonch).
    actual_weight_kg = estimated_weight_kg (bir xil).
    """
    return await svc.record_manual_weight(data)


@router.post("/{scale_id}/webhook", response_model=WeightMeasurementExtended, status_code=201)
async def scale_webhook(
    scale_id: int = Path(..., gt=0),
    payload:  ScaleWebhookPayload = Body(...),
    svc:      ScaleService = Depends(_svc),
):
    """
    Tarozi qurilmadan kelgan webhook (serial/api).

    Autentifikatsiya: JWT emas, api_token orqali.
    Tarozi o'zi ushbu endpointga POST yuboradi.
    """
    return await svc.process_scale_webhook(scale_id, payload)


@router.post("/weights/{measurement_id}/actual", response_model=WeightMeasurementExtended)
async def attach_actual_weight(
    measurement_id:   int   = Path(..., gt=0),
    actual_weight_kg: float = Body(..., embed=True, gt=0, le=2000),
    current_user:     CurrentManager = None,
    svc:              ScaleService = Depends(_svc),
):
    """
    Mavjud AI o'lchoviga haqiqiy tarozi vazni biriktirish.

    Bu kalibratsiya ma'lumoti to'plash uchun ishlatiladi.
    Jonivorni taroziga tortib, keyin shu o'lchovga natijani biriktiring.
    """
    return await svc.attach_actual_weight(measurement_id, actual_weight_kg)


# =============================================================================
# KALIBRATSIYA
# =============================================================================

@router.post("/{scale_id}/calibrate", response_model=CalibrationResponse)
async def calibrate_scale(
    scale_id:    int                     = Path(..., gt=0),
    data_points: list[CalibrationDataPoint] = Body(..., min_length=3),
    current_user: CurrentManager = None,
    svc:         ScaleService = Depends(_svc),
):
    """
    AI taxmin modelini kalibratsiya qilish.

    Kamida 3 ta (AI o'lchov ID + haqiqiy vazn) juftligi kerak.
    Kalibratsiya koeffitsiyenti median usulida hisoblanadi.
    """
    return await svc.calibrate(scale_id, data_points)