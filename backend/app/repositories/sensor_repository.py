"""
Taurus Vision — Sensor Repository (Sprint 17-18)

SensorReading modeli uchun barcha DB operatsiyalari.
Service layer bu repository orqali ishlaydi.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor_reading import SensorReading

logger = logging.getLogger(__name__)


class SensorRepository:
    """
    SensorReading CRUD va query operatsiyalari.

    Usage:
        repo = SensorRepository(db)
        reading = await repo.create(reading_obj)
        summary = await repo.get_daily_summary(animal_id, "2026-03-04")
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------ #
    # WRITE                                                                #
    # ------------------------------------------------------------------ #

    async def create(self, reading: SensorReading) -> SensorReading:
        """Yangi sensor o'lchovini saqlash."""
        self.db.add(reading)
        await self.db.flush()
        await self.db.refresh(reading)
        return reading

    async def bulk_create(
        self, readings: list[SensorReading]
    ) -> list[SensorReading]:
        """Bir nechta o'lchovni batch saqlash."""
        for r in readings:
            self.db.add(r)
        await self.db.flush()
        return readings

    # ------------------------------------------------------------------ #
    # READ — Single Animal                                                 #
    # ------------------------------------------------------------------ #

    async def get_latest_for_animal(
        self, animal_id: int
    ) -> Optional[SensorReading]:
        """Jonivorning eng so'nggi o'lchovi."""
        result = await self.db.execute(
            select(SensorReading)
            .where(SensorReading.animal_id == animal_id)
            .order_by(desc(SensorReading.recorded_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_for_period(
        self,
        animal_id: int,
        start: datetime,
        end: datetime,
    ) -> list[SensorReading]:
        """Berilgan davrdagi barcha o'lchovlar."""
        result = await self.db.execute(
            select(SensorReading)
            .where(
                and_(
                    SensorReading.animal_id == animal_id,
                    SensorReading.recorded_at >= start,
                    SensorReading.recorded_at < end,
                )
            )
            .order_by(SensorReading.recorded_at.asc())
        )
        return list(result.scalars().all())

    async def get_daily_summary(
        self,
        animal_id: int,
        date_str: str,
    ) -> Optional[dict]:
        """
        Kunlik o'rtacha qiymatlar — ADI _get_sensor_data() uchun.

        Returns:
            {
                "temperature": float | None,
                "heart_rate": float | None,
                "activity_level": float | None,
                "weight_kg": float | None,
                "reading_count": int,
            }
            yoki None agar ma'lumot bo'lmasa
        """
        date = datetime.strptime(date_str, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
        start = date
        end   = date + timedelta(days=1)

        result = await self.db.execute(
            select(
                func.avg(SensorReading.temperature).label("avg_temp"),
                func.avg(SensorReading.heart_rate).label("avg_hr"),
                func.avg(SensorReading.activity_level).label("avg_activity"),
                func.avg(SensorReading.weight_kg).label("avg_weight"),
                func.count(SensorReading.id).label("count"),
            )
            .where(
                and_(
                    SensorReading.animal_id == animal_id,
                    SensorReading.recorded_at >= start,
                    SensorReading.recorded_at < end,
                )
            )
        )
        row = result.fetchone()

        if not row or row.count == 0:
            return None

        return {
            "temperature":    float(row.avg_temp)     if row.avg_temp     else None,
            "heart_rate":     float(row.avg_hr)       if row.avg_hr       else None,
            "activity_level": float(row.avg_activity) if row.avg_activity else None,
            "weight_kg":      float(row.avg_weight)   if row.avg_weight   else None,
            "reading_count":  int(row.count),
        }

    # ------------------------------------------------------------------ #
    # READ — Farm-wide                                                     #
    # ------------------------------------------------------------------ #

    async def get_active_devices(
        self, hours: int = 24
    ) -> list[dict]:
        """So'nggi N soatda ma'lumot yuborgan qurilmalar."""
        since = datetime.now(timezone.utc) - timedelta(hours=hours)

        result = await self.db.execute(
            select(
                SensorReading.device_id,
                SensorReading.device_type,
                SensorReading.animal_id,
                func.count(SensorReading.id).label("reading_count"),
                func.max(SensorReading.recorded_at).label("last_seen"),
            )
            .where(SensorReading.recorded_at >= since)
            .group_by(
                SensorReading.device_id,
                SensorReading.device_type,
                SensorReading.animal_id,
            )
            .order_by(desc("last_seen"))
        )
        rows = result.fetchall()
        return [
            {
                "device_id":     r.device_id,
                "device_type":   r.device_type,
                "animal_id":     r.animal_id,
                "reading_count": r.reading_count,
                "last_seen":     r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        ]

    async def get_farm_stats_today(self) -> dict:
        """Ferma bo'yicha bugungi sensor statistikasi."""
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total = await self.db.scalar(
            select(func.count(SensorReading.id)).where(
                SensorReading.recorded_at >= today_start
            )
        ) or 0

        animals_with_data = await self.db.scalar(
            select(func.count(func.distinct(SensorReading.animal_id))).where(
                and_(
                    SensorReading.recorded_at >= today_start,
                    SensorReading.animal_id.isnot(None),
                )
            )
        ) or 0

        active_devices = await self.db.scalar(
            select(func.count(func.distinct(SensorReading.device_id))).where(
                SensorReading.recorded_at >= today_start
            )
        ) or 0

        return {
            "total_readings_today":  total,
            "animals_with_sensors":  animals_with_data,
            "active_devices_today":  active_devices,
        }

    async def get_anomalies_today(self) -> list[dict]:
        """
        Bugungi anormal qiymatlar.
        Normal diapazondagi: harorat 38.0-39.5°C, HR 40-80 bpm.
        """
        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        result = await self.db.execute(
            select(SensorReading)
            .where(
                and_(
                    SensorReading.recorded_at >= today_start,
                    SensorReading.animal_id.isnot(None),
                )
            )
            .order_by(desc(SensorReading.recorded_at))
        )
        readings = result.scalars().all()

        anomalies = []
        for r in readings:
            issues = []
            if r.temperature is not None:
                if r.temperature < 37.5 or r.temperature > 40.5:
                    issues.append(f"Harorat: {r.temperature:.1f}°C")
            if r.heart_rate is not None:
                if r.heart_rate < 30 or r.heart_rate > 100:
                    issues.append(f"Yurak urishi: {r.heart_rate:.0f}bpm")
            if issues:
                anomalies.append({
                    "animal_id": r.animal_id,
                    "device_id": r.device_id,
                    "issues":    issues,
                    "recorded_at": r.recorded_at.isoformat(),
                })

        return anomalies