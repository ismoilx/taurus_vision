"""
Taurus Vision — Behavior Analysis Celery Tasks (Sprint 9-10)

Jonivorlar xatti-harakatini tahlil qilish uchun background tasklar.

TASKLAR:
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

ASYNC PATTERN:
    BUG FIX #2 va #3: Barcha tasklar endi DatabaseTask base class dan
    foydalanadi. Bu Python 3.12 da thread-safe va event loop leak dan
    himoyalaydi. DatabaseTask.run_async() har doim yangi thread +
    yangi event loop ochadi — worker thread ni iflostirmaslik uchun.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Any

from workers.celery_app import celery_app
from workers.tasks.adi_tasks import DatabaseTask  # BUG FIX #3: DatabaseTask ishlatilmoqda

logger = logging.getLogger(__name__)

# Behavior chegaralari — detection_pipeline va behavior_service bilan mos
_MIN_DAILY_DETECTIONS  = 24     # Kuniga minimal normal detection
_WARN_DAILY_DETECTIONS = 8      # Bu dan past → ogohlantirish
_FEEDING_INTERVAL_H    = 12     # Oziqlanish oralig'i (soat) — bu dan ko'p = xavfli
_MOVEMENT_STD_ACTIVE   = 0.15   # Bbox std > shu = faol jonivor
_MOVEMENT_STD_INACTIVE = 0.05   # Bbox std < shu = harakatsiz jonivor

# Ferma zonalari (normalized koordinatalar) — behavior_service bilan mos
_FEEDING_ZONE = {"x1": 0.10, "y1": 0.20, "x2": 0.50, "y2": 0.60}
_RESTING_ZONE = {"x1": 0.50, "y1": 0.50, "x2": 0.90, "y2": 0.90}


# =============================================================================
# TASK 1: BITTA JONIVOR XATTI-HARAKATINI TAHLIL QILISH
# =============================================================================

@celery_app.task(
    name="analysis.run_behavior_analysis",
    queue="default",
    bind=True,
    base=DatabaseTask,          # BUG FIX #3: base=DatabaseTask qo'shildi
    max_retries=3,
    default_retry_delay=120,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def run_behavior_analysis(
    self,
    animal_id: int,
    date_str: str | None = None,
) -> dict[str, Any]:
    """
    Bitta jonivorning 24 soatlik xatti-harakatini tahlil qiladi.

    Detection pattern laridan quyidagilarni aniqlaydi:
        - Faollik darajasi (activity level)
        - Oziqlanish davriyligi (feeding regularity)
        - Harakatlanish intensivligi (movement intensity)
        - Ijtimoiy xulq (social score)

    Args:
        animal_id: Tahlil qilinadigan jonivor ID
        date_str:  Tahlil sanasi "YYYY-MM-DD" (None = bugun)

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
    logger.info(
        "Behavior analysis started",
        extra={"extra_data": {"animal_id": animal_id, "date": date_str}},
    )

    # BUG FIX #2 + #3: self.run_async() ishlatilmoqda
    # Eski kod: asyncio.new_event_loop() + loop.close() (finally blokida emas edi)
    # Yangi kod: DatabaseTask.run_async() → ThreadPoolExecutor → asyncio.run()
    # Bu har doim yangi thread va event loop ochadi, xavfsiz yopadi.
    try:
        result = self.run_async(
            _run_behavior_analysis_async(animal_id=animal_id, date_str=date_str)
        )
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
            "activity_level": result.get("activity_level"),
            "anomalies":      len(result.get("anomalies", [])),
        }},
    )
    return result


