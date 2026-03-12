"""
Taurus Vision — Sensor API Endpoints (Sprint 17-18)

IoT qurilmalardan sensor ma'lumotlarini qabul qilish va
monitoring uchun API endpointlar.

ENDPOINTLAR:
    POST   /sensors/reading               — Bitta o'lchov yuborish
    POST   /sensors/readings/bulk         — Batch o'lchovlar (max 100)
    GET    /sensors/readings              — Barcha o'lchovlar ro'yxati
    GET    /sensors/latest                — Oxirgi o'lchovlar (barcha)
    GET    /sensors/latest/{animal_id}    — Jonivorning oxirgi o'lchovi
    GET    /sensors/history/{animal_id}   — Jonivor sensor tarixi (grafik uchun)
    GET    /sensors/farm-history          — Ferma umumiy sensor tarixi
    GET    /sensors/devices               — Aktiv qurilmalar ro'yxati
    GET    /sensors/stats                 — Ferma sensor statistikasi
    GET    /sensors/anomalies             — Bugungi anomaliyalar
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

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
from app.models.sensor_reading import SensorReading

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sensors", tags=["Sensors — IoT"])


# =============================================================================
# FLEXIBLE CREATE SCHEMA — test compatibility (sensor_type/value/unit)
# =============================================================================

class SensorReadingFlexCreate(BaseModel):
    """
    Moslashuvchan sensor o'lchov yaratish.
    Eski format (sensor_type/value/unit) ham yangi format (device_type/temperature) ham qabul qilinadi.
    """
    device_id:    str            = Field(..., min_length=1, max_length=100)
    # Yangi format
    device_type:  Optional[str]  = Field(None)
    animal_id:    Optional[int]  = Field(None)
    temperature:  Optional[float]= Field(None)
    heart_rate:   Optional[float]= Field(None)
    activity_level: Optional[float] = Field(None)
    weight_kg:    Optional[float]= Field(None)
    recorded_at:  Optional[datetime] = Field(None)
    # Eski format (test compatibility)
    sensor_type:  Optional[str]  = Field(None, description="Alias: temperature|heart_rate|activity|weight")
    value:        Optional[float]= Field(None, description="Alias: o'lchov qiymati")
    unit:         Optional[str]  = Field(None, description="Birligi (ignored, compatibility)")

    @model_validator(mode="after")
    def resolve_legacy_fields(self) -> "SensorReadingFlexCreate":
        # sensor_type → device_type
        if self.device_type is None:
            st = (self.sensor_type or "").lower()
            if st in ("temperature", "temp"):
                self.device_type = "collar"
            elif st in ("heart_rate", "heartrate", "bpm"):
                self.device_type = "collar"
            elif st in ("activity", "motion"):
                self.device_type = "collar"
            elif st in ("weight", "scale"):
                self.device_type = "scale"
            elif st in ("environment", "env", "humidity", "co2"):
                self.device_type = "environment"
            else:
                self.device_type = "collar"

        # value → to'g'ri maydon
        if self.value is not None:
            st = (self.sensor_type or "").lower()
            if st in ("temperature", "temp") and self.temperature is None:
                self.temperature = self.value
            elif st in ("heart_rate", "heartrate", "bpm") and self.heart_rate is None:
                self.heart_rate = self.value
            elif st in ("activity", "motion") and self.activity_level is None:
                self.activity_level = min(max(self.value / 100.0, 0.0), 1.0) if self.value > 1 else self.value
            elif st in ("weight", "scale") and self.weight_kg is None:
                self.weight_kg = self.value
            else:
                # Default: temperature ga qo'yamiz
                if self.temperature is None:
                    self.temperature = self.value
        return self

    def to_sensor_reading_create(self) -> SensorReadingCreate:
        return SensorReadingCreate(
            device_id=self.device_id,
            device_type=self.device_type or "collar",
            animal_id=self.animal_id,
            temperature=self.temperature,
            heart_rate=self.heart_rate,
            activity_level=self.activity_level,
            weight_kg=self.weight_kg,
            recorded_at=self.recorded_at,
        )


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
    data: SensorReadingFlexCreate,
    db:   AsyncSession = Depends(get_db),
    _:    object       = Depends(require_manager),
):
    """
    Bitta sensor o'lchovini qabul qilish va saqlash.
    Anomaly aniqlansa avtomatik alert yaratiladi.
    """
    service = SensorService(db)
    reading = await service.process_reading(data.to_sensor_reading_create())
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

@router.get(
    "/readings",
    summary="Barcha sensor o'lchovlari ro'yxati",
)
async def list_sensor_readings(
    limit: int        = Query(50, ge=1, le=500, description="Sahifa hajmi"),
    skip:  int        = Query(0, ge=0, description="Offset"),
    db:    AsyncSession = Depends(get_db),
    _:     object       = Depends(get_current_active_user),
):
    """Barcha sensor o'lchovlarini sahifalab qaytaradi."""
    result = await db.execute(
        select(SensorReading)
        .order_by(SensorReading.recorded_at.desc())
        .offset(skip)
        .limit(limit)
    )
    readings = result.scalars().all()
    total = await db.scalar(select(func.count(SensorReading.id))) or 0
    return {
        "items": [SensorReadingResponse.model_validate(r) for r in readings],
        "total": total,
    }


