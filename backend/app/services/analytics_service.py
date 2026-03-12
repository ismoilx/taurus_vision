"""
Taurus Vision — Analytics Service (Sprint 21-24)

Ferma monitoring tizimi uchun to'liq tahlil servisi.

SPRINT 1-20 (mavjud):
    - get_dashboard_overview()     — Dashboard asosiy ko'rsatkichlari
    - get_weight_trends()          — Vazn o'zgarish grafigi
    - get_detection_patterns()     — Deteksiya naqshlari (soat/kun/kamera)
    - get_health_metrics()         — Sog'liq ko'rsatkichlari va alertlar
    - get_camera_performance()     — Kamera ishlash samaradorligi

SPRINT 21-24 (yangi):
    - get_adi_trends()             — ADI ball o'zgarishi trenди
    - get_growth_trends()          — O'sish egri chizig'i (chiziqli regressiya)
    - get_behavior_trends()        — Xatti-harakat komponentlari trenди
    - compare_animals()            — Ko'p jonivorni yonma-yon taqqoslash
    - compare_periods()            — Davr-davr taqqoslash (shu oy vs o'tgan oy)
    - get_herd_statistics()        — Podaning to'liq statistik panoramasi
    - get_automated_insights()     — Qoidaga asoslangan avtomatik tushunchalar

BUG FIX (Sprint 9-10 dan qolgan):
    AnalyticsService.__init__() da CameraManager import qilingan edi,
    lekin bu klass Sprint 9-10 da PipelineManager bilan almashtirilgan.
    Hozir get_pipeline_manager() ishlatiladi.

ARXITEKTURA:
    Endpoint → AnalyticsService → SQLAlchemy ORM
    Endpoint → AnalyticsService → get_pipeline_manager() (kamera holati uchun)
    AnalyticsService hech qachon biznes logikaнi endpoint'ga qoldirmaydi.
"""

import logging
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Dict, Any, List, Tuple

import numpy as np
from sqlalchemy import select, func, and_, or_, desc, case, distinct
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement
from app.models.adi_log import ADILog, ADICategory
from app.models.alert import Alert as AlertModel, AlertStatus, AlertSeverity
from app.models.feed import FeedRecord
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Xavf darajalari uchun ADI threshold konstantalari
# ---------------------------------------------------------------------------
_ADI_HEALTHY_THRESHOLD  = 75.0
_ADI_AVERAGE_THRESHOLD  = 50.0
_ADI_WARNING_THRESHOLD  = 25.0
_MIN_REGRESSION_POINTS  = 3      # Chiziqli regressiya uchun minimum nuqta soni
_TREND_STABLE_DELTA     = 2.0    # ±2.0 ball — "barqaror" deb hisoblanadi
_MISSING_DAYS_THRESHOLD = 7      # 7 kundan ko'p ko'rinmagan = alarm


