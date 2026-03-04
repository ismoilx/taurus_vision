"""
Taurus Vision — Sensor Service (Sprint 17-18)

IoT sensor ma'lumotlarini qabul qilish, saqlash va tahlil qilish.

ARXITEKTURA:
    IoT Device  →  POST /api/v1/sensors/reading
                       ↓
                   SensorService.process_reading()
                       ├── Validatsiya
                       ├── SensorRepository.create()
                       ├── Anomaly detection
                       └── AlertService (agar anormal)

ADI INTEGRATSIYA:
    ADIService._get_sensor_data(animal_id, date)
        └── SensorRepository.get_daily_summary()
            → {"temperature": 38.7, "heart_rate": 62, ...}

NORMAL DIAPZONLAR (qoramol):
    Harorat:      38.0 – 39.5 °C
    Yurak urishi: 40   – 80   bpm
    Faollik:      0.2  – 0.8  (rest–normal)
    Vazn:         jonivorga xos, 15% og'ish = muammo
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sensor_reading import SensorReading
from app.repositories.sensor_repository import SensorRepository
from app.schemas.sensor import SensorReadingCreate
from app.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Sog'liq normalari (qoramol)                                          #
# ------------------------------------------------------------------ #

NORMAL_RANGES = {
    "temperature": {
        "min_normal":   38.0,
        "max_normal":   39.5,
        "min_warning":  37.5,
        "max_warning":  40.0,
        "min_critical": 36.0,
        "max_critical": 41.5,
    },
    "heart_rate": {
        "min_normal":   40,
        "max_normal":   80,
        "min_warning":  30,
        "max_warning":  100,
        "min_critical": 20,
        "max_critical": 120,
    },
}


class SensorService:
    """
    IoT sensor ma'lumotlarini boshqarish servisi.

    Usage:
        service = SensorService(db)
        result = await service.process_reading(data)
        summary = await service.get_daily_summary(animal_id, "2026-03-04")
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self._repo = SensorRepository(db)

    # ================================================================ #
    # PUBLIC API                                                         #
    # ================================================================ #

    async def process_reading(
        self,
        data: SensorReadingCreate,
    ) -> SensorReading:
        """
        Bitta sensor o'lchovini qabul qilib saqlash.

        Anomaly aniqlansa alert yaratadi.

        Args:
            data: SensorReadingCreate schema

        Returns:
            Saqlangan SensorReading instance

        Raises:
            ValidationError: Noto'g'ri ma'lumot
        """
        recorded_at = data.recorded_at or datetime.now(timezone.utc)

        reading = SensorReading(
            device_id      = data.device_id,
            device_type    = data.device_type,
            animal_id      = data.animal_id,
            temperature    = data.temperature,
            heart_rate     = data.heart_rate,
            activity_level = data.activity_level,
            weight_kg      = data.weight_kg,
            recorded_at    = recorded_at,
        )

        saved = await self._repo.create(reading)

        # Anomaly tekshirish va alert yaratish
        if data.animal_id:
            await self._check_and_alert(saved)

        await self.db.commit()

        logger.info(
            f"Sensor reading saved | "
            f"device={data.device_id} | "
            f"animal={data.animal_id} | "
            f"temp={data.temperature} | "
            f"hr={data.heart_rate}"
        )

        return saved

    async def process_bulk(
        self,
        readings: list[SensorReadingCreate],
    ) -> dict:
        """
        Bir nechta o'lchovni batch qayta ishlash.

        Args:
            readings: 1–100 ta SensorReadingCreate

        Returns:
            {"saved": int, "failed": int, "errors": list}
        """
        saved_count  = 0
        failed_count = 0
        errors       = []

        for item in readings:
            try:
                await self.process_reading(item)
                saved_count += 1
            except Exception as e:
                failed_count += 1
                errors.append({"device_id": item.device_id, "error": str(e)})

        logger.info(
            f"Bulk sensor: saved={saved_count} failed={failed_count}"
        )
        return {
            "saved":  saved_count,
            "failed": failed_count,
            "errors": errors,
        }

    async def get_daily_summary(
        self,
        animal_id: int,
        date_str: str,
    ) -> Optional[dict]:
        """
        ADI service uchun kunlik o'rtacha sensor qiymatlari.

        Args:
            animal_id: Jonivor ID
            date_str:  YYYY-MM-DD

        Returns:
            {"temperature": 38.7, "heart_rate": 62, ...} yoki None
        """
        return await self._repo.get_daily_summary(animal_id, date_str)

    async def get_latest_for_animal(
        self,
        animal_id: int,
    ) -> Optional[SensorReading]:
        """Jonivorning eng so'nggi sensor o'lchovi."""
        return await self._repo.get_latest_for_animal(animal_id)

    async def get_farm_stats(self) -> dict:
        """Ferma bo'yicha sensor statistikasi — dashboard uchun."""
        stats     = await self._repo.get_farm_stats_today()
        devices   = await self._repo.get_active_devices(hours=24)
        anomalies = await self._repo.get_anomalies_today()

        return {
            **stats,
            "total_devices":    len(devices),
            "anomalies_today":  len(anomalies),
            "recent_anomalies": anomalies[:10],
        }

    async def get_active_devices(self) -> list[dict]:
        """So'nggi 24 soatda aktiv qurilmalar ro'yxati."""
        return await self._repo.get_active_devices(hours=24)

    # ================================================================ #
    # ANOMALY DETECTION (private)                                        #
    # ================================================================ #

    async def _check_and_alert(self, reading: SensorReading) -> None:
        """
        Sensor qiymati anormal bo'lsa alert yaratish.

        CRITICAL: harorat >41.5°C yoki <36°C, HR >120 yoki <20
        WARNING:  harorat >40°C yoki <37.5°C, HR >100 yoki <30

        Args:
            reading: Saqlangan SensorReading
        """
        try:
            from app.services.alert_service import AlertService
            from app.models.alert import AlertType, AlertSeverity

            alert_service = AlertService(self.db)
            issues        = self._detect_issues(reading)

            if not issues:
                return

            severity = AlertSeverity.CRITICAL if issues["critical"] else AlertSeverity.HIGH

            description_parts = []
            for issue in issues["critical"] + issues["warning"]:
                description_parts.append(issue)

            await alert_service._ensure_alert(
                animal_id   = reading.animal_id,
                alert_type  = AlertType.HEALTH_ANOMALY,
                title       = f"Sensor anomaliya: {reading.device_id}",
                description = " | ".join(description_parts),
                severity    = severity,
                context     = {
                    "device_id":    reading.device_id,
                    "temperature":  reading.temperature,
                    "heart_rate":   reading.heart_rate,
                    "recorded_at":  reading.recorded_at.isoformat(),
                },
            )

            logger.warning(
                f"Sensor anomaly alert | "
                f"animal={reading.animal_id} | "
                f"device={reading.device_id} | "
                f"issues={description_parts}"
            )

        except Exception as e:
            # Alert xatosi asosiy jarayonni to'xtatmasin
            logger.error(f"Failed to create sensor alert: {e}", exc_info=True)

    @staticmethod
    def _detect_issues(reading: SensorReading) -> dict:
        """
        Sensor qiymatlarida muammolarni aniqlash.

        Returns:
            {"critical": [...], "warning": [...]}
        """
        critical = []
        warning  = []

        temp = reading.temperature
        if temp is not None:
            r = NORMAL_RANGES["temperature"]
            if temp < r["min_critical"] or temp > r["max_critical"]:
                critical.append(f"Harorat kritik: {temp:.1f}°C")
            elif temp < r["min_warning"] or temp > r["max_warning"]:
                warning.append(f"Harorat ogohlantiruv: {temp:.1f}°C")

        hr = reading.heart_rate
        if hr is not None:
            r = NORMAL_RANGES["heart_rate"]
            if hr < r["min_critical"] or hr > r["max_critical"]:
                critical.append(f"Yurak urishi kritik: {hr:.0f}bpm")
            elif hr < r["min_warning"] or hr > r["max_warning"]:
                warning.append(f"Yurak urishi ogohlantiruv: {hr:.0f}bpm")

        return {"critical": critical, "warning": warning}