async def _run_behavior_analysis_async(
    animal_id: int,
    date_str: str | None,
) -> dict[str, Any]:
    """Bitta jonivor uchun async xatti-harakat tahlili."""
    from app.core.database import AsyncSessionLocal
    from app.models.animal import Animal, AnimalStatus
    from app.models.detection import Detection
    from app.services.alert_service import AlertService
    from app.models.alert import AlertType, AlertSeverity
    from sqlalchemy import select, func

    result: dict[str, Any] = {
        "animal_id":       animal_id,
        "date":            None,
        "activity_level":  "unknown",
        "detection_count": 0,
        "feeding_visits":  0,
        "last_feeding_h":  None,
        "movement_score":  0.0,
        "social_score":    0.0,
        "anomalies":       [],
        "alert_created":   False,
    }

    # Tahlil sanasini aniqlash
    if date_str:
        analysis_date = datetime.fromisoformat(date_str).replace(tzinfo=timezone.utc)
    else:
        analysis_date = datetime.now(timezone.utc)

    period_start = analysis_date.replace(hour=0, minute=0, second=0, microsecond=0)
    period_end   = period_start + timedelta(days=1)
    result["date"] = period_start.date().isoformat()

    async with AsyncSessionLocal() as db:
        # 1. Jonivor mavjudligini tekshirish
        animal = await db.get(Animal, animal_id)
        if not animal or animal.status != AnimalStatus.ACTIVE:
            result["activity_level"] = "inactive_animal"
            return result

        # 2. Davr ichidagi detectionlar
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

        # 4. Oziqlanish zonasi tashrifi
        feeding_visits    = 0
        last_feeding_ts: datetime | None = None

        for det in detections:
            bbox = det.bbox or {}
            cx   = bbox.get("x", 0.0) + bbox.get("w", 0.0) / 2
            cy   = bbox.get("y", 0.0) + bbox.get("h", 0.0) / 2

            if (
                _FEEDING_ZONE["x1"] <= cx <= _FEEDING_ZONE["x2"]
                and _FEEDING_ZONE["y1"] <= cy <= _FEEDING_ZONE["y2"]
            ):
                feeding_visits  += 1
                last_feeding_ts  = det.timestamp

        result["feeding_visits"] = feeding_visits

        if last_feeding_ts:
            hours_ago = (
                datetime.now(timezone.utc) - last_feeding_ts
            ).total_seconds() / 3600
            result["last_feeding_h"] = round(hours_ago, 1)

            if hours_ago > _FEEDING_INTERVAL_H:
                result["anomalies"].append(
                    f"Oziqlanmagan: {hours_ago:.1f} soat "
                    f"(chegara: {_FEEDING_INTERVAL_H} soat)"
                )
        elif det_count > 0:
            result["anomalies"].append("Oziqlanish zonasida ko'rinmadi (24 soat)")

        # 5. Harakatlanish tahlili (bbox markazi std)
        cx_values = [
            (d.bbox or {}).get("x", 0.0) + (d.bbox or {}).get("w", 0.0) / 2
            for d in detections
            if d.bbox
        ]

        if len(cx_values) >= 2:
            mean_cx  = sum(cx_values) / len(cx_values)
            variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
            std_cx   = variance ** 0.5
            result["movement_score"] = round(std_cx, 3)

            if std_cx < _MOVEMENT_STD_INACTIVE:
                result["anomalies"].append(
                    f"Juda kam harakat (std={std_cx:.3f}, "
                    f"normal >={_MOVEMENT_STD_ACTIVE})"
                )

        # 6. Ijtimoiy xulq (bir xil kamera va vaqtda boshqa jonivorlar)
        social_detections = 0
        for det in detections:
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

        result["social_score"] = round(social_detections / det_count, 3)

        # 7. Kritik anomaliyalar uchun alert yaratish
        critical_anomalies = [
            a for a in result["anomalies"]
            if "oziqlanmagan" in a.lower() or "0 detection" in a.lower()
        ]

        if critical_anomalies:
            try:
                alert_svc = AlertService(db)
                await alert_svc.create_alert(
                    animal_id  = animal_id,
                    alert_type = AlertType.HEALTH_CONCERN,
                    severity   = AlertSeverity.WARNING,
                    message    = (
                        f"Xatti-harakat anomaliyasi: "
                        f"{'; '.join(critical_anomalies)}"
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


# =============================================================================
# TASK 2: BARCHA JONIVORLAR UCHUN ANOMALIYA ANIQLASH
# =============================================================================

@celery_app.task(
    name="analysis.detect_anomalies",
    queue="default",
    bind=True,
    base=DatabaseTask,          # BUG FIX #3: DatabaseTask qo'shildi
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=600,
    time_limit=660,
    acks_late=True,
)
def detect_anomalies(self) -> dict[str, Any]:
    """
    Barcha aktiv jonivorlar uchun anomaliya aniqlaydi.

    Har 6 soatda celery_beat tomonidan chaqiriladi.

    ALGORITM:
        1. Barcha ACTIVE jonivorlarni oladi
        2. Har biri uchun so'nggi 24 soatdagi detection count ni hisoblaydi
        3. Norma dan pastga tushgan jonivorlar uchun behavior_analysis queue qiladi
        4. Umumiy statistikani qaytaradi

    Returns:
        {
            "total_animals":   int,
            "analyzed":        int,
            "anomalies_found": int,
            "queued_analysis": int,
            "timestamp":       str,
        }
    """
    logger.info("Anomaly detection started")

    try:
        result = self.run_async(_detect_anomalies_async())
    except Exception as exc:
        logger.error(f"detect_anomalies failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    logger.info("Anomaly detection completed", extra={"extra_data": result})
    return result


async def _detect_anomalies_async() -> dict[str, Any]:
    """Barcha jonivorlar uchun anomaliya tekshiruvi async implementatsiyasi."""
    from app.core.database import AsyncSessionLocal
    from app.models.animal import Animal, AnimalStatus
    from app.models.detection import Detection
    from sqlalchemy import select, func

    anomaly_count  = 0
    queued_count   = 0
    analyzed_count = 0

    async with AsyncSessionLocal() as db:
        animals = (
            await db.execute(
                select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            )
        ).scalars().all()

        total         = len(animals)
        period_start  = datetime.now(timezone.utc) - timedelta(hours=24)

        for animal in animals:
            try:
                det_count = await db.scalar(
                    select(func.count(Detection.id)).where(
                        Detection.animal_id == animal.id,
                        Detection.timestamp >= period_start,
                    )
                ) or 0

                if det_count < _WARN_DAILY_DETECTIONS:
                    anomaly_count += 1
                    # Behavior analysis ni background da queue qilish
                    run_behavior_analysis.apply_async(
                        args=[animal.id],
                        queue="default",
                    )
                    queued_count += 1

                analyzed_count += 1

            except Exception as exc:
                logger.warning(
                    f"Anomaly check failed for animal {animal.id}: {exc}"
                )

    return {
        "total_animals":   total,
        "analyzed":        analyzed_count,
        "anomalies_found": anomaly_count,
        "queued_analysis": queued_count,
        "timestamp":       datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# TASK 3: KUNLIK FERMA XULOSASI
# =============================================================================

@celery_app.task(
    name="analysis.generate_daily_summary",
    queue="default",
    bind=True,
    base=DatabaseTask,          # BUG FIX #3: DatabaseTask qo'shildi
    max_retries=2,
    default_retry_delay=300,
    soft_time_limit=300,
    time_limit=360,
    acks_late=True,
)
def generate_daily_summary(
    self,
    date_str: str | None = None,
) -> dict[str, Any]:
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
    logger.info(f"Daily summary generation started (date={date_str})")

    try:
        result = self.run_async(
            _generate_daily_summary_async(date_str=date_str)
        )
    except Exception as exc:
        logger.error(f"generate_daily_summary failed: {exc}", exc_info=True)
        raise self.retry(exc=exc)

    logger.info("Daily summary generated", extra={"extra_data": result})
    return result


async def _generate_daily_summary_async(
    date_str: str | None,
) -> dict[str, Any]:
    """Kunlik ferma xulosasi async implementatsiyasi."""
    from app.core.database import AsyncSessionLocal
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

        # Tanilgan detectionlar
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

        # Ko'ringan noyob jonivorlar
        active_animals_seen = await db.scalar(
            select(func.count(distinct(Detection.animal_id))).where(
                Detection.timestamp.between(day_start, day_end),
                Detection.animal_id.isnot(None),
            )
        ) or 0

        # Jami aktiv jonivorlar
        total_active = await db.scalar(
            select(func.count(Animal.id)).where(
                Animal.status == AnimalStatus.ACTIVE
            )
        ) or 0

        # Bugungi alertlar
        alerts_today = await db.scalar(
            select(func.count(Alert.id)).where(
                Alert.triggered_at.between(day_start, day_end)
            )
        ) or 0

        # Noyob kameralar
        unique_cameras = await db.scalar(
            select(func.count(distinct(Detection.camera_id))).where(
                Detection.timestamp.between(day_start, day_end)
            )
        ) or 0

    return {
        "date":                  day_start.date().isoformat(),
        "total_detections":      total_detections,
        "identified":            identified,
        "unidentified":          total_detections - identified,
        "identification_rate":   round(identified / total_detections * 100, 1)
                                 if total_detections > 0 else 0.0,
        "average_confidence":    round(avg_conf, 3),
        "active_animals_seen":   active_animals_seen,
        "total_active_animals":  total_active,
        "coverage_rate":         round(active_animals_seen / total_active * 100, 1)
                                 if total_active > 0 else 0.0,
        "alerts_created":        alerts_today,
        "unique_cameras":        unique_cameras,
        "generated_at":          datetime.now(timezone.utc).isoformat(),
    }