"""
Taurus Vision — Behavior Analysis Celery Tasks (Sprint 9-10)

Jonivorlar xatti-harakatini tahlil qilish uchun background task lari.

TASK LAR:
    run_behavior_analysis  — Bitta jonivorning 24 soatlik detection
                             pattern larini tahlil qiladi
    detect_anomalies       — Barcha aktiv jonivorlar uchun anomaliya
                             aniqlaydi va alert yaratadi
    generate_daily_summary — Kunlik ferma hisobini aggregate qiladi

BEHAVIOR MODELLARI:
    Faollik darajasi:
        - Yuqori (>48 detection/kun)  → Jonivor sog'lom va faol
        - O'rtacha (24-48)             → Odatiy holat
        - Past (<24)                   → Nazorat talab qiladi

    Feeding pattern:
        - Har 6 soatda kamida 1 ta feeding zona viziti = normal
        - 12+ soat l'araliksiz = ogohlantirish

    Harakatlanish:
        - Bbox markazining standart og'ishi > 0.3 = faol
        - < 0.05 = klinikalik (tinchlangan, yotib qolgan)
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from workers.celery_app import celery_app

logger = logging.getLogger(__name__)

# Behavior chegaralari
_MIN_DAILY_DETECTIONS   = 24    # Kuniga minimal normal detection
_WARN_DAILY_DETECTIONS  = 8     # Bu dan past → ogohlantirish
_FEEDING_INTERVAL_H     = 12    # Oziqlanish oralig'i (soat) — bu dan ko'p = xavfli
_MOVEMENT_STD_ACTIVE    = 0.15  # Bbox std > shu = faol jonivor
_MOVEMENT_STD_INACTIVE  = 0.05  # Bbox std < shu = harakatsiz jonivor

# Ferma zonalari (normalized koordinatalar) — detection_pipeline bilan mos
_FEEDING_ZONE  = {"x1": 0.1, "y1": 0.2, "x2": 0.5, "y2": 0.6}
_RESTING_ZONE  = {"x1": 0.5, "y1": 0.5, "x2": 0.9, "y2": 0.9}


# ============================================================================
# BITTA JONIVOR XATTI-HARAKATINI TAHLIL QILISH
# ============================================================================

@celery_app.task(
    name="analysis.run_behavior_analysis",
    queue="default",
    bind=True,
    max_retries=3,
    default_retry_delay=120,
)
def run_behavior_analysis(
    self,
    animal_id:  int,
    date_str:   str | None = None,
) -> dict[str, Any]:
    """
    Bitta jonivorning 24 soatlik xatti-harakatini tahlil qiladi.

    Detection pattern laridan quyidagilarni aniqlaydi:
        - Faollik darajasi (activity level)
        - Oziqlanish davriyligi (feeding regularity)
        - Harakatlanish intensivligi (movement intensity)
        - Ijtimoiy xulq (social score — boshqa jonivorlar bilan birga aniqlanish)

    Args:
        animal_id: Tahlil qilinadigan jonivor ID
        date_str:  Tahlil sanasi "YYYY-MM-DD" formatida (None = bugun)

    Returns:
        {
            "animal_id":        int,
            "date":             str,
            "activity_level":   "high" | "medium" | "low" | "critical",
            "detection_count":  int,
            "feeding_visits":   int,
            "last_feeding_h":   float | None,
            "movement_score":   float,
            "social_score":     float,
            "anomalies":        list[str],
            "alert_created":    bool,
        }
    """
    import asyncio
    from app.core.database import AsyncSessionLocal

    logger.info(
        f"Behavior analysis started",
        extra={"extra_data": {"animal_id": animal_id, "date": date_str}},
    )

    async def _run() -> dict[str, Any]:
        from app.models.detection import Detection
        from app.models.animal import Animal, AnimalStatus
        from app.services.alert_service import AlertService
        from app.models.alert import AlertType, AlertSeverity
        from sqlalchemy import select, func

        # Tahlil sanasini aniqlash
        if date_str:
            analysis_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        else:
            analysis_date = datetime.now(timezone.utc)

        period_start = analysis_date.replace(hour=0, minute=0, second=0, microsecond=0)
        period_end   = period_start + timedelta(days=1)

        result: dict[str, Any] = {
            "animal_id":       animal_id,
            "date":            period_start.date().isoformat(),
            "activity_level":  "unknown",
            "detection_count": 0,
            "feeding_visits":  0,
            "last_feeding_h":  None,
            "movement_score":  0.0,
            "social_score":    0.0,
            "anomalies":       [],
            "alert_created":   False,
        }

        async with AsyncSessionLocal() as db:
            # 1. Jonivor mavjudligini tekshirish
            animal = await db.get(Animal, animal_id)
            if not animal or animal.status != AnimalStatus.ACTIVE:
                result["activity_level"] = "inactive_animal"
                return result

            # 2. Davr ichidagi detection larni olish
            detections = (
                await db.execute(
                    select(Detection)
                    .where(
                        Detection.animal_id == animal_id,
                        Detection.timestamp >= period_start,
                        Detection.timestamp < period_end,
                    )
                    .order_by(Detection.timestamp)
                )
            ).scalars().all()

            det_count = len(detections)
            result["detection_count"] = det_count

            # 3. Faollik darajasi
            if det_count >= _MIN_DAILY_DETECTIONS:
                activity = "high"
            elif det_count >= _WARN_DAILY_DETECTIONS:
                activity = "medium"
            elif det_count > 0:
                activity = "low"
            else:
                activity = "critical"
                result["anomalies"].append(
                    f"0 detection (kutilgan: {_MIN_DAILY_DETECTIONS}/kun)"
                )

            result["activity_level"] = activity

            if det_count == 0:
                return result

            # 4. Oziqlanish zonasi tashrif (bbox feeding zone ga tegishi)
            feeding_visits = 0
            last_feeding_ts: datetime | None = None

            for det in detections:
                bbox = det.bbox or {}
                cx   = bbox.get("x", 0) + bbox.get("w", 0) / 2
                cy   = bbox.get("y", 0) + bbox.get("h", 0) / 2

                if (
                    _FEEDING_ZONE["x1"] <= cx <= _FEEDING_ZONE["x2"]
                    and _FEEDING_ZONE["y1"] <= cy <= _FEEDING_ZONE["y2"]
                ):
                    feeding_visits += 1
                    last_feeding_ts = det.timestamp

            result["feeding_visits"] = feeding_visits

            if last_feeding_ts:
                hours_ago = (datetime.now(timezone.utc) - last_feeding_ts).total_seconds() / 3600
                result["last_feeding_h"] = round(hours_ago, 1)

                if hours_ago > _FEEDING_INTERVAL_H:
                    result["anomalies"].append(
                        f"Oziqlanmagan: {hours_ago:.1f} soat "
                        f"(chegarasi: {_FEEDING_INTERVAL_H} soat)"
                    )
            elif det_count > 0:
                # Detectionlar bor lekin feeding zone da ko'rinmagan
                result["anomalies"].append(
                    "Oziqlanish zonasida ko'rinmadi (24 soat)"
                )

            # 5. Harakatlanish tahlili (bbox markazi standart og'ishi)
            cx_values = [
                (d.bbox or {}).get("x", 0) + (d.bbox or {}).get("w", 0) / 2
                for d in detections if d.bbox
            ]

            if len(cx_values) >= 2:
                mean_cx = sum(cx_values) / len(cx_values)
                variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
                std_cx   = variance ** 0.5
                result["movement_score"] = round(std_cx, 3)

                if std_cx < _MOVEMENT_STD_INACTIVE:
                    result["anomalies"].append(
                        f"Juda kam harakat (std={std_cx:.3f}, "
                        f"normal >={_MOVEMENT_STD_ACTIVE})"
                    )

            # 6. Ijtimoiy xulq (boshqa jonivorlar bilan bir vaqtda kamera da)
            # Bir xil kamera va vaqtda (±10s) boshqa jonivorlar bormi?
            social_detections = 0
            for i, det in enumerate(detections):
                nearby = await db.scalar(
                    select(func.count(Detection.id)).where(
                        Detection.camera_id == det.camera_id,
                        Detection.timestamp.between(
                            det.timestamp - timedelta(seconds=10),
                            det.timestamp + timedelta(seconds=10),
                        ),
                        Detection.animal_id != animal_id,
                        Detection.animal_id.isnot(None),
                    )
                )
                if nearby and nearby > 0:
                    social_detections += 1

            if det_count > 0:
                result["social_score"] = round(social_detections / det_count, 3)

            # 7. Jiddiy anomaliyalar uchun Alert yaratish
            critical_anomalies = [
                a for a in result["anomalies"]
                if "oziqlanmagan" in a.lower() or "0 detection" in a.lower()
            ]

            if critical_anomalies and len(critical_anomalies) >= 1:
                try:
                    alert_svc = AlertService(db)
                    await alert_svc.create_alert(
                        animal_id  = animal_id,
                        alert_type = AlertType.HEALTH_CONCERN,
                        severity   = AlertSeverity.WARNING,
                        message    = (
                            f"Xatti-harakat anomaliyasi: {'; '.join(critical_anomalies)}"
                        ),
                    )
                    result["alert_created"] = True
                    logger.warning(
                        f"Alert created for animal {animal_id}",
                        extra={"extra_data": {"anomalies": critical_anomalies}},
                    )
                except Exception as exc:
                    logger.error(f"Alert creation failed: {exc}")

        return result

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        final = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(
            f"run_behavior_analysis failed for animal {animal_id}: {exc}",
            exc_info=True,
        )
        raise self.retry(exc=exc)

    logger.info(
        "Behavior analysis completed",
        extra={"extra_data": {
            "animal_id":      animal_id,
            "activity_level": final.get("activity_level"),
            "anomalies":      len(final.get("anomalies", [])),
        }},
    )
    return final


# ============================================================================
# BARCHA JONIVOLAR UCHUN ANOMALIYA ANIQLASH
# ============================================================================

@celery_app.task(
    name="analysis.detect_anomalies",
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def detect_anomalies(self) -> dict[str, Any]:
    """
    Barcha aktiv jonivorlar uchun anomaliya aniqlaydi.

    Har 6 soatda celery_beat tomonidan chaqiriladi.

    ALGORITM:
        1. Barcha ACTIVE jonivorlarni oladi
        2. Har biri uchun so'nggi 24 soatdagi detection count ni hisoblaydi
        3. Norma dan pastga tushgan jonivorilar uchun behavior_analysis chaqiradi
        4. Umumiy statistikani qaytaradi

    Returns:
        {
            "total_animals":    int,
            "analyzed":         int,
            "anomalies_found":  int,
            "alerts_created":   int,
        }
    """
    import asyncio
    from app.core.database import AsyncSessionLocal

    logger.info("Anomaly detection started")

    async def _run() -> dict[str, Any]:
        from app.models.animal import Animal, AnimalStatus
        from app.models.detection import Detection
        from sqlalchemy import select, func

        anomaly_count = 0
        alerts_created = 0
        analyzed = 0

        async with AsyncSessionLocal() as db:
            # Aktiv jonivorlarni olish
            animals = (
                await db.execute(
                    select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
                )
            ).scalars().all()

            total = len(animals)
            period_start = datetime.now(timezone.utc) - timedelta(hours=24)

            for animal in animals:
                try:
                    # So'nggi 24 soatdagi detection soni
                    det_count = await db.scalar(
                        select(func.count(Detection.id)).where(
                            Detection.animal_id == animal.id,
                            Detection.timestamp >= period_start,
                        )
                    ) or 0

                    # Kutilgan minimal detection dan kam bo'lsa — tahlil qilish
                    if det_count < _WARN_DAILY_DETECTIONS:
                        anomaly_count += 1
                        # Behavior analysis ni background da queue qilish
                        run_behavior_analysis.apply_async(
                            args=[animal.id],
                            queue="default",
                        )

                    analyzed += 1

                except Exception as exc:
                    logger.warning(
                        f"Anomaly check failed for animal {animal.id}: {exc}"
                    )

        return {
            "total_animals":   total,
            "analyzed":        analyzed,
            "anomalies_found": anomaly_count,
            "alerts_created":  alerts_created,
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(f"detect_anomalies failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    logger.info("Anomaly detection completed", extra={"extra_data": result})
    return result


# ============================================================================
# KUNLIK FERMA XULOSASI
# ============================================================================

@celery_app.task(
    name="analysis.generate_daily_summary",
    queue="default",
    bind=True,
    max_retries=2,
    default_retry_delay=300,
)
def generate_daily_summary(self, date_str: str | None = None) -> dict[str, Any]:
    """
    Kunlik ferma xulosa statistikasini generatsiya qiladi.

    Har kuni soat 23:00 da celery_beat tomonidan chaqiriladi.

    HISOBOT TARKIBI:
        - Jami detection soni
        - Tanilgan/tanilmagan jonivorlar nisbati
        - O'rtacha confidence
        - Aktiv/faol kameralar
        - Yaratilgan alertlar soni

    Args:
        date_str: "YYYY-MM-DD" (None = bugun)

    Returns:
        Kunlik statistika dict
    """
    import asyncio
    from app.core.database import AsyncSessionLocal

    logger.info(f"Daily summary generation started (date={date_str})")

    async def _run() -> dict[str, Any]:
        from app.models.detection import Detection
        from app.models.alert import Alert
        from app.models.animal import Animal, AnimalStatus
        from sqlalchemy import select, func, distinct

        if date_str:
            target_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
        else:
            target_date = datetime.now(timezone.utc)

        day_start = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        day_end   = day_start + timedelta(days=1)

        async with AsyncSessionLocal() as db:
            # Jami detectionlar
            total_detections = await db.scalar(
                select(func.count(Detection.id)).where(
                    Detection.timestamp.between(day_start, day_end)
                )
            ) or 0

            # Tanilgan detectionlar (animal_id mavjud)
            identified = await db.scalar(
                select(func.count(Detection.id)).where(
                    Detection.timestamp.between(day_start, day_end),
                    Detection.animal_id.isnot(None),
                )
            ) or 0

            # O'rtacha confidence
            avg_conf = await db.scalar(
                select(func.avg(Detection.confidence)).where(
                    Detection.timestamp.between(day_start, day_end)
                )
            ) or 0.0

            # Faol jonivorlar (aniqlangan)
            active_animals = await db.scalar(
                select(func.count(distinct(Detection.animal_id))).where(
                    Detection.timestamp.between(day_start, day_end),
                    Detection.animal_id.isnot(None),
                )
            ) or 0

            # Jami aktiv jonivorlar (DB da)
            total_active = await db.scalar(
                select(func.count(Animal.id)).where(
                    Animal.status == AnimalStatus.ACTIVE
                )
            ) or 0

            # Bugungi alertlar
            alerts_today = await db.scalar(
                select(func.count(Alert.id)).where(
                    Alert.created_at.between(day_start, day_end)
                )
            ) or 0

            # Noyob kameralar soni
            unique_cameras = await db.scalar(
                select(func.count(distinct(Detection.camera_id))).where(
                    Detection.timestamp.between(day_start, day_end)
                )
            ) or 0

        return {
            "date":                 day_start.date().isoformat(),
            "total_detections":     total_detections,
            "identified":           identified,
            "unidentified":         total_detections - identified,
            "identification_rate":  round(identified / total_detections * 100, 1)
                                    if total_detections > 0 else 0.0,
            "average_confidence":   round(avg_conf, 3),
            "active_animals_seen":  active_animals,
            "total_active_animals": total_active,
            "coverage_rate":        round(active_animals / total_active * 100, 1)
                                    if total_active > 0 else 0.0,
            "alerts_created":       alerts_today,
            "unique_cameras":       unique_cameras,
            "generated_at":         datetime.now(timezone.utc).isoformat(),
        }

    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(_run())
        loop.close()
    except Exception as exc:
        logger.error(f"generate_daily_summary failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    logger.info("Daily summary generated", extra={"extra_data": result})
    return result