class AnalyticsService:
    """
    Ferma monitoring uchun to'liq tahlil servisi.

    Barcha metodlar async va AsyncSession bilan ishlaydi.
    Biznes mantiq faqat shu sinfda — endpoint'lar shunchaki
    chaqirib natijani qaytaradi.
    """

    # ------------------------------------------------------------------
    # INIT  (CameraManager bug tuzatildi — endi pipeline_manager ishlatiladi)
    # ------------------------------------------------------------------

    def __init__(self) -> None:
        """
        Initialize analytics service.

        NOTE: camera_manager olib tashlandi — Sprint 9-10 dan beri
        PipelineManager (singleton) bu vazifani bajaradi.
        Kamera holati lazim bo'lganda get_pipeline_manager() chaqiriladi.
        """
        # Hech qanday singleton saqlashlik kerak emas — pipeline_manager
        # o'z singleton'ini o'zi boshqaradi.
        pass

    # =========================================================================
    # DASHBOARD OVERVIEW  (Sprint 1-8)
    # =========================================================================

    async def get_dashboard_overview(
        self,
        db: AsyncSession,
        date_from: Optional[date] = None,
        date_to:   Optional[date] = None,
    ) -> Dict[str, Any]:
        """
        Dashboard uchun asosiy ko'rsatkichlarni qaytaradi.

        Args:
            db:        Async database session
            date_from: Vaqt diapazoni boshi (None = bugun)
            date_to:   Vaqt diapazoni oxiri  (None = bugun)

        Returns:
            Dict: animals, detections, weight, system, recent_activity, alerts

        Raises:
            Exception: DB so'rov xatosi
        """
        logger.info("Generating dashboard overview")

        if date_to   is None: date_to   = datetime.utcnow().date()
        if date_from is None: date_from = date_to

        try:
            total_animals      = await self._get_total_animals(db)
            active_animals     = await self._get_active_animals(db)
            animals_by_status  = await self._get_animals_by_status(db)
            detections_today   = await self._get_detections_count(db, datetime.utcnow().date(), datetime.utcnow().date())
            detections_week    = await self._get_detections_count(db, datetime.utcnow().date() - timedelta(days=7), datetime.utcnow().date())
            detections_month   = await self._get_detections_count(db, datetime.utcnow().date() - timedelta(days=30), datetime.utcnow().date())
            total_detections   = await self._get_detections_count(db)
            avg_weight         = await self._get_average_weight(db)
            weight_change      = await self._get_weight_change_percentage(db, days=7)
            camera_status      = self._get_camera_status()
            recent_detections  = await self._get_recent_detections(db, limit=5)
            alerts             = await self._generate_alerts(db)

            return {
                "timestamp": datetime.utcnow().isoformat(),
                "animals": {
                    "total": total_animals,
                    "active": active_animals,
                    "by_status": animals_by_status,
                },
                "detections": {
                    "today": detections_today,
                    "week":  detections_week,
                    "month": detections_month,
                    "total": total_detections,
                },
                "weight": {
                    "average_kg":           round(avg_weight, 2) if avg_weight else None,
                    "change_percentage_7d": round(weight_change, 2) if weight_change else None,
                },
                "system":          {"cameras": camera_status},
                "recent_activity": recent_detections,
                "alerts":          alerts,
            }

        except Exception as exc:
            logger.error(f"Error generating dashboard overview: {exc}", exc_info=True)
            raise

    # =========================================================================
    # WEIGHT TRENDS  (Sprint 7-8)
    # =========================================================================

    async def get_weight_trends(
        self,
        db:          AsyncSession,
        animal_id:   Optional[int] = None,
        days:        int = 30,
        aggregation: str = "daily",
    ) -> List[Dict[str, Any]]:
        """
        Vazn o'zgarish grafikasi uchun time-series ma'lumot qaytaradi.

        Args:
            db:          Async database session
            animal_id:   Aniq jonivor (None = butun ferma)
            days:        Necha kun orqaga qaralsin
            aggregation: daily | weekly | monthly

        Returns:
            List[Dict]: date, average_weight, min_weight, max_weight,
                        measurement_count, animal_count
        """
        logger.info(
            "Generating weight trends",
            extra={"extra_data": {"animal_id": animal_id, "days": days}},
        )
        try:
            date_from = datetime.utcnow().date() - timedelta(days=days)
            date_to   = datetime.utcnow().date()

            query = (
                select(
                    func.date(WeightMeasurement.timestamp).label("date"),
                    func.avg(WeightMeasurement.estimated_weight_kg).label("avg_weight"),
                    func.min(WeightMeasurement.estimated_weight_kg).label("min_weight"),
                    func.max(WeightMeasurement.estimated_weight_kg).label("max_weight"),
                    func.count(WeightMeasurement.id).label("measurement_count"),
                    func.count(distinct(WeightMeasurement.animal_id)).label("animal_count"),
                )
                .where(
                    and_(
                        WeightMeasurement.timestamp >= datetime.combine(date_from, datetime.min.time()),
                        WeightMeasurement.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                    )
                )
            )

            if animal_id is not None:
                query = query.where(WeightMeasurement.animal_id == animal_id)

            query = query.group_by(func.date(WeightMeasurement.timestamp)).order_by(
                func.date(WeightMeasurement.timestamp)
            )

            rows = (await db.execute(query)).all()

            return [
                {
                    "date":              str(row.date)[:10],
                    "average_weight":    round(float(row.avg_weight), 2),
                    "min_weight":        round(float(row.min_weight), 2),
                    "max_weight":        round(float(row.max_weight), 2),
                    "measurement_count": row.measurement_count,
                    "animal_count":      row.animal_count,
                }
                for row in rows
            ]

        except Exception as exc:
            logger.error(f"Error generating weight trends: {exc}", exc_info=True)
            raise

    # =========================================================================
    # DETECTION PATTERNS  (Sprint 7-8)
    # =========================================================================

    async def get_detection_patterns(
        self,
        db:        AsyncSession,
        date_from: date,
        date_to:   date,
    ) -> Dict[str, Any]:
        """
        Deteksiya naqshlarini tahlil qiladi.

        Args:
            db:        Async database session
            date_from: Tahlil boshi
            date_to:   Tahlil oxiri

        Returns:
            Dict: detections_by_hour (24), detections_by_day,
                  detections_by_camera, top_detected_animals, statistics
        """
        logger.info(f"Analyzing detection patterns: {date_from} → {date_to}")
        try:
            # 24 soatlik heatmap
            hour_rows = (await db.execute(
                select(
                    func.extract("hour", Detection.timestamp).label("hour"),
                    func.count(Detection.id).label("count"),
                )
                .where(and_(
                    Detection.timestamp >= datetime.combine(date_from, datetime.min.time()),
                    Detection.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                ))
                .group_by("hour")
                .order_by("hour")
            )).all()

            detections_by_hour = [0] * 24
            for row in hour_rows:
                detections_by_hour[int(row.hour)] = row.count

            # Kunlik soni
            day_rows = (await db.execute(
                select(
                    func.date(Detection.timestamp).label("date"),
                    func.count(Detection.id).label("count"),
                )
                .where(and_(
                    Detection.timestamp >= datetime.combine(date_from, datetime.min.time()),
                    Detection.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                ))
                .group_by("date")
                .order_by("date")
            )).all()

            detections_by_day = [
                {"date": str(row.date)[:10], "count": row.count}
                for row in day_rows
            ]

            # Kamera bo'yicha
            cam_rows = (await db.execute(
                select(
                    Detection.camera_id,
                    func.count(Detection.id).label("count"),
                    func.avg(Detection.confidence).label("avg_conf"),
                )
                .where(and_(
                    Detection.timestamp >= datetime.combine(date_from, datetime.min.time()),
                    Detection.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                ))
                .group_by(Detection.camera_id)
                .order_by(desc("count"))
            )).all()

            detections_by_camera = [
                {
                    "camera_id":          row.camera_id,
                    "detections":         row.count,
                    "average_confidence": round(float(row.avg_conf), 3) if row.avg_conf else 0.0,
                }
                for row in cam_rows
            ]

            # Top 10 aniqlangan jonivor
            top_rows = (await db.execute(
                select(
                    Animal.tag_id,
                    Animal.species,
                    func.count(Detection.id).label("det_count"),
                )
                .select_from(Detection)
                .join(Animal, Detection.animal_id == Animal.id)
                .where(and_(
                    Detection.timestamp >= datetime.combine(date_from, datetime.min.time()),
                    Detection.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                ))
                .group_by(Animal.id, Animal.tag_id, Animal.species)
                .order_by(desc("det_count"))
                .limit(10)
            )).all()

            top_detected_animals = [
                {"tag_id": r.tag_id, "species": r.species, "detections": r.det_count}
                for r in top_rows
            ]

            total        = sum(detections_by_hour)
            days_count   = (date_to - date_from).days + 1
            hours_count  = days_count * 24
            peak_hour    = detections_by_hour.index(max(detections_by_hour)) if total > 0 else None

            return {
                "date_range": {
                    "from":  date_from.isoformat(),
                    "to":    date_to.isoformat(),
                    "days":  days_count,
                },
                "detections_by_hour":     detections_by_hour,
                "detections_by_day":      detections_by_day,
                "detections_by_camera":   detections_by_camera,
                "top_detected_animals":   top_detected_animals,
                "statistics": {
                    "total_detections":      total,
                    "detection_rate_per_hour": round(total / hours_count, 2) if hours_count else 0.0,
                    "peak_hour":             peak_hour,
                },
            }

        except Exception as exc:
            logger.error(f"Error analyzing detection patterns: {exc}", exc_info=True)
            raise

    # =========================================================================
    # HEALTH METRICS  (Sprint 11-12)
    # =========================================================================

    async def get_health_metrics(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Sog'liq ko'rsatkichlari va xavf ballini hisoblaydi.

        Args:
            db: Async database session

        Returns:
            Dict: animals_by_status, weight_distribution, alerts,
                  alert_summary, risk_score, timestamp
        """
        logger.info("Calculating health metrics")
        try:
            animals_by_status = await self._get_animals_by_status(db)

            # Vazn taqsimoti
            weight_rows = (await db.execute(
                select(
                    case(
                        (WeightMeasurement.estimated_weight_kg < 100, "0-100kg"),
                        (WeightMeasurement.estimated_weight_kg < 200, "100-200kg"),
                        (WeightMeasurement.estimated_weight_kg < 300, "200-300kg"),
                        (WeightMeasurement.estimated_weight_kg < 400, "300-400kg"),
                        else_="400kg+",
                    ).label("range"),
                    func.count(distinct(WeightMeasurement.animal_id)).label("count"),
                ).group_by("range")
            )).all()

            weight_distribution = {row.range: row.count for row in weight_rows}

            # Alertlar
            alerts = await self._generate_alerts(db)
            weight_loss_alerts = await self._detect_weight_loss(db)
            alerts.extend(weight_loss_alerts)

            total_animals = sum(animals_by_status.values()) or 1

            return {
                "animals_by_status":   animals_by_status,
                "status_distribution": animals_by_status,   # alias — testlar uchun
                "weight_distribution": weight_distribution,
                "alerts":             alerts,
                "alert_summary": {
                    "total":    len(alerts),
                    "critical": sum(1 for a in alerts if a["severity"] == "critical"),
                    "warning":  sum(1 for a in alerts if a["severity"] == "warning"),
                },
                "risk_score": self._calculate_risk_score(animals_by_status, alerts, total_animals),
                "timestamp":  datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            logger.error(f"Error calculating health metrics: {exc}", exc_info=True)
            raise

    # =========================================================================
    # CAMERA PERFORMANCE  (Sprint 9-10)  — BUG FIX: CameraManager → PipelineManager
    # =========================================================================

    async def get_camera_performance(
        self,
        db:        AsyncSession,
        camera_id: Optional[str] = None,
        days:      int = 7,
    ) -> Dict[str, Any]:
        """
        Kamera ishlash samaradorligini tahlil qiladi.

        Args:
            db:        Async database session
            camera_id: Aniq kamera (None = barcha kameralar)
            days:      Tahlil davri (kunlar)

        Returns:
            Dict: period, cameras[], summary

        Note:
            Kamera ro'yxati DB dagi Detection.camera_id lardan olinadi,
            pipeline_manager dan esa real-time status qo'shiladi.
        """
        logger.info(
            "Analyzing camera performance",
            extra={"extra_data": {"camera_id": camera_id, "days": days}},
        )
        try:
            from app.services.pipeline_manager import get_pipeline_manager
            pm         = get_pipeline_manager()
            pm_status  = pm.get_all_status()  # dict[camera_id, status_dict]

            date_from = datetime.utcnow() - timedelta(days=days)

            # Barcha aktiv kamera ID larini DB dan topamiz
            cam_id_rows = (await db.execute(
                select(distinct(Detection.camera_id))
                .where(Detection.timestamp >= date_from)
            )).scalars().all()

            # Agar camera_id so'ralgan bo'lsa faqat uni ko'rsatamiz
            cam_ids = (
                [camera_id] if camera_id and camera_id in cam_id_rows
                else cam_id_rows
            )

            performance_data = []
            for cam_id in cam_ids:
                det_row = (await db.execute(
                    select(
                        func.count(Detection.id).label("total"),
                        func.avg(Detection.confidence).label("avg_conf"),
                    )
                    .where(and_(
                        Detection.camera_id == cam_id,
                        Detection.timestamp >= date_from,
                    ))
                )).one_or_none()

                total_det   = det_row.total    if det_row else 0
                avg_conf    = float(det_row.avg_conf) if det_row and det_row.avg_conf else 0.0
                hours       = days * 24
                det_per_h   = round(total_det / hours, 2) if hours else 0.0

                cam_stat    = pm_status.get(cam_id, {})
                stats_dict  = cam_stat.get("stats") or {}
                is_running  = cam_stat.get("running", False)

                performance_data.append({
                    "camera_id":           cam_id,
                    "status":              "running" if is_running else "stopped",
                    "uptime_percentage":   100.0 if is_running else 0.0,
                    "total_detections":    total_det,
                    "detections_per_hour": det_per_h,
                    "average_confidence":  round(avg_conf, 3),
                    "fps":                 float(stats_dict.get("fps", 0.0)),
                    "errors":              int(stats_dict.get("errors", 0)),
                    "total_frames":        int(stats_dict.get("total_frames", 0)),
                })

            running_count = sum(1 for c in performance_data if c["status"] == "running")
            avg_fps_val   = (
                round(sum(c["fps"] for c in performance_data) / len(performance_data), 2)
                if performance_data else 0.0
            )

            return {
                "period": {
                    "days": days,
                    "from": date_from.isoformat(),
                    "to":   datetime.utcnow().isoformat(),
                },
                "cameras": performance_data,
                "summary": {
                    "total_cameras":    len(performance_data),
                    "running_cameras":  running_count,
                    "total_detections": sum(c["total_detections"] for c in performance_data),
                    "average_fps":      avg_fps_val,
                },
            }

        except Exception as exc:
            logger.error(f"Error analyzing camera performance: {exc}", exc_info=True)
            raise

    # =========================================================================
    # SPRINT 21 — ADI TRENDS
    # =========================================================================

    async def get_adi_trends(
        self,
        db:        AsyncSession,
        animal_id: Optional[int] = None,
        days:      int = 30,
    ) -> Dict[str, Any]:
        """
        ADI ball o'zgarishi trendini qaytaradi.

        Individual jonivor uchun: aniq ADI balli va 8 komponent.
        Herd-wide (animal_id=None): kunlik o'rtacha ADI.

        Args:
            db:        Async database session
            animal_id: Aniq jonivor ID (None = butun ferma)
            days:      Qancha kunlik tarix (1-365)

        Returns:
            Dict: animal_id, animal_tag, data[], stats, period_days

        Raises:
            ValueError: animal_id topilmasa
        """
        logger.info(
            "Generating ADI trends",
            extra={"extra_data": {"animal_id": animal_id, "days": days}},
        )
        try:
            date_from_str = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
            date_to_str   = datetime.utcnow().date().isoformat()

            animal_tag: Optional[str] = None

            if animal_id is not None:
                animal = (await db.execute(
                    select(Animal).where(Animal.id == animal_id)
                )).scalar_one_or_none()
                if animal is None:
                    raise ValueError(f"Animal {animal_id} not found")
                animal_tag = animal.tag_id

            # ADI loglarni o'qiymiz
            query = (
                select(
                    ADILog.calculation_date,
                    func.avg(ADILog.adi_score).label("avg_adi"),
                    func.avg(ADILog.activity_score).label("avg_activity"),
                    func.avg(ADILog.feeding_score).label("avg_feeding"),
                    func.avg(ADILog.drinking_score).label("avg_drinking"),
                    func.avg(ADILog.movement_score).label("avg_movement"),
                    func.avg(ADILog.growth_score).label("avg_growth"),
                    func.avg(ADILog.social_score).label("avg_social"),
                    func.avg(ADILog.sensor_score).label("avg_sensor"),
                    func.avg(ADILog.veterinary_score).label("avg_veterinary"),
                    func.avg(ADILog.data_quality).label("avg_quality"),
                    func.count(ADILog.id).label("animal_count"),
                )
                .where(
                    and_(
                        ADILog.calculation_date >= date_from_str,
                        ADILog.calculation_date <= date_to_str,
                    )
                )
            )

            if animal_id is not None:
                query = query.where(ADILog.animal_id == animal_id)

            query = (
                query
                .group_by(ADILog.calculation_date)
                .order_by(ADILog.calculation_date)
            )

            rows = (await db.execute(query)).all()

            def _safe(val: Any) -> Optional[float]:
                return round(float(val), 2) if val is not None else None

            data_points = [
                {
                    "date":             row.calculation_date,
                    "adi_score":        round(float(row.avg_adi), 2),
                    "category":         ADICategory.from_score(float(row.avg_adi)),
                    "activity_score":   _safe(row.avg_activity),
                    "feeding_score":    _safe(row.avg_feeding),
                    "drinking_score":   _safe(row.avg_drinking),
                    "movement_score":   _safe(row.avg_movement),
                    "growth_score":     _safe(row.avg_growth),
                    "social_score":     _safe(row.avg_social),
                    "sensor_score":     _safe(row.avg_sensor),
                    "veterinary_score": _safe(row.avg_veterinary),
                    "data_quality":     _safe(row.avg_quality),
                    "animal_count":     row.animal_count,
                }
                for row in rows
            ]

            stats = self._calculate_adi_trend_stats(data_points, days)

            return {
                "animal_id":   animal_id,
                "animal_tag":  animal_tag,
                "period_days": days,
                "data":        data_points,
                "stats":       stats,
            }

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Error generating ADI trends: {exc}", exc_info=True)
            raise

    def _calculate_adi_trend_stats(
        self,
        data: List[Dict[str, Any]],
        period_days: int,
    ) -> Dict[str, Any]:
        """
        ADI trend statistikasini hisoblaydi.

        Trend yo'nalishi: oxirgi 7 kun o'rtachasi vs oldingi 7 kun o'rtachasi.
        """
        if not data:
            return {
                "period_days":     period_days,
                "avg_adi":         0.0,
                "min_adi":         0.0,
                "max_adi":         0.0,
                "trend_direction": "insufficient_data",
                "trend_delta":     0.0,
                "days_healthy":    0,
                "days_critical":   0,
            }

        scores = [p["adi_score"] for p in data]

        # Oxirgi 7 kun vs oldingi 7 kun
        recent   = scores[-7:]  if len(scores) >= 7  else scores
        previous = scores[-14:-7] if len(scores) >= 14 else scores[:max(1, len(scores)-7)]

        avg_recent   = sum(recent)   / len(recent)   if recent   else 0.0
        avg_previous = sum(previous) / len(previous) if previous else avg_recent

        delta = avg_recent - avg_previous

        if len(scores) < 3:
            direction = "insufficient_data"
        elif delta > _TREND_STABLE_DELTA:
            direction = "improving"
        elif delta < -_TREND_STABLE_DELTA:
            direction = "declining"
        else:
            direction = "stable"

        return {
            "period_days":     period_days,
            "avg_adi":         round(sum(scores) / len(scores), 2),
            "min_adi":         round(min(scores), 2),
            "max_adi":         round(max(scores), 2),
            "trend_direction": direction,
            "trend_delta":     round(delta, 2),
            "days_healthy":    sum(1 for p in data if p["category"] == "healthy"),
            "days_critical":   sum(1 for p in data if p["category"] == "critical"),
        }

    # =========================================================================
    # SPRINT 21 — GROWTH TRENDS  (chiziqli regressiya)
    # =========================================================================

    async def get_growth_trends(
        self,
        db:        AsyncSession,
        animal_id: Optional[int] = None,
        days:      int = 90,
    ) -> Dict[str, Any]:
        """
        O'sish egri chizig'ini chiziqli regressiya bilan tahlil qiladi.

        Args:
            db:        Async database session
            animal_id: Aniq jonivor (None = butun ferma)
            days:      Tahlil davri (max 365)

        Returns:
            Dict: animal_id, animal_tag, period_days, data[],
                  regression (slope, r2, prognoz), summary

        Notes:
            regression faqat >= 3 o'lchov nuqtasi bo'lganda qaytariladi.
            Prognoz 30 kunlik ekstrapolyatsiya.
        """
        logger.info(
            "Generating growth trends",
            extra={"extra_data": {"animal_id": animal_id, "days": days}},
        )
        try:
            date_from = datetime.utcnow().date() - timedelta(days=days)
            date_to   = datetime.utcnow().date()

            animal_tag: Optional[str] = None

            if animal_id is not None:
                animal = (await db.execute(
                    select(Animal).where(Animal.id == animal_id)
                )).scalar_one_or_none()
                if animal is None:
                    raise ValueError(f"Animal {animal_id} not found")
                animal_tag = animal.tag_id

            query = (
                select(
                    func.date(WeightMeasurement.timestamp).label("date"),
                    func.avg(WeightMeasurement.estimated_weight_kg).label("avg_weight"),
                    func.count(WeightMeasurement.id).label("meas_count"),
                    func.count(distinct(WeightMeasurement.animal_id)).label("animal_count"),
                )
                .where(
                    and_(
                        WeightMeasurement.timestamp >= datetime.combine(date_from, datetime.min.time()),
                        WeightMeasurement.timestamp <  datetime.combine(date_to + timedelta(days=1), datetime.min.time()),
                    )
                )
            )

            if animal_id is not None:
                query = query.where(WeightMeasurement.animal_id == animal_id)

            query = (
                query
                .group_by(func.date(WeightMeasurement.timestamp))
                .order_by(func.date(WeightMeasurement.timestamp))
            )

            rows = (await db.execute(query)).all()

            data_points = [
                {
                    "date":                 str(row.date)[:10],
                    "average_weight_kg":    round(float(row.avg_weight), 2),
                    "bbox_area_normalized": None,   # kamera ma'lumoti keyingi sprint'da
                    "measurement_count":    row.meas_count,
                    "animal_count":         row.animal_count,
                }
                for row in rows
            ]

            regression = self._compute_linear_regression(data_points)

            # Xulosa
            weights      = [p["average_weight_kg"] for p in data_points]
            summary: Dict[str, Any] = {}
            if weights:
                summary["first_weight_kg"] = weights[0]
                summary["last_weight_kg"]  = weights[-1]
                summary["total_gain_kg"]   = round(weights[-1] - weights[0], 2)
                summary["data_points"]     = len(weights)

            return {
                "animal_id":   animal_id,
                "animal_tag":  animal_tag,
                "period_days": days,
                "data":        data_points,
                "regression":  regression,
                "summary":     summary,
            }

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Error generating growth trends: {exc}", exc_info=True)
            raise

    def _compute_linear_regression(
        self,
        data_points: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """
        Vazn ma'lumotlariga chiziqli regressiya qo'llaydi.

        Args:
            data_points: date va average_weight_kg bo'lgan list

        Returns:
            Dict: slope_kg_per_day, r_squared, projected_weight_30d, ...
            None: agar yetarli nuqta bo'lmasa

        Algorithm:
            x = kunlar indeksi (0, 1, 2, ..., n-1)
            y = o'rtacha vazn (kg)
            numpy.polyfit(x, y, 1) → [slope, intercept]
            R² = 1 - SS_res / SS_tot
        """
        if len(data_points) < _MIN_REGRESSION_POINTS:
            return None

        try:
            x   = np.arange(len(data_points), dtype=float)
            y   = np.array([p["average_weight_kg"] for p in data_points], dtype=float)

            coeffs       = np.polyfit(x, y, 1)
            slope        = float(coeffs[0])      # kg/kun
            intercept    = float(coeffs[1])

            # R² hisoblash
            y_pred  = np.polyval(coeffs, x)
            ss_res  = float(np.sum((y - y_pred) ** 2))
            ss_tot  = float(np.sum((y - np.mean(y)) ** 2))
            r2      = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

            # 30 kunlik prognoz
            last_weight   = float(y[-1])
            projected_30d = round(last_weight + slope * 30, 2)

            return {
                "slope_kg_per_day":    round(slope, 4),
                "slope_kg_per_week":   round(slope * 7, 3),
                "slope_kg_per_month":  round(slope * 30, 2),
                "r_squared":           round(max(0.0, r2), 4),
                "projected_weight_30d": max(0.0, projected_30d),
                "data_points_used":    len(data_points),
            }

        except Exception as exc:
            logger.warning(f"Linear regression failed: {exc}")
            return None

    # =========================================================================
    # SPRINT 21 — BEHAVIOR TRENDS
    # =========================================================================

    async def get_behavior_trends(
        self,
        db:        AsyncSession,
        animal_id: Optional[int] = None,
        days:      int = 30,
    ) -> Dict[str, Any]:
        """
        Xatti-harakat komponentlari trendini qaytaradi.

        ADILog dagi 8 komponent ballini kunlik grafik uchun taqdim etadi.
        Har komponent uchun trend yo'nalishi ham hisoblanadi.

        Args:
            db:        Async database session
            animal_id: Aniq jonivor (None = butun ferma)
            days:      Tahlil davri

        Returns:
            Dict: animal_id, animal_tag, period_days, data[],
                  component_summaries[], weakest, strongest
        """
        logger.info("Generating behavior trends")
        try:
            date_from_str = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
            date_to_str   = datetime.utcnow().date().isoformat()

            animal_tag: Optional[str] = None

            if animal_id is not None:
                animal = (await db.execute(
                    select(Animal).where(Animal.id == animal_id)
                )).scalar_one_or_none()
                if animal is None:
                    raise ValueError(f"Animal {animal_id} not found")
                animal_tag = animal.tag_id

            query = (
                select(
                    ADILog.calculation_date,
                    func.avg(ADILog.activity_score).label("activity"),
                    func.avg(ADILog.feeding_score).label("feeding"),
                    func.avg(ADILog.drinking_score).label("drinking"),
                    func.avg(ADILog.movement_score).label("movement"),
                    func.avg(ADILog.growth_score).label("growth"),
                    func.avg(ADILog.social_score).label("social"),
                    func.avg(ADILog.sensor_score).label("sensor"),
                    func.avg(ADILog.veterinary_score).label("veterinary"),
                    func.count(ADILog.id).label("animal_count"),
                )
                .where(
                    and_(
                        ADILog.calculation_date >= date_from_str,
                        ADILog.calculation_date <= date_to_str,
                    )
                )
            )

            if animal_id is not None:
                query = query.where(ADILog.animal_id == animal_id)

            query = (
                query
                .group_by(ADILog.calculation_date)
                .order_by(ADILog.calculation_date)
            )

            rows = (await db.execute(query)).all()

            def _s(val: Any) -> Optional[float]:
                return round(float(val), 2) if val is not None else None

            data_points = []
            for row in rows:
                act = _s(row.activity)
                fed = _s(row.feeding)
                mov = _s(row.movement)

                # Kompozit xatti-harakat: activity(40%) + feeding(35%) + movement(25%)
                components_present = [v for v in [act, fed, mov] if v is not None]
                composite = (
                    round(sum(components_present) / len(components_present), 2)
                    if components_present else None
                )

                data_points.append({
                    "date":               row.calculation_date,
                    "activity_score":     act,
                    "feeding_score":      fed,
                    "drinking_score":     _s(row.drinking),
                    "movement_score":     mov,
                    "growth_score":       _s(row.growth),
                    "social_score":       _s(row.social),
                    "sensor_score":       _s(row.sensor),
                    "veterinary_score":   _s(row.veterinary),
                    "composite_behavior": composite,
                    "animal_count":       row.animal_count,
                })

            # Komponent xulosalari
            component_summaries = self._build_component_summaries(data_points)

            weakest   = min(component_summaries, key=lambda c: c["average"], default=None)
            strongest = max(component_summaries, key=lambda c: c["average"], default=None)

            return {
                "animal_id":            animal_id,
                "animal_tag":           animal_tag,
                "period_days":          days,
                "data":                 data_points,
                "component_summaries":  component_summaries,
                "weakest_component":    weakest["component"]   if weakest   else None,
                "strongest_component":  strongest["component"] if strongest else None,
            }

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Error generating behavior trends: {exc}", exc_info=True)
            raise

    def _build_component_summaries(
        self,
        data: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Har bir xatti-harakat komponenti uchun xulosa va trend hisoблайди.
        """
        _COMPONENTS = [
            "activity_score", "feeding_score", "drinking_score",
            "movement_score", "growth_score",  "social_score",
            "sensor_score",   "veterinary_score",
        ]

        summaries = []
        for comp in _COMPONENTS:
            values = [
                p[comp] for p in data if p.get(comp) is not None
            ]
            if not values:
                continue

            avg     = sum(values) / len(values)
            recent  = values[-7:]  if len(values) >= 7  else values
            prev    = values[-14:-7] if len(values) >= 14 else values[:max(1, len(values)-7)]

            avg_recent = sum(recent) / len(recent) if recent else avg
            avg_prev   = sum(prev) / len(prev)     if prev   else avg_recent
            delta      = avg_recent - avg_prev

            if   delta > _TREND_STABLE_DELTA:  trend = "improving"
            elif delta < -_TREND_STABLE_DELTA: trend = "declining"
            else:                              trend = "stable"

            summaries.append({
                "component": comp.replace("_score", ""),
                "average":   round(avg, 2),
                "trend":     trend,
                "delta":     round(delta, 2),
            })

        return summaries

    # =========================================================================
    # SPRINT 22 — ANIMAL COMPARISON
    # =========================================================================

    async def compare_animals(
        self,
        db:         AsyncSession,
        animal_ids: List[int],
        days:       int = 30,
    ) -> Dict[str, Any]:
        """
        Bir nechta jonivorni yonma-yon taqqoslaydi.

        Args:
            db:         Async database session
            animal_ids: Taqqoslanadigan jonivorlar ID ro'yxati (maks 10)
            days:       Taqqoslash davri

        Returns:
            Dict: period_days, animals[], best_adi, worst_adi, ...

        Raises:
            ValueError: animal_ids bo'sh yoki > 10 bo'lsa
        """
        if not animal_ids:
            raise ValueError("animal_ids bo'sh bo'lishi mumkin emas")
        if len(animal_ids) > 10:
            raise ValueError("Bir vaqtda maksimal 10 ta jonivor taqqoslanadi")

        logger.info(f"Comparing {len(animal_ids)} animals over {days} days")

        try:
            date_from_str = (datetime.utcnow().date() - timedelta(days=days)).isoformat()
            date_from_dt  = datetime.utcnow() - timedelta(days=days)

            animals_data = []
            for aid in animal_ids:
                animal = (await db.execute(
                    select(Animal).where(Animal.id == aid)
                )).scalar_one_or_none()
                if animal is None:
                    raise ValueError(f"Animal {aid} not found")

                # ADI ma'lumotlari
                adi_rows = (await db.execute(
                    select(
                        func.avg(ADILog.adi_score).label("avg_adi"),
                        func.max(ADILog.adi_score).label("latest_adi"),
                    )
                    .where(
                        and_(
                            ADILog.animal_id == aid,
                            ADILog.calculation_date >= date_from_str,
                        )
                    )
                )).one_or_none()

                # ADI trendi
                adi_trend_data = (await db.execute(
                    select(ADILog.adi_score, ADILog.calculation_date)
                    .where(
                        and_(
                            ADILog.animal_id == aid,
                            ADILog.calculation_date >= date_from_str,
                        )
                    )
                    .order_by(ADILog.calculation_date)
                )).all()

                adi_trend_direction = None
                if len(adi_trend_data) >= 4:
                    scores    = [r.adi_score for r in adi_trend_data]
                    recent_   = scores[-3:]
                    prev_     = scores[:3]
                    delta_    = (sum(recent_) / 3) - (sum(prev_) / 3)
                    if   delta_ > _TREND_STABLE_DELTA:  adi_trend_direction = "improving"
                    elif delta_ < -_TREND_STABLE_DELTA: adi_trend_direction = "declining"
                    else:                               adi_trend_direction = "stable"

                # Oxirgi vazn
                weight_rows = (await db.execute(
                    select(WeightMeasurement.estimated_weight_kg, WeightMeasurement.timestamp)
                    .where(WeightMeasurement.animal_id == aid)
                    .order_by(desc(WeightMeasurement.timestamp))
                    .limit(2)
                )).all()

                latest_weight    = float(weight_rows[0].estimated_weight_kg) if weight_rows else None
                previous_weight  = float(weight_rows[1].estimated_weight_kg) if len(weight_rows) > 1 else None
                weight_change_kg = None
                weight_change_pct = None
                if latest_weight and previous_weight and previous_weight > 0:
                    weight_change_kg  = round(latest_weight - previous_weight, 2)
                    weight_change_pct = round((weight_change_kg / previous_weight) * 100, 2)

                # Deteksiya soni
                det_count = (await db.execute(
                    select(func.count(Detection.id))
                    .where(
                        and_(
                            Detection.animal_id == aid,
                            Detection.timestamp >= date_from_dt,
                        )
                    )
                )).scalar() or 0

                # Xatti-harakat o'rtachalari
                beh_row = (await db.execute(
                    select(
                        func.avg(ADILog.activity_score).label("avg_act"),
                        func.avg(ADILog.feeding_score).label("avg_feed"),
                    )
                    .where(
                        and_(
                            ADILog.animal_id == aid,
                            ADILog.calculation_date >= date_from_str,
                        )
                    )
                )).one_or_none()

                # Aktiv alertlar soni
                alert_count = (await db.execute(
                    select(func.count(AlertModel.id))
                    .where(
                        and_(
                            AlertModel.animal_id == aid,
                            AlertModel.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                        )
                    )
                )).scalar() or 0

                # Xavf darajasi (ADI asosida)
                avg_adi_val = float(adi_rows.avg_adi) if adi_rows and adi_rows.avg_adi else None
                risk = self._adi_to_risk_level(avg_adi_val, alert_count)

                animals_data.append({
                    "animal_id":             aid,
                    "tag_id":                animal.tag_id,
                    "species":               animal.species.value if hasattr(animal.species, "value") else str(animal.species),
                    "status":                animal.status.value  if hasattr(animal.status, "value")  else str(animal.status),
                    "average_adi":           round(float(adi_rows.avg_adi), 2) if adi_rows and adi_rows.avg_adi else None,
                    "latest_adi":            round(float(adi_rows.latest_adi), 2) if adi_rows and adi_rows.latest_adi else None,
                    "adi_trend":             adi_trend_direction,
                    "latest_weight_kg":      round(latest_weight, 2) if latest_weight else None,
                    "weight_change_kg":      weight_change_kg,
                    "weight_change_pct":     weight_change_pct,
                    "detections_period":     det_count,
                    "detection_rate_per_day": round(det_count / max(days, 1), 2),
                    "avg_activity_score":    round(float(beh_row.avg_act), 2) if beh_row and beh_row.avg_act else None,
                    "avg_feeding_score":     round(float(beh_row.avg_feed), 2) if beh_row and beh_row.avg_feed else None,
                    "risk_level":            risk,
                    "active_alerts_count":   alert_count,
                })

            # Taqqoslash xulosalari
            animals_with_adi = [a for a in animals_data if a["average_adi"] is not None]
            best_adi  = max(animals_with_adi, key=lambda a: a["average_adi"], default=None)
            worst_adi = min(animals_with_adi, key=lambda a: a["average_adi"], default=None)
            heaviest  = max([a for a in animals_data if a["latest_weight_kg"]], key=lambda a: a["latest_weight_kg"], default=None)
            most_active = max(animals_data, key=lambda a: a["detections_period"], default=None)

            return {
                "period_days":           days,
                "animals":               animals_data,
                "best_adi_animal":       best_adi["tag_id"]    if best_adi    else None,
                "worst_adi_animal":      worst_adi["tag_id"]   if worst_adi   else None,
                "highest_weight_animal": heaviest["tag_id"]    if heaviest    else None,
                "most_active_animal":    most_active["tag_id"] if most_active else None,
            }

        except ValueError:
            raise
        except Exception as exc:
            logger.error(f"Error comparing animals: {exc}", exc_info=True)
            raise

    def _adi_to_risk_level(self, avg_adi: Optional[float], alert_count: int) -> str:
        """ADI va alert soni asosida xavf darajasini aniqlaydi."""
        if avg_adi is None:
            return "moderate" if alert_count > 0 else "low"
        if avg_adi < _ADI_WARNING_THRESHOLD or alert_count >= 3:
            return "critical"
        if avg_adi < _ADI_AVERAGE_THRESHOLD or alert_count >= 1:
            return "high"
        if avg_adi < _ADI_HEALTHY_THRESHOLD:
            return "moderate"
        return "low"

    # =========================================================================
    # SPRINT 22 — PERIOD COMPARISON
    # =========================================================================

    async def compare_periods(
        self,
        db:       AsyncSession,
        days:     int = 30,
    ) -> Dict[str, Any]:
        """
        Joriy davr va oldingi davrni taqqoslaydi.

        Masalan, days=30 bo'lsa:
            joriy = so'nggi 30 kun
            oldingi = 30-60 kun avval

        Args:
            db:   Async database session
            days: Har bir davr uzunligi (kunlar)

        Returns:
            Dict: current_period, previous_period, deltas[],
                  overall_assessment, key_changes[]
        """
        logger.info(f"Comparing periods: {days} days each")
        try:
            now           = datetime.utcnow()
            curr_end      = now.date()
            curr_start    = curr_end - timedelta(days=days - 1)
            prev_end      = curr_start - timedelta(days=1)
            prev_start    = prev_end - timedelta(days=days - 1)

            curr = await self._get_period_metrics(db, curr_start, curr_end,  f"So'nggi {days} kun")
            prev = await self._get_period_metrics(db, prev_start, prev_end,  f"Oldingi {days} kun")

            deltas     = self._build_period_deltas(curr, prev)
            assessment = self._assess_periods(curr, prev)
            key_changes = self._summarize_key_changes(deltas)

            return {
                "current_period":   curr,
                "previous_period":  prev,
                "deltas":           deltas,
                "overall_assessment": assessment,
                "key_changes":      key_changes,
            }

        except Exception as exc:
            logger.error(f"Error comparing periods: {exc}", exc_info=True)
            raise

    async def _get_period_metrics(
        self,
        db:          AsyncSession,
        date_from:   date,
        date_to:     date,
        period_label: str,
    ) -> Dict[str, Any]:
        """Bitta davr uchun asosiy metrikalar to'plamini hisoblaydi."""
        dt_from  = datetime(date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc)
        dt_to    = datetime(date_to.year,   date_to.month,   date_to.day,   tzinfo=timezone.utc) + timedelta(days=1)
        date_from_str = date_from.isoformat()
        date_to_str   = date_to.isoformat()
        days_count = (date_to - date_from).days + 1

        # Deteksiya
        det_row = (await db.execute(
            select(
                func.count(Detection.id).label("total"),
                func.avg(Detection.confidence).label("avg_conf"),
            )
            .where(and_(Detection.timestamp >= dt_from, Detection.timestamp < dt_to))
        )).one_or_none()

        total_det = det_row.total if det_row else 0
        avg_conf  = float(det_row.avg_conf) if det_row and det_row.avg_conf else None

        # ADI
        adi_row = (await db.execute(
            select(
                func.avg(ADILog.adi_score).label("avg_adi"),
                func.count(case((ADILog.category == "healthy",  1))).label("healthy_cnt"),
                func.count(case((ADILog.category == "critical", 1))).label("critical_cnt"),
            )
            .where(
                and_(
                    ADILog.calculation_date >= date_from_str,
                    ADILog.calculation_date <= date_to_str,
                )
            )
        )).one_or_none()

        avg_adi    = float(adi_row.avg_adi) if adi_row and adi_row.avg_adi else None
        healthy_c  = adi_row.healthy_cnt  if adi_row else 0
        critical_c = adi_row.critical_cnt if adi_row else 0

        # Vazn
        weight_avg = (await db.execute(
            select(func.avg(WeightMeasurement.estimated_weight_kg))
            .where(
                and_(
                    WeightMeasurement.timestamp >= dt_from,
                    WeightMeasurement.timestamp <  dt_to,
                )
            )
        )).scalar()

        # Alertlar
        alert_row = (await db.execute(
            select(
                func.count(AlertModel.id).label("total"),
                func.count(case((AlertModel.severity == AlertSeverity.CRITICAL, 1))).label("crit"),
            )
            .where(
                and_(
                    AlertModel.created_at >= dt_from,
                    AlertModel.created_at <  dt_to,
                )
            )
        )).one_or_none()

        return {
            "period_label":       period_label,
            "date_from":          date_from.isoformat(),
            "date_to":            date_to.isoformat(),
            "total_detections":   total_det,
            "avg_detections_per_day": round(total_det / days_count, 2) if days_count else 0.0,
            "avg_confidence":     round(avg_conf, 3)                   if avg_conf  else None,
            "avg_adi":            round(avg_adi, 2)                    if avg_adi   else None,
            "animals_in_healthy": int(healthy_c),
            "animals_in_critical":int(critical_c),
            "avg_weight_kg":      round(float(weight_avg), 2)          if weight_avg else None,
            "total_alerts":       int(alert_row.total) if alert_row else 0,
            "critical_alerts":    int(alert_row.crit)  if alert_row else 0,
        }

    def _build_period_deltas(
        self,
        curr: Dict[str, Any],
        prev: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Ikki davr o'rtasidagi delta metrikalar ro'yxatini tuzadi."""
        _METRICS = [
            ("total_detections",     "Jami deteksiyalar",        True),
            ("avg_detections_per_day","Kunlik o'rtacha deteksiya", True),
            ("avg_adi",              "O'rtacha ADI",             True),
            ("animals_in_healthy",   "Healthy jonivorilar soni",  True),
            ("animals_in_critical",  "Critical jonivorilar soni", False),
            ("avg_weight_kg",        "O'rtacha vazn (kg)",        True),
            ("total_alerts",         "Jami alertlar",             False),
            ("critical_alerts",      "Kritik alertlar",           False),
        ]

        deltas = []
        for key, label, higher_is_better in _METRICS:
            c_val = curr.get(key)
            p_val = prev.get(key)

            if c_val is None and p_val is None:
                continue

            abs_change = (
                round(float(c_val) - float(p_val), 4)
                if c_val is not None and p_val is not None
                else None
            )
            pct_change = (
                round((abs_change / float(p_val)) * 100, 2)
                if abs_change is not None and p_val and float(p_val) != 0
                else None
            )

            if abs_change is None or abs_change == 0:
                direction = "unchanged"
            elif abs_change > 0:
                direction = "up"
            else:
                direction = "down"

            is_positive = (
                (direction == "up"   and     higher_is_better) or
                (direction == "down" and not higher_is_better)
            )

            deltas.append({
                "metric":             label,
                "current_value":      c_val,
                "previous_value":     p_val,
                "absolute_change":    abs_change,
                "percentage_change":  pct_change,
                "direction":          direction,
                "is_positive_change": is_positive,
            })

        return deltas

    def _assess_periods(
        self, curr: Dict[str, Any], prev: Dict[str, Any]
    ) -> str:
        """
        Umumiy holat bahosi.

        Qaytarish qiymatlari (test kutgan to'plam bilan moslashtirilgan):
            "improving"         — ikkala davrda ham ma'lumot bor, yaxshilangan
            "declining"         — ikkala davrda ham ma'lumot bor, yomonlashgan
            "stable"            — ikkala davrda ham ma'lumot bor, farq kichik
            "mixed"             — ba'zi ko'rsatkichlar yaxshi, ba'zilari yomon
            "no_data"           — ikkala davrda ham hech qanday ma'lumot yo'q
            "insufficient_data" — faqat bitta davrda ma'lumot bor
        """
        has_curr_data = bool(
            curr.get("avg_adi") or curr.get("total_detections", 0) > 0
        )
        has_prev_data = bool(
            prev.get("avg_adi") or prev.get("total_detections", 0) > 0
        )

        # Ma'lumot yo'q holatlari
        if not has_curr_data and not has_prev_data:
            return "no_data"
        if not has_curr_data or not has_prev_data:
            return "insufficient_data"

        score = 0
        signals: list[int] = []

        # ADI ko'rsatkich
        if curr.get("avg_adi") and prev.get("avg_adi"):
            adi_delta = curr["avg_adi"] - prev["avg_adi"]
            sig = 1 if adi_delta > 2 else (-1 if adi_delta < -2 else 0)
            score += sig
            signals.append(sig)

        # Deteksiya
        p_det = prev.get("total_detections", 0)
        c_det = curr.get("total_detections", 0)
        if p_det > 0:
            if   c_det > p_det * 1.05:  sig = 1
            elif c_det < p_det * 0.95:  sig = -1
            else:                       sig = 0
        else:
            sig = 1 if c_det > 0 else 0
        score += sig
        signals.append(sig)

        # Critical alertlar (kami yaxshi)
        c_crit = curr.get("critical_alerts", 0)
        p_crit = prev.get("critical_alerts", 0)
        if   c_crit < p_crit:  sig = 1
        elif c_crit > p_crit:  sig = -1
        else:                  sig = 0
        score += sig
        signals.append(sig)

        # "mixed": qarama-qarshi signallar bor
        non_zero = [s for s in signals if s != 0]
        if len(non_zero) >= 2 and any(s > 0 for s in non_zero) and any(s < 0 for s in non_zero):
            return "mixed"

        if   score >= 2:   return "improving"
        elif score <= -2:  return "declining"
        return "stable"

    def _summarize_key_changes(
        self, deltas: List[Dict[str, Any]]
    ) -> List[str]:
        """Eng muhim 3 ta o'zgarishni matn shaklida qaytaradi."""
        significant = sorted(
            [d for d in deltas if d.get("percentage_change") is not None],
            key=lambda d: abs(d["percentage_change"] or 0),
            reverse=True,
        )[:3]

        texts = []
        for d in significant:
            pct  = d["percentage_change"]
            sign = "+" if d["direction"] == "up" else ""
            icon = "✅" if d["is_positive_change"] else "⚠️"
            texts.append(
                f"{icon} {d['metric']}: {sign}{pct:.1f}% "
                f"({d['previous_value']} → {d['current_value']})"
            )
        return texts

    # =========================================================================
    # SPRINT 23 — HERD STATISTICS
    # =========================================================================

    async def get_herd_statistics(self, db: AsyncSession) -> Dict[str, Any]:
        """
        Podaning to'liq statistik panoramasini qaytaradi.

        KPI'lar, taqsimotlar, sog'liq ko'rsatkichlari.

        Args:
            db: Async database session

        Returns:
            Dict: timestamp, total/active, species_breakdown,
                  adi_distribution, weight_distribution, age_distribution,
                  kpis (health_score, coverage, missing, etc.)
        """
        logger.info("Generating herd statistics")
        try:
            now  = datetime.utcnow()
            today_str     = now.date().isoformat()
            week_ago_str  = (now.date() - timedelta(days=7)).isoformat()
            month_ago_str = (now.date() - timedelta(days=30)).isoformat()
            week_ago_dt   = now - timedelta(days=7)
            month_ago_dt  = now - timedelta(days=30)

            # Jami jonivorilar
            all_animals = (await db.execute(select(Animal))).scalars().all()
            active_animals = [a for a in all_animals if a.status == AnimalStatus.ACTIVE]

            total   = len(all_animals)
            active  = len(active_animals)

            # Tur bo'yicha taqsimot
            species_dict: Dict[str, Dict] = {}
            for a in active_animals:
                sp = a.species.value if hasattr(a.species, "value") else str(a.species)
                species_dict.setdefault(sp, {"count": 0, "weights": [], "adis": []})
                species_dict[sp]["count"] += 1

            # Har bir tur uchun o'rtacha vazn va ADI
            if active_animals:
                w_rows = (await db.execute(
                    select(
                        Animal.species,
                        func.avg(WeightMeasurement.estimated_weight_kg).label("avg_w"),
                    )
                    .select_from(Animal)
                    .join(WeightMeasurement, Animal.id == WeightMeasurement.animal_id)
                    .where(Animal.status == AnimalStatus.ACTIVE)
                    .group_by(Animal.species)
                )).all()
                for row in w_rows:
                    sp = row.species.value if hasattr(row.species, "value") else str(row.species)
                    if sp in species_dict:
                        species_dict[sp]["avg_weight"] = round(float(row.avg_w), 2)

            species_breakdown = [
                {
                    "species":       sp,
                    "count":         d["count"],
                    "percentage":    round(d["count"] / active * 100, 1) if active else 0.0,
                    "avg_weight_kg": d.get("avg_weight"),
                    "avg_adi":       None,
                }
                for sp, d in species_dict.items()
            ]

            # ADI taqsimoti (oxirgi hisoblangan)
            latest_adi_subq = (
                select(ADILog.animal_id, func.max(ADILog.calculation_date).label("max_date"))
                .group_by(ADILog.animal_id)
                .subquery()
            )
            latest_adi_rows = (await db.execute(
                select(ADILog.animal_id, ADILog.adi_score, ADILog.category)
                .join(
                    latest_adi_subq,
                    and_(
                        ADILog.animal_id == latest_adi_subq.c.animal_id,
                        ADILog.calculation_date == latest_adi_subq.c.max_date,
                    )
                )
            )).all()

            animals_with_adi = {r.animal_id for r in latest_adi_rows}
            adi_cats = {"healthy": 0, "average": 0, "warning": 0, "critical": 0}
            adi_scores_all = []

            for r in latest_adi_rows:
                cat = r.category if isinstance(r.category, str) else r.category.value
                if cat in adi_cats:
                    adi_cats[cat] += 1
                adi_scores_all.append(r.adi_score)

            no_adi_count = active - len(animals_with_adi)

            adi_distribution = {
                **{k: v for k, v in adi_cats.items()},
                "no_data":       max(0, no_adi_count),
                "healthy_pct":   round(adi_cats["healthy"]  / active * 100, 1) if active else 0.0,
                "critical_pct":  round(adi_cats["critical"] / active * 100, 1) if active else 0.0,
            }

            # Vazn taqsimoti
            weight_buckets = [
                {"range_label": "0-100kg",   "min": 0,   "max": 100},
                {"range_label": "100-200kg",  "min": 100, "max": 200},
                {"range_label": "200-300kg",  "min": 200, "max": 300},
                {"range_label": "300-400kg",  "min": 300, "max": 400},
                {"range_label": "400kg+",     "min": 400, "max": 99999},
            ]

            latest_w_subq = (
                select(WeightMeasurement.animal_id, func.max(WeightMeasurement.timestamp).label("max_ts"))
                .group_by(WeightMeasurement.animal_id)
                .subquery()
            )
            latest_w_rows = (await db.execute(
                select(WeightMeasurement.animal_id, WeightMeasurement.estimated_weight_kg)
                .join(
                    latest_w_subq,
                    and_(
                        WeightMeasurement.animal_id == latest_w_subq.c.animal_id,
                        WeightMeasurement.timestamp == latest_w_subq.c.max_ts,
                    )
                )
            )).all()

            weight_map = {r.animal_id: r.estimated_weight_kg for r in latest_w_rows}
            weight_buckets_result = []
            for bucket in weight_buckets:
                cnt = sum(
                    1 for aid in [a.id for a in active_animals]
                    if weight_map.get(aid) is not None
                    and bucket["min"] <= float(weight_map[aid]) < bucket["max"]
                )
                weight_buckets_result.append({
                    "range_label": bucket["range_label"],
                    "count":       cnt,
                    "percentage":  round(cnt / active * 100, 1) if active else 0.0,
                })

            # Yosh taqsimoti
            age_buckets = self._build_age_distribution(active_animals)

            # KPI'lar
            # 1. Umumiy sog'liq balli
            overall_health = (
                round(sum(adi_scores_all) / len(adi_scores_all), 2)
                if adi_scores_all else 0.0
            )

            # 2. Detection coverage (oxirgi 7 kunda ko'ringan)
            seen_animal_ids = set(
                (await db.execute(
                    select(distinct(Detection.animal_id))
                    .where(
                        and_(
                            Detection.animal_id.is_not(None),
                            Detection.timestamp >= week_ago_dt,
                        )
                    )
                )).scalars().all()
            )
            coverage_pct = round(len(seen_animal_ids) / active * 100, 1) if active else 0.0

            # 3. Kunlik o'rtacha deteksiya (oxirgi 7 kun)
            total_det_7d = (await db.execute(
                select(func.count(Detection.id))
                .where(Detection.timestamp >= week_ago_dt)
            )).scalar() or 0
            avg_daily_det = round(total_det_7d / 7, 2)

            # 4. Diqqat kerak jonivorlar
            needing_attention = adi_cats["warning"] + adi_cats["critical"]

            # 5. 7 kundan beri ko'rinmagan
            active_ids_set = {a.id for a in active_animals}
            missing_7d     = len(active_ids_set - seen_animal_ids)

            # 6. O'rtacha vazn
            all_weights = list(weight_map.values())
            avg_weight  = round(sum(float(w) for w in all_weights) / len(all_weights), 2) if all_weights else None

            # 7. So'nggi 30 kunda jami vazn o'sishi
            growth_row = (await db.execute(
                select(
                    func.sum(WeightMeasurement.estimated_weight_kg).label("sum_w"),
                    func.count(WeightMeasurement.id).label("cnt"),
                )
                .where(WeightMeasurement.timestamp >= month_ago_dt)
            )).one_or_none()

            total_weight_gain: Optional[float] = None
            if growth_row and growth_row.cnt and growth_row.cnt >= 2:
                # Taxminiy: oxirgi va birinchi o'lchov farqi × jonivorlar soni
                total_weight_gain = round(
                    (len(all_weights) * avg_weight if avg_weight else 0) - 
                    (float(growth_row.sum_w) / growth_row.cnt * active),
                    2,
                )

            return {
                "timestamp":          now.isoformat(),
                "total_animals":      total,
                "active_animals":     active,
                "species_breakdown":  species_breakdown,
                "adi_distribution":   adi_distribution,
                "weight_distribution": weight_buckets_result,
                "age_distribution":   age_buckets,
                "kpis": {
                    "overall_health_score":    overall_health,
                    "detection_coverage_pct":  coverage_pct,
                    "avg_daily_detections":    avg_daily_det,
                    "animals_needing_attention": needing_attention,
                    "animals_missing_7d":      missing_7d,
                    "avg_weight_kg":           avg_weight,
                    "total_weight_gain_kg":    total_weight_gain,
                    "feed_efficiency_index":   await self._compute_feed_efficiency_index(
                        db, month_ago_dt, active
                    ),
                },
            }

        except Exception as exc:
            logger.error(f"Error generating herd statistics: {exc}", exc_info=True)
            raise

    async def _compute_feed_efficiency_index(
        self,
        db:             AsyncSession,
        since:          datetime,
        active_count:   int,
    ) -> Optional[float]:
        """
        Feed Efficiency Index (FEI) hisoblash — Sprint 21-24 KPI.

        FORMULA:
            FEI = total_weight_gain_kg / total_feed_consumed_kg

        TALQIN:
            FEI > 0.15 → yaxshi (100 kg yem → 15+ kg go'sht)
            FEI 0.08–0.15 → o'rtacha
            FEI < 0.08 → past samaradorlik

        Ma'lumot yo'q bo'lsa (feed yozuvlari kiritilmagan):
            None qaytaradi — frontend "N/A" ko'rsatadi.

        Args:
            db:           Async session
            since:        Hisob boshlanish vaqti (odatda 30 kun oldin)
            active_count: Aktiv jonivorlar soni (log uchun)

        Returns:
            FEI float (2 xona) yoki None
        """
        try:
            # Jami iste'mol qilingan ozuqa (kg) — davr ichida
            feed_row = (await db.execute(
                select(func.sum(FeedRecord.quantity_kg).label("total_feed"))
                .where(FeedRecord.fed_at >= since)
            )).one_or_none()

            total_feed_kg: Optional[float] = (
                float(feed_row.total_feed) if feed_row and feed_row.total_feed else None
            )

            # Ma'lumot kiritilmagan bo'lsa — None qaytaramiz
            if not total_feed_kg or total_feed_kg <= 0:
                return None

            # Vazn o'sishi: davr boshidagi va oxiridagi o'rtacha vaznlar farqi × jonivorlar soni
            # Har bir aktiv jonivor uchun birinchi va oxirgi vazn o'lchovini olamiz
            earliest_w = (await db.execute(
                select(
                    WeightMeasurement.animal_id,
                    func.min(WeightMeasurement.estimated_weight_kg).label("w_early"),
                )
                .join(Animal, Animal.id == WeightMeasurement.animal_id)
                .where(
                    and_(
                        Animal.status == AnimalStatus.ACTIVE,
                        WeightMeasurement.timestamp >= since,
                    )
                )
                .group_by(WeightMeasurement.animal_id)
            )).all()

            latest_w = (await db.execute(
                select(
                    WeightMeasurement.animal_id,
                    func.max(WeightMeasurement.estimated_weight_kg).label("w_late"),
                )
                .join(Animal, Animal.id == WeightMeasurement.animal_id)
                .where(
                    and_(
                        Animal.status == AnimalStatus.ACTIVE,
                        WeightMeasurement.timestamp >= since,
                    )
                )
                .group_by(WeightMeasurement.animal_id)
            )).all()

            early_map = {r.animal_id: float(r.w_early) for r in earliest_w}
            late_map  = {r.animal_id: float(r.w_late)  for r in latest_w}

            # Faqat ikkalasi mavjud bo'lgan jonivorlar bo'yicha gain hisoblanadi
            total_gain_kg = sum(
                late_map[aid] - early_map[aid]
                for aid in early_map
                if aid in late_map and late_map[aid] > early_map[aid]
            )

            if total_gain_kg <= 0:
                return None

            fei = total_gain_kg / total_feed_kg
            return round(fei, 4)

        except Exception as exc:
            logger.warning(f"FEI hisoblashda xato: {exc}")
            return None

    def _build_age_distribution(self, animals: List[Any]) -> List[Dict[str, Any]]:
        """Jonivorlarni yosh bo'yicha guruhlaydi."""
        age_buckets = {
            "0-6 oy":   0,
            "6-12 oy":  0,
            "1-2 yil":  0,
            "2-4 yil":  0,
            "4+ yil":   0,
            "Noma'lum": 0,
        }
        now  = datetime.utcnow()
        total = len(animals)

        for a in animals:
            if a.birth_date is None:
                age_buckets["Noma'lum"] += 1
                continue
            birth = a.birth_date
            if hasattr(birth, "replace"):
                birth = birth.replace(tzinfo=None)
            months = (now - birth).days / 30.44

            if   months < 6:   age_buckets["0-6 oy"]  += 1
            elif months < 12:  age_buckets["6-12 oy"] += 1
            elif months < 24:  age_buckets["1-2 yil"] += 1
            elif months < 48:  age_buckets["2-4 yil"] += 1
            else:              age_buckets["4+ yil"]  += 1

        return [
            {
                "range_label": label,
                "count":       count,
                "percentage":  round(count / total * 100, 1) if total else 0.0,
            }
            for label, count in age_buckets.items()
        ]

    # =========================================================================
    # SPRINT 24 — AUTOMATED INSIGHTS
    # =========================================================================

    async def get_automated_insights(
        self,
        db:   AsyncSession,
        days: int = 14,
    ) -> Dict[str, Any]:
        """
        Qoidaga asoslangan avtomatik tushunchalar (insights) generatsiya qiladi.

        Deterministik qoidalar asosida real ma'lumotlardan
        amaliy tavsiyalar yaratadi.

        Args:
            db:   Async database session
            days: Tahlil davri (kunlar)

        Returns:
            Dict: generated_at, insights[], summary, analysis_period_days,
                  animals_analyzed

        Categories:
            health           — ADI pasayish, kritik jonivorilar
            growth           — O'sish sekinlashuvi / to'xtashi
            behavior         — Faollik o'zgarishi
            detection        — Ko'rinmaslik, past confidence
            feeding          — Oziqlantirish anomaliyalari
            alert_pattern    — Takroriy alertlar
            herd_trend       — Poda darajasidagi trendlar
            individual_spotlight — E'tiborga sazovor jonivorlar
        """
        logger.info(f"Generating automated insights for {days} days")
        try:
            now           = datetime.utcnow()
            date_from_str = (now.date() - timedelta(days=days)).isoformat()
            date_to_str   = now.date().isoformat()
            date_from_dt  = now - timedelta(days=days)
            prev_from_str = (now.date() - timedelta(days=days * 2)).isoformat()
            prev_to_str   = (now.date() - timedelta(days=days)).isoformat()

            insights: List[Dict[str, Any]] = []

            active_animals = (await db.execute(
                select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            )).scalars().all()
            animal_count = len(active_animals)

            generated_at = now.isoformat()

            # ------------------------------------------------------------------
            # INSIGHT 1: ADI pasayayotgan jonivorlar
            # ------------------------------------------------------------------
            adi_declining_animals = []
            for animal in active_animals:
                recent_adi = (await db.execute(
                    select(ADILog.adi_score, ADILog.calculation_date)
                    .where(
                        and_(
                            ADILog.animal_id == animal.id,
                            ADILog.calculation_date >= date_from_str,
                        )
                    )
                    .order_by(ADILog.calculation_date)
                )).all()

                if len(recent_adi) >= 6:
                    scores = [r.adi_score for r in recent_adi]
                    first_half  = sum(scores[:len(scores)//2]) / (len(scores)//2)
                    second_half = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
                    delta = second_half - first_half
                    if delta < -5.0:
                        adi_declining_animals.append({
                            "tag": animal.tag_id,
                            "delta": round(delta, 1),
                            "latest": round(scores[-1], 1),
                        })

            if adi_declining_animals:
                severity = "critical" if any(a["latest"] < 25 for a in adi_declining_animals) else "warning"
                tags     = [a["tag"] for a in adi_declining_animals[:5]]
                avg_drop = round(sum(a["delta"] for a in adi_declining_animals) / len(adi_declining_animals), 1)
                insights.append({
                    "insight_id":        f"ins_health_{uuid.uuid4().hex[:6]}",
                    "category":          "health",
                    "severity":          severity,
                    "title":             f"{len(adi_declining_animals)} ta jonivorning ADI balli pasaymoqda",
                    "description":       (
                        f"Oxirgi {days} kunda {', '.join(tags[:3])}"
                        f"{'...' if len(tags) > 3 else ''} jonivorilarining "
                        f"ADI balli o'rtacha {abs(avg_drop):.1f} ballga tushdi. "
                        "Veterinar tekshiruvi tavsiya etiladi."
                    ),
                    "affected_animals":  tags,
                    "metric_value":      abs(avg_drop),
                    "metric_label":      "O'rtacha ADI pasayish (ball)",
                    "action_required":   severity == "critical",
                    "generated_at":      generated_at,
                })

            # ------------------------------------------------------------------
            # INSIGHT 2: 7 kundan beri ko'rinmagan jonivorlar
            # ------------------------------------------------------------------
            week_ago_dt = now - timedelta(days=_MISSING_DAYS_THRESHOLD)
            seen_ids    = set(
                (await db.execute(
                    select(distinct(Detection.animal_id))
                    .where(
                        and_(
                            Detection.animal_id.is_not(None),
                            Detection.timestamp >= week_ago_dt,
                        )
                    )
                )).scalars().all()
            )
            missing_animals = [
                a.tag_id for a in active_animals if a.id not in seen_ids
            ]

            if missing_animals:
                insights.append({
                    "insight_id":       f"ins_detection_{uuid.uuid4().hex[:6]}",
                    "category":         "detection",
                    "severity":         "warning",
                    "title":            f"{len(missing_animals)} ta jonivor oxirgi 7 kunda ko'rinmagan",
                    "description":      (
                        f"{', '.join(missing_animals[:4])}"
                        f"{'...' if len(missing_animals) > 4 else ''} "
                        "jonivorilaridan so'nggi 7 kun ichida kamera orqali "
                        "birorta ham deteksiya qayd etilmagan. "
                        "Kamera burchagi yoki jonivor joylashuvi tekshirilsin."
                    ),
                    "affected_animals": missing_animals[:10],
                    "metric_value":     float(len(missing_animals)),
                    "metric_label":     "Ko'rinmagan jonivorlar soni",
                    "action_required":  len(missing_animals) > 3,
                    "generated_at":     generated_at,
                })

            # ------------------------------------------------------------------
            # INSIGHT 3: O'sish sekinlashuvi (regression slope)
            # ------------------------------------------------------------------
            weight_rows = (await db.execute(
                select(
                    func.date(WeightMeasurement.timestamp).label("date"),
                    func.avg(WeightMeasurement.estimated_weight_kg).label("avg_w"),
                )
                .where(WeightMeasurement.timestamp >= date_from_dt)
                .group_by(func.date(WeightMeasurement.timestamp))
                .order_by(func.date(WeightMeasurement.timestamp))
            )).all()

            if len(weight_rows) >= _MIN_REGRESSION_POINTS:
                w_data = [{"average_weight_kg": float(r.avg_w)} for r in weight_rows]
                reg    = self._compute_linear_regression(w_data)
                if reg and reg["slope_kg_per_day"] < -0.1:
                    insights.append({
                        "insight_id":       f"ins_growth_{uuid.uuid4().hex[:6]}",
                        "category":         "growth",
                        "severity":         "warning",
                        "title":            "Podada o'rtacha vazn kamaymoqda",
                        "description":      (
                            f"Oxirgi {days} kunda poda o'rtacha vazni "
                            f"kuniga {abs(reg['slope_kg_per_day']):.2f} kg ga kamaymoqda "
                            f"(R²={reg['r_squared']:.2f}). "
                            "Ozuqa ratsioni va sog'liq ahvolini tekshirish tavsiya etiladi."
                        ),
                        "affected_animals": [],
                        "metric_value":     round(reg["slope_kg_per_month"], 2),
                        "metric_label":     "Oylik vazn o'zgarishi (kg)",
                        "action_required":  reg["slope_kg_per_week"] < -1.0,
                        "generated_at":     generated_at,
                    })
                elif reg and reg["slope_kg_per_day"] > 0.3:
                    insights.append({
                        "insight_id":       f"ins_growth_{uuid.uuid4().hex[:6]}",
                        "category":         "growth",
                        "severity":         "positive",
                        "title":            "Poda yaxshi o'sish dinamikasini ko'rsatyapti",
                        "description":      (
                            f"Oxirgi {days} kunda poda o'rtacha vazni "
                            f"kuniga +{reg['slope_kg_per_day']:.2f} kg oshmoqda. "
                            f"30 kunlik prognoz: +{reg['slope_kg_per_month']:.1f} kg/jonivor."
                        ),
                        "affected_animals": [],
                        "metric_value":     round(reg["slope_kg_per_month"], 2),
                        "metric_label":     "Oylik o'rtacha o'sish (kg)",
                        "action_required":  False,
                        "generated_at":     generated_at,
                    })

            # ------------------------------------------------------------------
            # INSIGHT 4: Herd ADI overall trend
            # ------------------------------------------------------------------
            herd_adi_rows = (await db.execute(
                select(
                    ADILog.calculation_date,
                    func.avg(ADILog.adi_score).label("avg_adi"),
                )
                .where(ADILog.calculation_date >= date_from_str)
                .group_by(ADILog.calculation_date)
                .order_by(ADILog.calculation_date)
            )).all()

            if len(herd_adi_rows) >= 6:
                scores     = [float(r.avg_adi) for r in herd_adi_rows]
                half       = len(scores) // 2
                first_avg  = sum(scores[:half]) / half
                second_avg = sum(scores[half:]) / (len(scores) - half)
                delta_herd = second_avg - first_avg

                if delta_herd > 5.0:
                    insights.append({
                        "insight_id":       f"ins_herd_{uuid.uuid4().hex[:6]}",
                        "category":         "herd_trend",
                        "severity":         "positive",
                        "title":            "Podaning umumiy ADI balli yaxshilanmoqda",
                        "description":      (
                            f"Oxirgi {days} kunda poda o'rtacha ADI balli "
                            f"+{delta_herd:.1f} ballga oshdi "
                            f"({first_avg:.1f} → {second_avg:.1f}). "
                            "Joriy monitoring va ozuqlantirish rejimlari samarali."
                        ),
                        "affected_animals": [],
                        "metric_value":     round(delta_herd, 1),
                        "metric_label":     "ADI yaxshilanish (ball)",
                        "action_required":  False,
                        "generated_at":     generated_at,
                    })
                elif delta_herd < -5.0:
                    insights.append({
                        "insight_id":       f"ins_herd_{uuid.uuid4().hex[:6]}",
                        "category":         "herd_trend",
                        "severity":         "warning",
                        "title":            "Podaning umumiy ADI balli tushmoqda",
                        "description":      (
                            f"Oxirgi {days} kunda poda o'rtacha ADI balli "
                            f"{abs(delta_herd):.1f} ballga tushdi "
                            f"({first_avg:.1f} → {second_avg:.1f}). "
                            "Ozuqlantirish, sog'liq yoki kamera ishini tekshirish zarur."
                        ),
                        "affected_animals": [],
                        "metric_value":     round(abs(delta_herd), 1),
                        "metric_label":     "ADI pasayish (ball)",
                        "action_required":  second_avg < _ADI_AVERAGE_THRESHOLD,
                        "generated_at":     generated_at,
                    })

            # ------------------------------------------------------------------
            # INSIGHT 5: Aktiv alertlar pattern
            # ------------------------------------------------------------------
            alert_rows = (await db.execute(
                select(
                    AlertModel.animal_id,
                    func.count(AlertModel.id).label("cnt"),
                )
                .where(
                    and_(
                        AlertModel.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
                        AlertModel.created_at >= date_from_dt,
                    )
                )
                .group_by(AlertModel.animal_id)
                .having(func.count(AlertModel.id) >= 3)
                .order_by(desc("cnt"))
                .limit(5)
            )).all()

            if alert_rows:
                alert_ids  = [r.animal_id for r in alert_rows]
                alert_tags = []
                for aid in alert_ids:
                    a = next((x for x in active_animals if x.id == aid), None)
                    if a:
                        alert_tags.append(a.tag_id)

                insights.append({
                    "insight_id":       f"ins_alert_{uuid.uuid4().hex[:6]}",
                    "category":         "alert_pattern",
                    "severity":         "warning",
                    "title":            f"{len(alert_rows)} ta jonivor takroriy alert bermoqda",
                    "description":      (
                        f"{', '.join(alert_tags[:3])}"
                        f"{'...' if len(alert_tags) > 3 else ''} "
                        "jonivorilarida so'nggi davrda 3 yoki undan ko'p alert qayd etildi. "
                        "Bu jonivorlar individual kuzatuv talab qiladi."
                    ),
                    "affected_animals": alert_tags,
                    "metric_value":     float(len(alert_rows)),
                    "metric_label":     "Ko'p alertli jonivorlar soni",
                    "action_required":  True,
                    "generated_at":     generated_at,
                })

            # ------------------------------------------------------------------
            # INSIGHT 6: Yaxshi natija — agar barcha normal
            # ------------------------------------------------------------------
            if not insights:
                insights.append({
                    "insight_id":       f"ins_info_{uuid.uuid4().hex[:6]}",
                    "category":         "herd_trend",
                    "severity":         "positive",
                    "title":            "Ferma normal holat — alohida muammo aniqlanmadi",
                    "description":      (
                        f"Oxirgi {days} kunlik tahlil asosida: "
                        f"{animal_count} ta aktiv jonivorning barcha ko'rsatkichlari "
                        "me'yor doirasida. Monitoring davom ettirilsin."
                    ),
                    "affected_animals": [],
                    "metric_value":     None,
                    "metric_label":     None,
                    "action_required":  False,
                    "generated_at":     generated_at,
                })

            # Xulosa
            summary = {
                "total":           len(insights),
                "critical":        sum(1 for i in insights if i["severity"] == "critical"),
                "warning":         sum(1 for i in insights if i["severity"] == "warning"),
                "positive":        sum(1 for i in insights if i["severity"] == "positive"),
                "info":            sum(1 for i in insights if i["severity"] == "info"),
                "actions_required": sum(1 for i in insights if i["action_required"]),
            }

            logger.info(
                f"Automated insights generated: {len(insights)} insights",
                extra={"extra_data": summary},
            )

            return {
                "generated_at":         generated_at,
                "insights":             insights,
                "summary":              summary,
                "analysis_period_days": days,
                "animals_analyzed":     animal_count,
            }

        except Exception as exc:
            logger.error(f"Error generating automated insights: {exc}", exc_info=True)
            raise

    # =========================================================================
    # PRIVATE HELPERS
    # =========================================================================

    async def _get_total_animals(self, db: AsyncSession) -> int:
        return (await db.execute(select(func.count(Animal.id)))).scalar() or 0

    async def _get_active_animals(self, db: AsyncSession) -> int:
        return (
            await db.execute(
                select(func.count(Animal.id)).where(Animal.status == AnimalStatus.ACTIVE)
            )
        ).scalar() or 0

    async def _get_animals_by_status(self, db: AsyncSession) -> Dict[str, int]:
        rows = (
            await db.execute(
                select(Animal.status, func.count(Animal.id).label("cnt"))
                .group_by(Animal.status)
            )
        ).all()
        return {
            (r.status.value if hasattr(r.status, "value") else str(r.status)): r.cnt
            for r in rows
        }

    async def _get_detections_count(
        self,
        db:        AsyncSession,
        date_from: Optional[date] = None,
        date_to:   Optional[date] = None,
    ) -> int:
        query = select(func.count(Detection.id))
        if date_from is not None:
            query = query.where(
                Detection.timestamp >= datetime(
                    date_from.year, date_from.month, date_from.day, tzinfo=timezone.utc
                )
            )
        if date_to is not None:
            query = query.where(
                Detection.timestamp < datetime(
                    date_to.year, date_to.month, date_to.day, tzinfo=timezone.utc
                ) + timedelta(days=1)
            )
        return (await db.execute(query)).scalar() or 0

    async def _get_average_weight(self, db: AsyncSession) -> Optional[float]:
        subq = (
            select(
                WeightMeasurement.animal_id,
                func.max(WeightMeasurement.timestamp).label("max_ts"),
            )
            .group_by(WeightMeasurement.animal_id)
            .subquery()
        )
        avg = (
            await db.execute(
                select(func.avg(WeightMeasurement.estimated_weight_kg))
                .select_from(WeightMeasurement)
                .join(
                    subq,
                    and_(
                        WeightMeasurement.animal_id == subq.c.animal_id,
                        WeightMeasurement.timestamp  == subq.c.max_ts,
                    ),
                )
            )
        ).scalar()
        return float(avg) if avg else None

    async def _get_weight_change_percentage(
        self, db: AsyncSession, days: int = 7
    ) -> Optional[float]:
        now       = datetime.utcnow()
        past_date = now - timedelta(days=days)
        current   = await self._get_average_weight(db)
        past_avg  = (
            await db.execute(
                select(func.avg(WeightMeasurement.estimated_weight_kg)).where(
                    and_(
                        WeightMeasurement.timestamp >= past_date - timedelta(days=1),
                        WeightMeasurement.timestamp <  past_date + timedelta(days=1),
                    )
                )
            )
        ).scalar()
        past = float(past_avg) if past_avg else None
        if current and past and past > 0:
            return ((current - past) / past) * 100
        return None

    def _get_camera_status(self) -> Dict[str, Any]:
        """
        PipelineManager dan kamera holati.

        CameraManager o'rniga pipeline_manager.get_all_status() ishlatiladi.
        """
        try:
            from app.services.pipeline_manager import get_pipeline_manager
            pm         = get_pipeline_manager()
            all_status = pm.get_all_status()
            total      = len(all_status)
            running    = sum(1 for s in all_status.values() if s.get("running"))
            return {
                "total":   total,
                "running": running,
                "healthy": running,
                "status":  "healthy" if running == total and total > 0 else (
                    "degraded" if running > 0 else "down"
                ),
            }
        except Exception as exc:
            logger.warning(f"Could not get camera status from pipeline_manager: {exc}")
            return {"total": 0, "running": 0, "healthy": 0, "status": "down"}

    async def _get_recent_detections(
        self, db: AsyncSession, limit: int = 5
    ) -> List[Dict[str, Any]]:
        rows = (
            await db.execute(
                select(Detection)
                .options(selectinload(Detection.animal))
                .order_by(desc(Detection.timestamp))
                .limit(limit)
            )
        ).scalars().all()
        return [
            {
                "animal_tag": d.animal.tag_id if d.animal else "Unknown",
                "camera_id":  d.camera_id,
                "confidence": round(d.confidence, 3),
                "detected_at": d.timestamp.isoformat(),
            }
            for d in rows
        ]

    async def _generate_alerts(self, db: AsyncSession) -> List[Dict[str, Any]]:
        animals = (
            await db.execute(
                select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            )
        ).scalars().all()

        alerts = []
        now    = datetime.utcnow()

        for animal in animals:
            if animal.last_detected_at is None:
                alerts.append({
                    "type":       "never_detected",
                    "severity":   "critical",
                    "animal_tag": animal.tag_id,
                    "message":    f"Animal {animal.tag_id} never detected",
                })
            else:
                last = animal.last_detected_at
                if hasattr(last, "replace"):
                    last = last.replace(tzinfo=None)
                days_since = (now - last).days
                if days_since > _MISSING_DAYS_THRESHOLD:
                    alerts.append({
                        "type":       "no_recent_detection",
                        "severity":   "warning",
                        "animal_tag": animal.tag_id,
                        "message":    f"No detection for {days_since} days",
                        "days":       days_since,
                    })

        return alerts

    async def _detect_weight_loss(self, db: AsyncSession) -> List[Dict[str, Any]]:
        animals = (
            await db.execute(
                select(Animal)
                .options(selectinload(Animal.weight_measurements))
                .where(Animal.status == AnimalStatus.ACTIVE)
            )
        ).scalars().all()

        alerts = []
        week_ago = datetime.utcnow() - timedelta(days=7)

        for animal in animals:
            meas = sorted(animal.weight_measurements, key=lambda m: m.timestamp, reverse=True)
            if len(meas) < 2:
                continue

            latest   = meas[0].estimated_weight_kg
            week_ago_w = None
            for m in meas[1:]:
                ts = m.timestamp.replace(tzinfo=None) if hasattr(m.timestamp, "replace") else m.timestamp
                if ts < week_ago:
                    week_ago_w = m.estimated_weight_kg
                    break

            if week_ago_w and latest < week_ago_w:
                loss_pct = ((week_ago_w - latest) / week_ago_w) * 100
                if loss_pct > 5:
                    alerts.append({
                        "type":             "weight_loss",
                        "severity":         "warning" if loss_pct < 10 else "critical",
                        "animal_tag":       animal.tag_id,
                        "message":          f"Weight loss of {loss_pct:.1f}% in 7 days",
                        "loss_percentage":  round(loss_pct, 2),
                        "previous_weight":  round(float(week_ago_w), 2),
                        "current_weight":   round(float(latest), 2),
                    })

        return alerts

    def _calculate_risk_score(
        self,
        animals_by_status: Dict[str, int],
        alerts: List[Dict[str, Any]],
        total_animals: int,
    ) -> int:
        """0–100 oralig'ida umumiy xavf ballini hisoblaydi."""
        if total_animals == 0:
            return 0
        score  = 0
        score += (animals_by_status.get("sold", 0)     / total_animals) * 20
        score += (animals_by_status.get("deceased", 0) / total_animals) * 30
        score += (sum(1 for a in alerts if a["severity"] == "critical") / total_animals) * 30
        score += (sum(1 for a in alerts if a["severity"] == "warning")  / total_animals) * 15
        return min(int(score), 100)