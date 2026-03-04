"""
Taurus Vision — Sensor Celery Tasks (Sprint 17-18)

IoT sensor ma'lumotlarini avtomatik monitoring qiluvchi background tasklar.

TASKLAR:
    sensor.check_anomalies      — Har 5 daqiqada: anormal sensor qiymatlarini tekshirish
    sensor.daily_sensor_report  — Har kecha 01:30: kunlik sensor hisoboti
    sensor.cleanup_old_readings — Har haftada: eski sensor ma'lumotlarini tozalash
    sensor.check_offline_devices — Har 15 daqiqada: offline qurilmalarni aniqlash

QUEUE:
    default — barcha sensor tasklar (yengil, tez)

INTEGRATSIYA:
    SensorService  → SensorRepository → PostgreSQL
    AlertService   → alert yaratish va deduplication
    ADIService     → kunlik ADI hisoblashda sensor data ishlatiladi
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from celery import Task

from workers.celery_app import celery_app
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Base Task                                                            #
# ------------------------------------------------------------------ #

class DatabaseTask(Task):
    """
    Async coroutine larni Celery sync muhitida xavfsiz ishlatish.
    Har doim yangi thread + yangi event loop yaratiladi.
    """
    abstract = True

    def run_async(self, coro) -> object:
        import asyncio
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, coro)
            return future.result()


# =============================================================================
# TASK 1: ANOMALY CHECK — har 5 daqiqada
# =============================================================================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="sensor.check_anomalies",
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
    time_limit=180,
    acks_late=True,
)
def check_sensor_anomalies(self) -> dict:
    """
    So'nggi 5 daqiqada kelgan sensor o'lchovlarini tekshirish.

    Anormal qiymat (harorat >40°C yoki <37.5°C, HR >100 yoki <30)
    aniqlansa avtomatik alert yaratiladi.

    Returns:
        {
            "checked":       int,
            "anomalies":     int,
            "alerts_created": int,
        }
    """
    return self.run_async(_check_anomalies_async())


async def _check_anomalies_async() -> dict:
    """check_sensor_anomalies ning async implementatsiyasi."""

    logger.debug("[sensor] Anomaly check started")

    anomaly_count = 0
    alert_count   = 0
    checked_count = 0

    since = datetime.now(timezone.utc) - timedelta(minutes=6)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, and_
        from app.models.sensor_reading import SensorReading
        from app.services.sensor_service import SensorService, NORMAL_RANGES
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType, AlertSeverity

        alert_service = AlertService(db)

        # So'nggi 6 daqiqadagi barcha o'lchovlar
        result = await db.execute(
            select(SensorReading).where(
                and_(
                    SensorReading.recorded_at >= since,
                    SensorReading.animal_id.isnot(None),
                )
            ).order_by(SensorReading.recorded_at.desc())
        )
        readings = result.scalars().all()
        checked_count = len(readings)

        for reading in readings:
            issues = SensorService._detect_issues(reading)
            if not issues["critical"] and not issues["warning"]:
                continue

            anomaly_count += 1
            severity = (
                AlertSeverity.CRITICAL
                if issues["critical"]
                else AlertSeverity.HIGH
            )

            all_issues = issues["critical"] + issues["warning"]

            try:
                await alert_service._ensure_alert(
                    animal_id   = reading.animal_id,
                    alert_type  = AlertType.HEALTH_ANOMALY,
                    title       = f"Sensor anomaliya: {reading.device_id}",
                    description = " | ".join(all_issues),
                    severity    = severity,
                    context     = {
                        "device_id":   reading.device_id,
                        "temperature": reading.temperature,
                        "heart_rate":  reading.heart_rate,
                        "recorded_at": reading.recorded_at.isoformat(),
                        "source":      "celery_sensor_check",
                    },
                )
                alert_count += 1
            except Exception as e:
                logger.error(
                    f"[sensor] Alert yaratishda xato: "
                    f"animal={reading.animal_id} | {e}"
                )

        await db.commit()

    if anomaly_count:
        logger.warning(
            f"[sensor] Anomaly check | "
            f"checked={checked_count} | "
            f"anomalies={anomaly_count} | "
            f"alerts={alert_count}"
        )
    else:
        logger.debug(
            f"[sensor] Anomaly check OK | checked={checked_count}"
        )

    return {
        "checked":        checked_count,
        "anomalies":      anomaly_count,
        "alerts_created": alert_count,
    }


# =============================================================================
# TASK 2: OFFLINE QURILMALAR — har 15 daqiqada
# =============================================================================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="sensor.check_offline_devices",
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=180,
    time_limit=240,
    acks_late=True,
)
def check_offline_devices(self) -> dict:
    """
    30 daqiqadan ortiq ma'lumot yuborмаgan qurilmalarni aniqlash.

    Offline qurilma aniqlansa WARNING darajada alert yaratiladi.
    Bir xil qurilma uchun alert deduplication ishlaydi.

    Returns:
        {
            "total_devices":   int,
            "offline_devices": int,
            "alerts_created":  int,
        }
    """
    return self.run_async(_check_offline_devices_async())


async def _check_offline_devices_async() -> dict:
    """check_offline_devices ning async implementatsiyasi."""

    logger.debug("[sensor] Offline device check started")

    offline_count = 0
    alert_count   = 0

    offline_threshold = datetime.now(timezone.utc) - timedelta(minutes=30)

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func, and_
        from app.models.sensor_reading import SensorReading
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType, AlertSeverity

        alert_service = AlertService(db)

        # So'nggi 24 soatda aktiv bo'lgan qurilmalar
        result = await db.execute(
            select(
                SensorReading.device_id,
                SensorReading.animal_id,
                func.max(SensorReading.recorded_at).label("last_seen"),
            )
            .where(
                SensorReading.recorded_at >= datetime.now(timezone.utc) - timedelta(hours=24)
            )
            .group_by(SensorReading.device_id, SensorReading.animal_id)
        )
        devices = result.fetchall()
        total_devices = len(devices)

        for device in devices:
            if device.last_seen and device.last_seen < offline_threshold:
                offline_count += 1
                minutes_offline = int(
                    (datetime.now(timezone.utc) - device.last_seen).total_seconds() / 60
                )

                if device.animal_id:
                    try:
                        await alert_service._ensure_alert(
                            animal_id   = device.animal_id,
                            alert_type  = AlertType.SENSOR_OFFLINE,
                            title       = f"Sensor offline: {device.device_id}",
                            description = (
                                f"Qurilma {device.device_id} "
                                f"{minutes_offline} daqiqadan beri "
                                f"ma'lumot yuborмаyapti."
                            ),
                            severity    = AlertSeverity.MEDIUM,
                            context     = {
                                "device_id":       device.device_id,
                                "minutes_offline": minutes_offline,
                                "last_seen":       device.last_seen.isoformat(),
                            },
                        )
                        alert_count += 1
                    except Exception as e:
                        logger.error(
                            f"[sensor] Offline alert xatosi: "
                            f"device={device.device_id} | {e}"
                        )

        await db.commit()

    logger.info(
        f"[sensor] Offline check | "
        f"total={total_devices} | "
        f"offline={offline_count} | "
        f"alerts={alert_count}"
    )

    return {
        "total_devices":   total_devices,
        "offline_devices": offline_count,
        "alerts_created":  alert_count,
    }


# =============================================================================
# TASK 3: KUNLIK SENSOR HISOBOTI — har kecha 01:30
# =============================================================================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="sensor.daily_report",
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=720,
    acks_late=True,
)
def daily_sensor_report(
    self,
    target_date: Optional[str] = None,
) -> dict:
    """
    Barcha aktiv jonivorlar uchun kunlik sensor xulosasini hisoblash.

    Natijalar log ga yoziladi va keyinchalik dashboard da ko'rsatiladi.
    ADI hisoblashdan KEYIN ishga tushishi kerak (01:30 UTC).

    Args:
        target_date: YYYY-MM-DD (None = kecha)

    Returns:
        {
            "date":             str,
            "animals_with_data": int,
            "anomaly_count":    int,
            "avg_temperature":  float | None,
            "avg_heart_rate":   float | None,
        }
    """
    return self.run_async(_daily_sensor_report_async(target_date))


async def _daily_sensor_report_async(target_date: Optional[str]) -> dict:
    """daily_sensor_report ning async implementatsiyasi."""

    date_str = target_date or (
        datetime.now(timezone.utc) - timedelta(days=1)
    ).strftime("%Y-%m-%d")

    logger.info(f"[sensor] Daily report started | date={date_str}")

    async with AsyncSessionLocal() as db:
        from sqlalchemy import select, func, and_
        from app.models.sensor_reading import SensorReading
        from app.models.animal import Animal, AnimalStatus
        from app.repositories.sensor_repository import SensorRepository

        repo = SensorRepository(db)

        # Aktiv jonivorlar
        result  = await db.execute(
            select(Animal.id).where(Animal.status == AnimalStatus.ACTIVE)
        )
        animal_ids = [row[0] for row in result.fetchall()]

        animals_with_data = 0
        total_temp  = []
        total_hr    = []
        anomaly_count = 0

        for animal_id in animal_ids:
            summary = await repo.get_daily_summary(animal_id, date_str)
            if not summary or summary["reading_count"] == 0:
                continue

            animals_with_data += 1

            if summary["temperature"]:
                total_temp.append(summary["temperature"])
                if summary["temperature"] < 37.5 or summary["temperature"] > 40.0:
                    anomaly_count += 1

            if summary["heart_rate"]:
                total_hr.append(summary["heart_rate"])
                if summary["heart_rate"] < 30 or summary["heart_rate"] > 100:
                    anomaly_count += 1

    avg_temp = round(sum(total_temp) / len(total_temp), 2) if total_temp else None
    avg_hr   = round(sum(total_hr)   / len(total_hr),   2) if total_hr   else None

    result_data = {
        "date":              date_str,
        "animals_with_data": animals_with_data,
        "anomaly_count":     anomaly_count,
        "avg_temperature":   avg_temp,
        "avg_heart_rate":    avg_hr,
    }

    logger.info(
        f"[sensor] Daily report done | "
        f"date={date_str} | "
        f"animals={animals_with_data} | "
        f"anomalies={anomaly_count} | "
        f"avg_temp={avg_temp} | "
        f"avg_hr={avg_hr}"
    )

    return result_data


# =============================================================================
# TASK 4: ESKI MA'LUMOTLARNI TOZALASH — haftalik
# =============================================================================

@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="sensor.cleanup_old_readings",
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def cleanup_old_sensor_readings(
    self,
    keep_days: int = 90,
) -> dict:
    """
    90 kundan eski sensor o'lchovlarini o'chirish.

    Har Yakshanba 04:00 UTC da ishga tushadi.
    Bu DB ni kichik va tez ushlab turadi.

    Args:
        keep_days: Necha kunlik ma'lumotni saqlash (default: 90)

    Returns:
        {"deleted": int, "kept": int, "cutoff_date": str}
    """
    return self.run_async(_cleanup_old_readings_async(keep_days))


async def _cleanup_old_readings_async(keep_days: int) -> dict:
    """cleanup_old_sensor_readings ning async implementatsiyasi."""

    from sqlalchemy import delete, func, select

    cutoff = datetime.now(timezone.utc) - timedelta(days=keep_days)

    logger.info(
        f"[sensor] Cleanup started | "
        f"cutoff={cutoff.strftime('%Y-%m-%d')} | "
        f"keep_days={keep_days}"
    )

    async with AsyncSessionLocal() as db:
        from app.models.sensor_reading import SensorReading

        delete_stmt = (
            delete(SensorReading)
            .where(SensorReading.recorded_at < cutoff)
        )
        result  = await db.execute(delete_stmt)
        deleted = result.rowcount
        await db.commit()

        remaining = await db.scalar(
            select(func.count(SensorReading.id))
        ) or 0

    logger.info(
        f"[sensor] Cleanup done | "
        f"deleted={deleted} | "
        f"remaining={remaining}"
    )

    return {
        "deleted":     deleted,
        "kept":        remaining,
        "cutoff_date": cutoff.strftime("%Y-%m-%d"),
    }