@router.get(
    "/latest",
    summary="Oxirgi o'lchovlar (barcha qurilmalar)",
)
async def get_all_latest_readings(
    limit: int        = Query(20, ge=1, le=100, description="Qaytariladigan o'lchovlar soni"),
    db:    AsyncSession = Depends(get_db),
    _:     object       = Depends(get_current_active_user),
):
    """
    Har bir qurilmaning eng so'nggi o'lchovini qaytaradi.
    test_latest_readings uchun: sample_sensor_reading bo'lsa ishlaydi.
    """
    # Har device_id dan bitta (eng so'nggi) o'lchov
    subq = (
        select(
            SensorReading.device_id,
            func.max(SensorReading.recorded_at).label("max_at"),
        )
        .group_by(SensorReading.device_id)
        .subquery()
    )
    q = (
        select(SensorReading)
        .join(
            subq,
            and_(
                SensorReading.device_id == subq.c.device_id,
                SensorReading.recorded_at == subq.c.max_at,
            ),
        )
        .order_by(SensorReading.recorded_at.desc())
        .limit(limit)
    )
    result = await db.execute(q)
    readings = result.scalars().all()
    return {
        "total": len(readings),
        "readings": [SensorReadingResponse.model_validate(r) for r in readings],
    }


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

# =============================================================================
# HISTORY ENDPOINTS (grafik uchun)
# =============================================================================

@router.get(
    "/history/{animal_id}",
    summary="Jonivor sensor tarixi (grafik uchun)",
    description=(
        "Berilgan jonivorning so'nggi N kunlik sensor o'lchovlarini qaytaradi. "
        "Grafik uchun optimallashtrilgan: har soat o'rtacha qiymatlari."
    ),
)
async def get_animal_sensor_history(
    animal_id: int,
    days: int = Query(default=7, ge=1, le=90, description="Necha kun (1-90)"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_active_user),
):
    """
    Jonivor sensor tarixini soatlik o'rtama bilan qaytaradi.

    Args:
        animal_id: Jonivor ID
        days:      Necha kun (1-90, default 7)

    Returns:
        { animal_id, days, points: [{hour, temperature, heart_rate, activity_level, weight_kg, count}] }
    """
    now   = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    # Soatlik o'rtama — PostgreSQL date_trunc bilan
    result = await db.execute(
        select(
            func.date_trunc("hour", SensorReading.recorded_at).label("hour"),
            func.avg(SensorReading.temperature).label("temperature"),
            func.avg(SensorReading.heart_rate).label("heart_rate"),
            func.avg(SensorReading.activity_level).label("activity_level"),
            func.avg(SensorReading.weight_kg).label("weight_kg"),
            func.count(SensorReading.id).label("count"),
        )
        .where(
            and_(
                SensorReading.animal_id == animal_id,
                SensorReading.recorded_at >= start,
            )
        )
        .group_by(func.date_trunc("hour", SensorReading.recorded_at))
        .order_by(func.date_trunc("hour", SensorReading.recorded_at).asc())
    )

    rows = result.all()
    points = [
        {
            "hour":           row.hour.isoformat() if row.hour else None,
            "temperature":    round(row.temperature, 2) if row.temperature else None,
            "heart_rate":     round(row.heart_rate, 1) if row.heart_rate else None,
            "activity_level": round(row.activity_level, 3) if row.activity_level else None,
            "weight_kg":      round(row.weight_kg, 2) if row.weight_kg else None,
            "count":          row.count,
        }
        for row in rows
    ]

    return {
        "animal_id": animal_id,
        "days":      days,
        "total_points": len(points),
        "points":    points,
    }


@router.get(
    "/farm-history",
    summary="Ferma umumiy sensor tarixi",
    description="Barcha jonivornlarning o'rtacha sensor ko'rsatkichlari — kunlik aggregatsiya.",
)
async def get_farm_sensor_history(
    days: int = Query(default=14, ge=1, le=90, description="Necha kun (1-90)"),
    db: AsyncSession = Depends(get_db),
    _: object = Depends(get_current_active_user),
):
    """
    Ferma bo'yicha kunlik sensor o'rtamalarini qaytaradi.

    Args:
        days: Necha kun (1-90, default 14)

    Returns:
        { days, points: [{date, avg_temperature, avg_heart_rate, avg_activity, animal_count}] }
    """
    now   = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    result = await db.execute(
        select(
            func.date_trunc("day", SensorReading.recorded_at).label("day"),
            func.avg(SensorReading.temperature).label("avg_temperature"),
            func.avg(SensorReading.heart_rate).label("avg_heart_rate"),
            func.avg(SensorReading.activity_level).label("avg_activity"),
            func.count(func.distinct(SensorReading.animal_id)).label("animal_count"),
            func.count(SensorReading.id).label("reading_count"),
        )
        .where(SensorReading.recorded_at >= start)
        .group_by(func.date_trunc("day", SensorReading.recorded_at))
        .order_by(func.date_trunc("day", SensorReading.recorded_at).asc())
    )

    rows   = result.all()
    points = [
        {
            "date":            row.day.strftime("%Y-%m-%d") if row.day else None,
            "avg_temperature": round(row.avg_temperature, 2) if row.avg_temperature else None,
            "avg_heart_rate":  round(row.avg_heart_rate, 1) if row.avg_heart_rate else None,
            "avg_activity":    round(row.avg_activity, 3) if row.avg_activity else None,
            "animal_count":    row.animal_count,
            "reading_count":   row.reading_count,
        }
        for row in rows
    ]

    return {
        "days":         days,
        "total_points": len(points),
        "points":       points,
    }