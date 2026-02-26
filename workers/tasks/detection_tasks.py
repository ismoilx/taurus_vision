"""
Taurus Vision — Detection Celery Tasks (Sprint 9-10)

Kamera detection pipeline uchun Celery background task lari.

TASK LAR:
    health_check_cameras  — Har 5 daqiqada barcha kameralar sog'lig'ini tekshiradi
    cleanup_stale_detections — Eski, bog'lanmagan detection yozuvlarini tozalaydi
    aggregate_camera_stats   — Kamera statistikasini Redis ga cache qiladi

ESLATMA:
    Real-time detection pipeline asyncio.Task sifatida ishlaydi
    (PipelineManager orqali). Celery task lari esa monitoring,
    cleanup va aggregation uchun ishlatiladi.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)


# ============================================================================
# KAMERA SOGLIQ TEKSHIRUVI
# ============================================================================

@celery_app.task(
    name="detection.health_check_cameras",
    queue="default",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def health_check_cameras(self) -> dict[str, Any]:
    """
    Barcha ro'yxatga olingan kameralar sog'lig'ini tekshiradi.

    Har 5 daqiqada celery_beat tomonidan chaqiriladi.

    TEKSHIRUVLAR:
        - DB dagi kameralar vs haqiqatda ishlayotganlar
        - Uzoq vaqt oflayn bo'lgan kameralar uchun alert yaratish
        - Pipeline statistikalarini log qilish

    Returns:
        {
            "checked":  kameralar soni,
            "healthy":  sog'lom kameralar soni,
            "offline":  oflayn kameralar soni,
            "alerts_created": yaratilgan alertlar soni,
        }
    """
    import asyncio
    from app.core.database import AsyncSessionLocal
    from app.models.camera import Camera
    from sqlalchemy import select

    logger.info("Camera health check started")

    result = {
        "checked":        0,
        "healthy":        0,
        "offline":        0,
        "alerts_created": 0,
        "timestamp":      datetime.now(timezone.utc).isoformat(),
    }

    async def _run() -> dict[str, Any]:
        try:
            from app.services.pipeline_manager import get_pipeline_manager
            manager = get_pipeline_manager()

            async with AsyncSessionLocal() as db:
                # DB dagi barcha kameralarni olamiz
                cameras = (await db.execute(select(Camera))).scalars().all()
                result["checked"] = len(cameras)

                running_cameras = set(manager.list_running())

                for camera in cameras:
                    if camera.camera_id in running_cameras:
                        result["healthy"] += 1
                    else:
                        result["offline"] += 1

                        # enabled=True lekin ishlamayotgan kameralar uchun
                        # biz alert yaratmaymiz (pipeline manual boshqariladi)
                        # lekin log qilamiz
                        logger.info(
                            f"Camera {camera.camera_id} is registered but pipeline "
                            "is not running (manual control)"
                        )

            # Pipeline statistikalarini log qilish
            all_status = manager.get_all_status()
            for cam_id, status in all_status.items():
                if status.get("running") and status.get("stats"):
                    stats = status["stats"]
                    logger.info(
                        "Pipeline stats",
                        extra={"extra_data": {
                            "camera_id":        cam_id,
                            "fps":              stats.get("fps", 0),
                            "processed_frames": stats.get("processed_frames", 0),
                            "detections":       stats.get("yolo_detections", 0),
                            "errors":           stats.get("errors", 0),
                        }},
                    )

        except Exception as exc:
            logger.error(f"Camera health check error: {exc}", exc_info=True)
            result["error"] = str(exc)

        return result

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        final_result = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(f"Event loop error in health_check_cameras: {exc}")
        final_result = result

    logger.info(
        "Camera health check completed",
        extra={"extra_data": final_result},
    )
    return final_result


# ============================================================================
# ESKI DETECTION YOZUVLARINI TOZALASH
# ============================================================================

@celery_app.task(
    name="detection.cleanup_stale_detections",
    queue="maintenance",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def cleanup_stale_detections(self, days_to_keep: int = 90) -> dict[str, Any]:
    """
    Eski detection yozuvlarini tozalaydi.

    Hafta da bir marta celery_beat tomonidan chaqiriladi.
    Animal ID si bo'lmagan (anonymous) va N kundan eski
    detection yozuvlari o'chiriladi.

    Args:
        days_to_keep: Qancha kun saqlansin (default: 90 kun)

    Returns:
        {
            "deleted_count":    o'chirilgan yozuvlar soni,
            "cutoff_date":      chegara sanasi,
            "execution_time_s": bajarilish vaqti,
        }
    """
    import asyncio
    import time as time_module
    from app.core.database import AsyncSessionLocal
    from app.models.detection import Detection
    from sqlalchemy import delete, and_

    logger.info(f"Stale detection cleanup started (keep={days_to_keep} days)")
    start_time = time_module.monotonic()

    async def _run() -> dict[str, Any]:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_to_keep)
        deleted_count = 0

        try:
            async with AsyncSessionLocal() as db:
                # Eski, jonivorga bog'lanmagan detectionlarni o'chirish
                stmt = delete(Detection).where(
                    and_(
                        Detection.timestamp < cutoff_date,
                        Detection.animal_id.is_(None),
                    )
                )
                result = await db.execute(stmt)
                deleted_count = result.rowcount
                await db.commit()

                logger.info(
                    f"Stale detections deleted",
                    extra={"extra_data": {
                        "deleted":     deleted_count,
                        "cutoff_date": cutoff_date.isoformat(),
                    }},
                )

        except Exception as exc:
            logger.error(f"Cleanup error: {exc}", exc_info=True)
            raise

        return {
            "deleted_count":    deleted_count,
            "cutoff_date":      cutoff_date.isoformat(),
            "execution_time_s": round(time_module.monotonic() - start_time, 2),
        }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(f"cleanup_stale_detections failed: {exc}")
        raise self.retry(exc=exc)

    logger.info("Stale detection cleanup completed", extra={"extra_data": result})
    return result


# ============================================================================
# KAMERA STATISTIKASINI REDIS GA CACHE QILISH
# ============================================================================

@celery_app.task(
    name="detection.aggregate_camera_stats",
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
)
def aggregate_camera_stats(self) -> dict[str, Any]:
    """
    Kamera statistikasini yig'adi va Redis ga cache qiladi.

    Har 1 daqiqada celery_beat tomonidan chaqiriladi.
    Frontend dashboard uchun tez-tez so'raladigan ma'lumotlarni
    Redis da saqlash API yukini kamaytiradi.

    Cache keys:
        taurus:cameras:stats:all   — Barcha kameralar
        taurus:cameras:stats:{id}  — Bitta kamera

    Returns:
        {
            "cached_cameras": cache qilingan kameralar soni,
            "total_fps":      umumiy FPS,
            "total_detections_today": bugungi detectionlar,
        }
    """
    import asyncio
    import json
    from app.core.database import AsyncSessionLocal
    from app.models.detection import Detection
    from sqlalchemy import func, select

    logger.debug("Camera stats aggregation started")

    async def _run() -> dict[str, Any]:
        try:
            from app.services.pipeline_manager import get_pipeline_manager
            import redis as redis_lib
            from app.config import settings

            manager    = get_pipeline_manager()
            all_status = manager.get_all_status()
            system_metrics = manager.get_system_metrics()

            # Bugungi detectionlar soni
            today_count = 0
            async with AsyncSessionLocal() as db:
                today_start = datetime.now(timezone.utc).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                today_count = await db.scalar(
                    select(func.count(Detection.id)).where(
                        Detection.timestamp >= today_start
                    )
                ) or 0

            # Redis ga yozish
            redis_client = redis_lib.from_url(settings.REDIS_URL, decode_responses=True)

            # Umumiy statistika
            total_fps = sum(
                (s.get("stats") or {}).get("fps", 0)
                for s in all_status.values()
            )

            summary = {
                "timestamp":            datetime.now(timezone.utc).isoformat(),
                "active_pipelines":     system_metrics["active_pipelines"],
                "max_pipelines":        system_metrics["max_pipelines"],
                "total_fps":            round(total_fps, 1),
                "total_detections_today": today_count,
                "cpu_percent":          system_metrics["cpu_percent"],
                "ram_percent":          system_metrics["ram_percent"],
                "can_start_new":        system_metrics["can_start_new"],
                "cameras":              all_status,
            }

            # 90 sekund TTL (2 ta aggregation tsikli)
            redis_client.setex(
                "taurus:cameras:stats:all",
                90,
                json.dumps(summary),
            )

            # Har bir kamera uchun alohida cache
            for cam_id, status in all_status.items():
                redis_client.setex(
                    f"taurus:cameras:stats:{cam_id}",
                    90,
                    json.dumps(status),
                )

            return {
                "cached_cameras":         len(all_status),
                "total_fps":              round(total_fps, 1),
                "total_detections_today": today_count,
                "active_pipelines":       system_metrics["active_pipelines"],
            }

        except Exception as exc:
            logger.warning(f"Stats aggregation error: {exc}")
            return {"error": str(exc), "cached_cameras": 0}

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(f"aggregate_camera_stats failed: {exc}")
        return {"error": str(exc), "cached_cameras": 0}

    return result
