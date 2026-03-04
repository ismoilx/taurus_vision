"""
Taurus Vision — Sensor API Endpoints (Sprint 17-18)

IoT qurilmalardan sensor ma'lumotlarini qabul qilish va
monitoring uchun API endpointlar.

ENDPOINTLAR:
    POST   /sensors/reading            — Bitta o'lchov yuborish
    POST   /sensors/readings/bulk      — Batch o'lchovlar (max 100)
    GET    /sensors/latest/{animal_id} — Jonivorning oxirgi o'lchovi
    GET    /sensors/devices            — Aktiv qurilmalar ro'yxati
    GET    /sensors/stats              — Ferma sensor statistikasi
    GET    /sensors/anomalies          — Bugungi anomaliyalar
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import (
    get_current_active_user,
    require_manager,
)
from app.services.sensor_service import SensorService
from app.schemas.sensor import (
    SensorReadingCreate,
    SensorReadingBulkCreate,
    SensorReadingResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sensors", tags=["Sensors — IoT"])


# =============================================================================
# WRITE ENDPOINTS
# =============================================================================

@router.post(
    "/reading",
    response_model=SensorReadingResponse,
    status_code=201,
    summary="Sensor o'lchovi yuborish",
)
async def create_sensor_reading(
    data: SensorReadingCreate,
    db:   AsyncSession = Depends(get_db),
    _:    object       = Depends(require_manager),
):
    """
    Bitta sensor o'lchovini qabul qilish va saqlash.
    Anomaly aniqlansa avtomatik alert yaratiladi.
    """
    service = SensorService(db)
    reading = await service.process_reading(data)
    return reading


@router.post(
    "/readings/bulk",
    status_code=201,
    summary="Batch sensor o'lchovlari",
)
async def create_bulk_readings(
    data: SensorReadingBulkCreate,
    db:   AsyncSession = Depends(get_db),
    _:    object       = Depends(require_manager),
):
    """
    1–100 ta sensor o'lchovini batch saqlash.
    Xato bo'lgan o'lchovlar skip qilinadi, qolganlar saqlanadi.
    """
    service = SensorService(db)
    result  = await service.process_bulk(data.readings)
    return result


# =============================================================================
# READ ENDPOINTS
# =============================================================================

@router.get(
    "/latest/{animal_id}",
    response_model=Optional[SensorReadingResponse],
    summary="Jonivorning oxirgi sensor o'lchovi",
)
async def get_latest_reading(
    animal_id: int,
    db:        AsyncSession = Depends(get_db),
    _:         object       = Depends(get_current_active_user),
):
    """Jonivorning eng so'nggi sensor ma'lumotini qaytaradi."""
    service = SensorService(db)
    reading = await service.get_latest_for_animal(animal_id)
    return reading


@router.get(
    "/devices",
    summary="Aktiv qurilmalar ro'yxati",
)
async def get_active_devices(
    db: AsyncSession = Depends(get_db),
    _:  object       = Depends(get_current_active_user),
):
    """So'nggi 24 soatda aktiv sensor qurilmalar ro'yxati."""
    service = SensorService(db)
    devices = await service.get_active_devices()
    return {"total": len(devices), "devices": devices}


@router.get(
    "/stats",
    summary="Ferma sensor statistikasi",
)
async def get_sensor_stats(
    db: AsyncSession = Depends(get_db),
    _:  object       = Depends(get_current_active_user),
):
    """Ferma bo'yicha bugungi sensor statistikasi."""
    service = SensorService(db)
    stats   = await service.get_farm_stats()
    return stats


@router.get(
    "/anomalies",
    summary="Bugungi sensor anomaliyalari",
)
async def get_anomalies(
    db: AsyncSession = Depends(get_db),
    _:  object       = Depends(get_current_active_user),
):
    """Bugun aniqlangan normal diapazondan chiqgan o'lchovlar."""
    from app.repositories.sensor_repository import SensorRepository
    repo      = SensorRepository(db)
    anomalies = await repo.get_anomalies_today()
    return {"total": len(anomalies), "anomalies": anomalies}