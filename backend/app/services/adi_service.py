"""
Animal Development Index (ADI) Service — Refactored with Repository Pattern.

ARXITEKTURA O'ZGARISHI (Sprint 5):
    Oldingi:  ADIService → self.db.execute(select...) to'g'ridan-to'g'ri
    Yangi:    ADIService → ADIRepository → SQLAlchemy → PostgreSQL

JAVOBGARLIK:
    - ADI algoritm logikasi (8 komponent hisoblash)
    - Repository orqali DB bilan muloqot
    - Celery task va API endpoint bilan integratsiya

ALGORITM:
    Har bir jonivor uchun so'nggi 24 soatlik ma'lumotlar
    detection jadvalidan olinadi va 8 ta komponent alohida
    hisoblanadi. Og'irlikli o'rtacha yakuniy ADI scoreni beradi.

OG'IRLIKLAR:
    activity   = 0.20  — kunlik faollik
    feeding    = 0.20  — ovqatlanish
    growth     = 0.20  — o'sish dinamikasi (30 kunlik trend)
    movement   = 0.15  — harakat sifati
    drinking   = 0.10  — suv ichish
    social     = 0.10  — ijtimoiy indeks
    sensor     = 0.05  — IoT sensor (hozir simulyatsiya)
    veterinary = 0.05  — veterinar holati (qo'lda kiritiladi)

PARTIAL DATA:
    Agar ba'zi komponentlar uchun ma'lumot bo'lmasa,
    mavjud komponentlar og'irliklari qayta normallanadi.
    Bu sensor yo'q yoki kamera offline bo'lsa ham
    tizimning ishlashini ta'minlaydi.
"""

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Optional, Any

from sqlalchemy import select, func, and_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.adi_log import ADILog, ADICategory
from app.models.health_record import HealthRecord
from app.repositories.adi_repository import ADIRepository
from app.core.exceptions import EntityNotFoundError, DatabaseError

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------ #
# Konstantalar                                                         #
# ------------------------------------------------------------------ #

# Komponent og'irliklari (jami = 1.0)
WEIGHTS: dict[str, float] = {
    "activity":   0.20,
    "feeding":    0.20,
    "growth":     0.20,
    "movement":   0.15,
    "drinking":   0.10,
    "social":     0.10,
    "sensor":     0.05,
    "veterinary": 0.05,
}

# Turning constants — real ferma ma'lumotlariga asoslangan
ACTIVITY_NORM_DETECTIONS_PER_DAY = 48    # 30 daqiqada 1 deteksiya = normal
FEEDING_NORM_VISITS_PER_DAY      = 6     # Kuniga 6 marta ozuqa zonasi = normal
DRINKING_NORM_VISITS_PER_DAY     = 8     # Kuniga 8 marta suv = normal
FEEDING_ZONE_DWELL_SECONDS       = 300   # 5 daqiqa ozuqa zonasida = to'liq ovqatlangan
DRINKING_ZONE_DWELL_SECONDS      = 60    # 1 daqiqa suv zonasida = to'liq ichdi
SOCIAL_NORM_CODETECTION_RATIO    = 0.3   # Deteksiyalarning 30% i boshqalar bilan = normal
GROWTH_WINDOW_DAYS               = 30    # O'sish trendi uchun oyna
GROWTH_MIN_DATAPOINTS            = 7     # Kamida 7 kun kerak
MISSING_THRESHOLD_HOURS          = 24    # Shu soatdan ko'p ko'rinmasa — muammo

# Bbox zona identifikatsiyasi uchun (normalized koordinatalar)
# Ferma rejasiga qarab sozlanadi — hozir umumiy qiymatlar
FEEDING_ZONE  = {"x_min": 0.0, "x_max": 0.4, "y_min": 0.6, "y_max": 1.0}
DRINKING_ZONE = {"x_min": 0.6, "x_max": 1.0, "y_min": 0.6, "y_max": 1.0}


# ------------------------------------------------------------------ #
# Internal data containers                                             #
# ------------------------------------------------------------------ #

@dataclass
class DetectionSummary:
    """
    24 soatlik deteksiya ma'lumotlari xulosasi.
    Hisoblash bosqichida ishlatiladi.
    """
    total_count:        int   = 0
    feeding_visits:     int   = 0
    feeding_dwell_sec:  float = 0.0
    drinking_visits:    int   = 0
    drinking_dwell_sec: float = 0.0
    co_detection_count: int   = 0
    bbox_sizes:         list[float] = field(default_factory=list)
    bbox_velocities:    list[float] = field(default_factory=list)
    hourly_counts:      dict[int, int] = field(default_factory=dict)


@dataclass
class ComponentResult:
    """Bitta komponent hisoblash natijasi."""
    score:    Optional[float]   # 0.0 — 100.0, None = ma'lumot yo'q
    weight:   float             # Og'irlik koeffitsienti
    detail:   dict[str, Any]    # Debug ma'lumotlari
    has_data: bool = True


@dataclass
class ADIResult:
    """To'liq ADI hisoblash natijasi."""
    animal_id:        int
    calculation_date: str
    calculated_at:    datetime
    adi_score:        float
    category:         str
    data_quality:     float
    components:       dict[str, ComponentResult]
    raw_data:         dict[str, Any]
    notes:            Optional[str] = None


# ------------------------------------------------------------------ #
# ADI Service                                                          #
# ------------------------------------------------------------------ #

class ADIService:
    """
    Animal Development Index hisoblash servisi.

    Barcha hisoblash logikasi shu klassda.
    DB bilan muloqot ADIRepository orqali amalga oshiriladi.

    Celery task va API endpoint tomonidan ishlatiladi.

    Usage:
        service = ADIService(db)
        result = await service.calculate_for_animal(
            animal_id=1,
            target_date="2026-02-20"
        )
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Initialize ADI service.

        Args:
            db: Async database session (FastAPI Depends orqali keladi)
        """
        self.db = db
        self._repo = ADIRepository(db)  # Repository pattern

    # ================================================================ #
    # PUBLIC API                                                         #
    # ================================================================ #

    async def calculate_for_animal(
        self,
        animal_id: int,
        target_date: Optional[str] = None,
        force_recalculate: bool = False,
    ) -> ADIResult:
        """
        Bitta jonivor uchun ADI hisoblash.

        Args:
            animal_id:         Jonivor ID
            target_date:       YYYY-MM-DD (None = bugun)
            force_recalculate: True = mavjud yozuvni qayta hisoblash

        Returns:
            ADIResult — to'liq hisoblash natijasi

        Raises:
            EntityNotFoundError: Jonivor topilmasa
            DatabaseError:       DB xatosi bo'lsa
        """
        # 1. Jonivorni tekshirish
        animal = await self._get_animal(animal_id)

        # 2. Sana
        date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        logger.info(
            "ADI calculation started",
            extra={"animal_id": animal_id, "date": date_str},
        )

        # 3. Mavjud yozuvni tekshirish (Repository orqali)
        if not force_recalculate:
            existing = await self._repo.get_by_animal_and_date(animal_id, date_str)
            if existing:
                logger.debug(
                    f"ADI already calculated for animal {animal_id} on {date_str}"
                )
                return self._adi_log_to_result(existing)

        # 4. Force recalculate bo'lsa — eskisini o'chirish (Repository orqali)
        if force_recalculate:
            await self._repo.delete_by_animal_and_date(animal_id, date_str)

        # 5. Ma'lumotlarni yig'ish
        period_start, period_end = self._get_period_bounds(date_str)
        summary = await self._collect_detection_summary(
            animal_id, period_start, period_end
        )
        historical_bbox = await self._collect_historical_bbox(animal_id, date_str)
        latest_health   = await self._get_latest_health_record(animal_id)
        sensor_data     = await self._get_sensor_data(animal_id, period_start, period_end)

        # 6. Komponentlarni hisoblash (pure logic, DB yo'q)
        components = self._compute_all_components(
            summary=summary,
            historical_bbox=historical_bbox,
            animal=animal,
            health_record=latest_health,
            sensor_data=sensor_data,
            date_str=date_str,
        )

        # 7. Yakuniy score
        adi_score, data_quality = self._compute_final_score(components)
        category = ADICategory.from_score(adi_score)

        # 8. Izoh generatsiya
        notes = self._generate_notes(components, adi_score, summary)

        # 9. raw_data yig'ish
        raw_data = self._build_raw_data(summary, components, historical_bbox, sensor_data)

        # 10. Natija
        result = ADIResult(
            animal_id=animal_id,
            calculation_date=date_str,
            calculated_at=datetime.now(timezone.utc),
            adi_score=round(adi_score, 2),
            category=category,
            data_quality=round(data_quality, 3),
            components=components,
            raw_data=raw_data,
            notes=notes,
        )

        # 11. DB ga saqlash (Repository orqali)
        await self._save_result(result)

        logger.info(
            "ADI calculation complete",
            extra={
                "animal_id":  animal_id,
                "date":       date_str,
                "score":      result.adi_score,
                "category":   result.category,
                "quality":    result.data_quality,
            },
        )

        return result

    async def calculate_for_all_active(
        self,
        target_date: Optional[str] = None,
        force_recalculate: bool = False,
    ) -> list[ADIResult]:
        """
        Barcha aktiv jonivorlar uchun ADI hisoblash.
        Celery daily task tomonidan ishlatiladi.

        Args:
            target_date:       YYYY-MM-DD (None = bugun)
            force_recalculate: True = qayta hisoblash

        Returns:
            Barcha natijalar ro'yxati
        """
        # Aktiv jonivorlar ID larini olish (Repository orqali)
        date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Faqat ADI hisoblanmagan jonivorlar (samarali strategiya)
        if not force_recalculate:
            animal_ids = await self._repo.get_animals_without_adi_today()
        else:
            # Barcha aktiv jonivorlar
            result = await self.db.execute(
                select(Animal.id).where(Animal.status == AnimalStatus.ACTIVE)
            )
            animal_ids = [row[0] for row in result.fetchall()]

        logger.info(f"Starting batch ADI calculation for {len(animal_ids)} animals")

        results: list[ADIResult] = []
        errors:  list[tuple[int, str]] = []

        for animal_id in animal_ids:
            try:
                adi_result = await self.calculate_for_animal(
                    animal_id=animal_id,
                    target_date=date_str,
                    force_recalculate=force_recalculate,
                )
                results.append(adi_result)
            except Exception as e:
                logger.error(
                    f"ADI calculation failed for animal {animal_id}: {e}",
                    exc_info=True,
                )
                errors.append((animal_id, str(e)))

        logger.info(
            f"Batch ADI complete: {len(results)} success, {len(errors)} failed"
        )

        return results

    async def get_animal_trend(
        self,
        animal_id: int,
        days: int = 30,
    ) -> list[ADILog]:
        """
        Jonivorning ADI trend tarixini olish.

        Args:
            animal_id: Jonivor ID
            days:      Necha kunlik tarix (default: 30)

        Returns:
            ADILog ro'yxati, yangi → eski tartibda
        """
        return await self._repo.get_trend_for_animal(animal_id, days)

    async def get_farm_summary(
        self,
        target_date: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Butun ferma bo'yicha ADI xulosasi.
        Dashboard widget uchun.

        Args:
            target_date: YYYY-MM-DD (None = bugun)

        Returns:
            Ferma ADI statistikasi
        """
        date_str = target_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Repository orqali
        avg_score = await self._repo.get_farm_avg_score(date_str)

        if avg_score is None:
            return {
                "date":         date_str,
                "total_animals": 0,
                "message":      "Bugun uchun ADI hali hisoblanmagan",
            }

        counts = await self._repo.get_farm_category_counts(date_str)
        concerning = await self._repo.get_concerning_animals(date_str)

        total = sum(counts.values())

        return {
            "date":            date_str,
            "total_animals":   total,
            "farm_adi_score":  avg_score,
            "healthy_count":   counts["healthy"],
            "average_count":   counts["average"],
            "warning_count":   counts["warning"],
            "critical_count":  counts["critical"],
            "healthy_pct":  round(counts["healthy"]  / total * 100, 1) if total else 0,
            "average_pct":  round(counts["average"]  / total * 100, 1) if total else 0,
            "warning_pct":  round(counts["warning"]  / total * 100, 1) if total else 0,
            "critical_pct": round(counts["critical"] / total * 100, 1) if total else 0,
            "needs_attention": [
                {
                    "animal_id": log.animal_id,
                    "adi_score": log.adi_score,
                    "category":  log.category,
                }
                for log in concerning
            ],
        }

    # ================================================================ #
    # KOMPONENT HISOBLASH (private, pure logic — DB yo'q)               #
    # ================================================================ #

    def _compute_all_components(
        self,
        summary: DetectionSummary,
        historical_bbox: list[tuple[str, float]],
        animal: Animal,
        health_record: Optional[Any],
        sensor_data: Optional[dict[str, float]],
        date_str: str,
    ) -> dict[str, ComponentResult]:
        """Barcha 8 ta komponentni hisoblash."""

        return {
            "activity":   self._compute_activity(summary),
            "feeding":    self._compute_feeding(summary),
            "drinking":   self._compute_drinking(summary),
            "movement":   self._compute_movement(summary),
            "growth":     self._compute_growth(historical_bbox, animal),
            "social":     self._compute_social(summary),
            "sensor":     self._compute_sensor(sensor_data),
            "veterinary": self._compute_veterinary(health_record),
        }

    def _compute_activity(self, summary: DetectionSummary) -> ComponentResult:
        """
        Faollik score hisoblash.

        Normaga nisbatan deteksiya soni.
        Sigmoid funksiya orqali 0-100 ga o'tkaziladi.

        Args:
            summary: 24 soatlik deteksiya xulosasi

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if summary.total_count == 0:
            return ComponentResult(
                score=0.0,
                weight=WEIGHTS["activity"],
                detail={"detections": 0, "norm": ACTIVITY_NORM_DETECTIONS_PER_DAY},
                has_data=False,
            )

        ratio = summary.total_count / ACTIVITY_NORM_DETECTIONS_PER_DAY
        score = self._sigmoid_score(ratio, midpoint=1.0, steepness=3.0)

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["activity"],
            detail={
                "detections_today": summary.total_count,
                "norm":             ACTIVITY_NORM_DETECTIONS_PER_DAY,
                "ratio":            round(ratio, 3),
                "hourly_breakdown": summary.hourly_counts,
            },
        )

    def _compute_feeding(self, summary: DetectionSummary) -> ComponentResult:
        """
        Ovqatlanish score hisoblash.

        Ozuqa zonasiga tashrif soni va u yerda o'tkazilgan
        vaqt kombinatsiyasi asosida.

        Args:
            summary: 24 soatlik deteksiya xulosasi

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if summary.total_count == 0:
            return ComponentResult(
                score=None,
                weight=WEIGHTS["feeding"],
                detail={"reason": "No detections today"},
                has_data=False,
            )

        visit_ratio = min(summary.feeding_visits / FEEDING_NORM_VISITS_PER_DAY, 1.5)
        dwell_ratio = min(summary.feeding_dwell_sec / FEEDING_ZONE_DWELL_SECONDS, 1.5)

        visit_score = self._sigmoid_score(visit_ratio, midpoint=0.8, steepness=4.0)
        dwell_score = self._sigmoid_score(dwell_ratio, midpoint=0.8, steepness=4.0)

        score = visit_score * 0.5 + dwell_score * 0.5

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["feeding"],
            detail={
                "feeding_visits": summary.feeding_visits,
                "norm_visits":    FEEDING_NORM_VISITS_PER_DAY,
                "dwell_seconds":  round(summary.feeding_dwell_sec, 1),
                "norm_dwell":     FEEDING_ZONE_DWELL_SECONDS,
                "visit_score":    round(visit_score, 2),
                "dwell_score":    round(dwell_score, 2),
            },
        )

    def _compute_drinking(self, summary: DetectionSummary) -> ComponentResult:
        """
        Suv ichish score hisoblash.

        Suv zonasiga tashrif va dwell vaqti asosida.

        Args:
            summary: 24 soatlik deteksiya xulosasi

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if summary.total_count == 0:
            return ComponentResult(
                score=None,
                weight=WEIGHTS["drinking"],
                detail={"reason": "No detections today"},
                has_data=False,
            )

        visit_ratio = min(summary.drinking_visits / DRINKING_NORM_VISITS_PER_DAY, 1.5)
        dwell_ratio = min(summary.drinking_dwell_sec / DRINKING_ZONE_DWELL_SECONDS, 1.5)

        visit_score = self._sigmoid_score(visit_ratio, midpoint=0.8, steepness=4.0)
        dwell_score = self._sigmoid_score(dwell_ratio, midpoint=0.8, steepness=4.0)

        score = visit_score * 0.5 + dwell_score * 0.5

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["drinking"],
            detail={
                "drinking_visits": summary.drinking_visits,
                "norm_visits":     DRINKING_NORM_VISITS_PER_DAY,
                "dwell_seconds":   round(summary.drinking_dwell_sec, 1),
                "norm_dwell":      DRINKING_ZONE_DWELL_SECONDS,
                "visit_score":     round(visit_score, 2),
                "dwell_score":     round(dwell_score, 2),
            },
        )

    def _compute_movement(self, summary: DetectionSummary) -> ComponentResult:
        """
        Harakat sifati score hisoblash.

        Bbox orasidagi o'rtacha tezlik va barqarorlik asosida.
        Juda sekin (kasal) yoki juda tez (hayajonlangan) = past ball.

        Args:
            summary: 24 soatlik deteksiya xulosasi

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if len(summary.bbox_velocities) < 3:
            return ComponentResult(
                score=None,
                weight=WEIGHTS["movement"],
                detail={"reason": "Insufficient velocity data"},
                has_data=False,
            )

        avg_velocity = sum(summary.bbox_velocities) / len(summary.bbox_velocities)
        velocity_std = self._std_dev(summary.bbox_velocities)

        if avg_velocity < 0.005:
            velocity_score = 30.0      # Harakatsiz — kasal yoki uxlayapti
        elif avg_velocity > 0.1:
            velocity_score = 50.0      # Juda tez — hayajonlangan
        else:
            normalized     = (avg_velocity - 0.005) / (0.1 - 0.005)
            velocity_score = 60.0 + normalized * 30.0

        stability_score = max(0.0, min(100.0, 100.0 - velocity_std * 500.0))
        score = velocity_score * 0.6 + stability_score * 0.4

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["movement"],
            detail={
                "avg_velocity":    round(avg_velocity, 5),
                "velocity_std":    round(velocity_std, 5),
                "velocity_score":  round(velocity_score, 2),
                "stability_score": round(stability_score, 2),
                "samples":         len(summary.bbox_velocities),
            },
        )

    def _compute_growth(
        self,
        historical_bbox: list[tuple[str, float]],
        animal: Animal,
    ) -> ComponentResult:
        """
        O'sish dinamikasi score hisoblash.

        30 kunlik bbox o'rtacha hajmi trend chizig'i asosida.
        Yosh bilan kutilgan o'sish normaliga taqqoslanadi.

        Args:
            historical_bbox: [(date_str, avg_bbox_size), ...] eski → yangi
            animal:          Yosh va tur ma'lumotlari uchun

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if len(historical_bbox) < GROWTH_MIN_DATAPOINTS:
            return ComponentResult(
                score=None,
                weight=WEIGHTS["growth"],
                detail={
                    "reason":     "Insufficient historical data",
                    "datapoints": len(historical_bbox),
                    "required":   GROWTH_MIN_DATAPOINTS,
                },
                has_data=False,
            )

        sizes = [s for _, s in historical_bbox]
        slope = self._linear_regression_slope(sizes)

        age_months     = animal.age_months or 12.0
        expected_slope = self._expected_growth_slope(age_months, animal.species.value)

        if expected_slope == 0:
            if abs(slope) < 0.0001:
                score = 85.0
            elif slope < 0:
                score = max(20.0, 85.0 + slope * 10000)
            else:
                score = 85.0
        else:
            ratio = slope / expected_slope
            if ratio >= 0.8:
                score = 90.0 + min(10.0, (ratio - 0.8) * 50)
            elif ratio >= 0.5:
                score = 70.0 + (ratio - 0.5) * 66.7
            elif ratio >= 0.0:
                score = 40.0 + ratio * 60.0
            else:
                score = max(0.0, 40.0 + ratio * 40.0)

        score = max(0.0, min(100.0, score))

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["growth"],
            detail={
                "datapoints":      len(historical_bbox),
                "slope":           round(slope, 8),
                "expected_slope":  round(expected_slope, 8),
                "age_months":      age_months,
                "species":         animal.species.value,
                "avg_size_recent": round(sum(sizes[-7:]) / len(sizes[-7:]), 4),
                "avg_size_older":  round(sum(sizes[:7])  / len(sizes[:7]),  4),
            },
        )

    def _compute_social(self, summary: DetectionSummary) -> ComponentResult:
        """
        Ijtimoiy indeks score hisoblash.

        Deteksiyalarning qancha qismi boshqa
        jonivorlar bilan birga bo'lganini o'lchaydi.

        Args:
            summary: 24 soatlik deteksiya xulosasi

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if summary.total_count == 0:
            return ComponentResult(
                score=None,
                weight=WEIGHTS["social"],
                detail={"reason": "No detections today"},
                has_data=False,
            )

        co_ratio = summary.co_detection_count / summary.total_count
        score = self._sigmoid_score(
            co_ratio / SOCIAL_NORM_CODETECTION_RATIO,
            midpoint=1.0,
            steepness=4.0,
        )

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["social"],
            detail={
                "total_detections": summary.total_count,
                "co_detections":    summary.co_detection_count,
                "co_ratio":         round(co_ratio, 3),
                "norm_co_ratio":    SOCIAL_NORM_CODETECTION_RATIO,
            },
        )

    def _compute_sensor(
        self,
        sensor_data: Optional[dict[str, float]],
    ) -> ComponentResult:
        """
        IoT sensor score hisoblash.

        Hozir simulyatsiya. Real sensorlar qo'shilganda yangilanadi.
        Normal diapazonlar (qoramol): Harorat 38.0-39.5°C, HR 40-80 bpm.

        Args:
            sensor_data: {"temperature": float, "heart_rate": float} yoki None

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if not sensor_data:
            return ComponentResult(
                score=70.0,
                weight=WEIGHTS["sensor"],
                detail={"mode": "simulated", "reason": "No real sensor data"},
                has_data=False,
            )

        scores: list[float] = []
        detail: dict[str, Any] = {"mode": "real"}

        if "temperature" in sensor_data:
            temp = sensor_data["temperature"]
            if 38.0 <= temp <= 39.5:
                scores.append(100.0)
            elif 37.5 <= temp < 38.0 or 39.5 < temp <= 40.0:
                scores.append(60.0)
            else:
                scores.append(10.0)
            detail["temperature"] = temp

        if "heart_rate" in sensor_data:
            hr = sensor_data["heart_rate"]
            if 40 <= hr <= 80:
                scores.append(100.0)
            elif 30 <= hr < 40 or 80 < hr <= 100:
                scores.append(50.0)
            else:
                scores.append(5.0)
            detail["heart_rate"] = hr

        score = sum(scores) / len(scores) if scores else 70.0

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["sensor"],
            detail=detail,
        )

    def _compute_veterinary(
        self,
        health_record: Optional[Any],
    ) -> ComponentResult:
        """
        Veterinar holati score hisoblash.

        So'nggi veterinar tekshiruv natijasi asosida.
        Ma'lumot yo'q bo'lsa — neytral ball (50).

        Args:
            health_record: HealthRecord ORM instance yoki None

        Returns:
            ComponentResult — score va tafsilotlar
        """
        if not health_record:
            return ComponentResult(
                score=50.0,
                weight=WEIGHTS["veterinary"],
                detail={"reason": "No veterinary records found"},
                has_data=False,
            )

        if health_record.treatment and not health_record.resolved_at:
            score  = 20.0
            status = "under_treatment"
        elif health_record.recorded_at:
            days_ago = (datetime.now(timezone.utc) - health_record.recorded_at).days
            if days_ago > 30:
                score  = 55.0
                status = "checkup_overdue"
            else:
                score  = 85.0
                status = "recently_checked"
        else:
            score  = 50.0
            status = "unknown"

        return ComponentResult(
            score=round(score, 2),
            weight=WEIGHTS["veterinary"],
            detail={
                "status":      status,
                "last_record": str(health_record.recorded_at)
                               if health_record.recorded_at else None,
            },
        )

    # ================================================================ #
    # SCORE AGGREGATION                                                  #
    # ================================================================ #

    def _compute_final_score(
        self,
        components: dict[str, ComponentResult],
    ) -> tuple[float, float]:
        """
        Yakuniy ADI score hisoblash.

        Agar biror komponent ma'lumoti bo'lmasa,
        uning og'irligi boshqa mavjud komponentlarga
        proporsional taqsimlanadi (partial data handling).

        Args:
            components: 8 ta ComponentResult dict

        Returns:
            (adi_score 0-100, data_quality 0-1)
        """
        available = {k: v for k, v in components.items() if v.score is not None}

        if not available:
            return 0.0, 0.0

        total_available_weight = sum(v.weight for v in available.values())
        data_quality = total_available_weight

        weighted_sum = sum(
            v.score * (v.weight / total_available_weight)  # type: ignore[operator]
            for v in available.values()
        )

        return round(weighted_sum, 4), round(data_quality, 4)

    # ================================================================ #
    # DATA COLLECTION (private, DB calls)                                #
    # ================================================================ #

    async def _collect_detection_summary(
        self,
        animal_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> DetectionSummary:
        """
        24 soatlik deteksiya ma'lumotlarini yig'ish.

        Args:
            animal_id:    Jonivor ID
            period_start: Period boshi (UTC)
            period_end:   Period oxiri (UTC)

        Returns:
            DetectionSummary — barcha hisoblash uchun zarur ma'lumotlar
        """
        stmt = (
            select(Detection)
            .where(
                and_(
                    Detection.animal_id == animal_id,
                    Detection.timestamp >= period_start,
                    Detection.timestamp < period_end,
                )
            )
            .order_by(Detection.timestamp.asc())
        )
        result = await self.db.execute(stmt)
        detections = list(result.scalars().all())

        summary = DetectionSummary()
        summary.total_count = len(detections)

        if not detections:
            return summary

        prev_bbox_cx: Optional[float] = None
        prev_timestamp: Optional[datetime] = None

        for det in detections:
            bbox = det.bbox or {}
            cx   = bbox.get("x", 0.5)
            cy   = bbox.get("y", 0.5)
            bw   = bbox.get("w", 0.0)
            bh   = bbox.get("h", 0.0)

            bbox_size = bw * bh
            if bbox_size > 0:
                summary.bbox_sizes.append(bbox_size)

            if prev_bbox_cx is not None and prev_timestamp is not None:
                dt_sec = (det.timestamp - prev_timestamp).total_seconds()
                if 0 < dt_sec <= 300:
                    velocity = abs(cx - prev_bbox_cx) / dt_sec
                    summary.bbox_velocities.append(velocity)

            prev_bbox_cx   = cx
            prev_timestamp = det.timestamp

            hour = det.timestamp.hour
            summary.hourly_counts[hour] = summary.hourly_counts.get(hour, 0) + 1

            if self._in_zone(cx, cy, FEEDING_ZONE):
                summary.feeding_visits    += 1
                summary.feeding_dwell_sec += 5.0

            if self._in_zone(cx, cy, DRINKING_ZONE):
                summary.drinking_visits    += 1
                summary.drinking_dwell_sec += 5.0

        summary.co_detection_count = await self._count_co_detections(
            animal_id, period_start, period_end
        )

        return summary

    async def _collect_historical_bbox(
        self,
        animal_id: int,
        target_date: str,
    ) -> list[tuple[str, float]]:
        """
        30 kunlik kunlik o'rtacha bbox o'lchamlarini olish.

        Args:
            animal_id:   Jonivor ID
            target_date: YYYY-MM-DD

        Returns:
            [(date_str, avg_bbox_size), ...] eski → yangi tartibda
        """
        end_date   = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        start_date = end_date - timedelta(days=GROWTH_WINDOW_DAYS)

        stmt = text("""
            SELECT
                DATE(timestamp AT TIME ZONE 'UTC') AS det_date,
                AVG((bbox->>'w')::float * (bbox->>'h')::float) AS avg_bbox_area
            FROM detections
            WHERE
                animal_id = :animal_id
                AND timestamp >= :start_date
                AND timestamp < :end_date
                AND bbox IS NOT NULL
                AND (bbox->>'w')::float > 0
                AND (bbox->>'h')::float > 0
            GROUP BY det_date
            ORDER BY det_date ASC
        """)

        result = await self.db.execute(
            stmt,
            {
                "animal_id":  animal_id,
                "start_date": start_date,
                "end_date":   end_date,
            },
        )
        rows = result.fetchall()
        return [(str(row[0]), float(row[1])) for row in rows]

    async def _count_co_detections(
        self,
        animal_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> int:
        """
        Boshqa jonivorlar bilan birgalikda ko'ringan deteksiyalar soni.

        Bir xil kamera, bir xil vaqt (±10 sekund) oralig'ida
        boshqa jonivorning deteksiyasi bo'lsa — co-detection.

        Args:
            animal_id:    Jonivor ID
            period_start: Period boshi
            period_end:   Period oxiri

        Returns:
            Co-detection soni
        """
        stmt = text("""
            SELECT COUNT(DISTINCT d1.id)
            FROM detections d1
            JOIN detections d2
                ON d1.camera_id = d2.camera_id
                AND d2.animal_id != d1.animal_id
                AND d2.animal_id IS NOT NULL
                AND ABS(EXTRACT(EPOCH FROM (d1.timestamp - d2.timestamp))) <= 10
            WHERE
                d1.animal_id = :animal_id
                AND d1.timestamp >= :start
                AND d1.timestamp < :end
        """)

        result = await self.db.execute(
            stmt,
            {"animal_id": animal_id, "start": period_start, "end": period_end},
        )
        row = result.fetchone()
        return int(row[0]) if row else 0

    async def _get_latest_health_record(
        self, animal_id: int
    ) -> Optional[Any]:
        """
        So'nggi veterinar yozuvini olish.

        Args:
            animal_id: Jonivor ID

        Returns:
            HealthRecord yoki None
        """
        try:
            result = await self.db.execute(
                select(HealthRecord)
                .where(HealthRecord.animal_id == animal_id)
                .order_by(HealthRecord.recorded_at.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()
        except Exception:
            return None

    async def _get_sensor_data(
        self,
        animal_id: int,
        period_start: datetime,
        period_end: datetime,
    ) -> Optional[dict[str, float]]:
        """
        IoT sensor ma'lumotlarini olish — real DB dan.

        SensorReading jadvalidan kunlik o'rtacha qiymatlar.
        Sensor bo'lmasa None qaytaradi (ADI 70.0 simulyatsiya ishlatadi).

        Args:
            animal_id:    Jonivor ID
            period_start: Period boshi (UTC)
            period_end:   Period oxiri (UTC)

        Returns:
            {"temperature": float, "heart_rate": float, ...} yoki None
        """
        try:
            from app.repositories.sensor_repository import SensorRepository
            sensor_repo = SensorRepository(self.db)
            date_str    = period_start.strftime("%Y-%m-%d")
            return await sensor_repo.get_daily_summary(animal_id, date_str)
        except Exception as e:
            logger.warning(
                f"Sensor data fetch failed for animal {animal_id}: {e}"
            )
            return None

    async def _get_animal(self, animal_id: int) -> Animal:
        """
        Jonivorni olish, topilmasa exception.

        Args:
            animal_id: Jonivor ID

        Returns:
            Animal ORM instance

        Raises:
            EntityNotFoundError: Jonivor topilmasa
        """
        result = await self.db.execute(
            select(Animal).where(Animal.id == animal_id)
        )
        animal = result.scalar_one_or_none()

        if not animal:
            raise EntityNotFoundError(entity="Animal", identifier=animal_id)
        return animal

    # ================================================================ #
    # SAVE (Repository orqali)                                           #
    # ================================================================ #

    async def _save_result(self, result: ADIResult) -> None:
        """
        ADI natijasini DB ga saqlash (Repository orqali).

        Args:
            result: Hisoblangan ADIResult

        Raises:
            DatabaseError: DB xatosi
        """
        try:
            comp = result.components

            log_data = dict(
                calculated_at=    result.calculated_at,
                adi_score=        result.adi_score,
                category=         result.category,
                activity_score=   comp["activity"].score,
                feeding_score=    comp["feeding"].score,
                drinking_score=   comp["drinking"].score,
                movement_score=   comp["movement"].score,
                growth_score=     comp["growth"].score,
                social_score=     comp["social"].score,
                sensor_score=     comp["sensor"].score,
                veterinary_score= comp["veterinary"].score,
                data_quality=     result.data_quality,
                raw_data=         result.raw_data,
                notes=            result.notes,
            )

            log = ADILog(
                animal_id=        result.animal_id,
                calculation_date= result.calculation_date,
                **log_data,
            )

            await self._repo.create(log)
            await self.db.commit()

        except DatabaseError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to save ADI result: {e}", exc_info=True)
            raise DatabaseError(f"ADI saqlashda xato: {e}") from e

    # ================================================================ #
    # UTILITY METHODS (pure static, no DB)                               #
    # ================================================================ #

    @staticmethod
    def _sigmoid_score(
        x: float,
        midpoint: float = 1.0,
        steepness: float = 3.0,
    ) -> float:
        """
        Sigmoid funksiya orqali 0-100 ga o'tkazish.

        x = 0        → ~5
        x = midpoint → ~75
        x = 2        → ~95+

        Args:
            x:          Kiruvchi qiymat (nisbiy, >=0)
            midpoint:   Bu qiymatda ~75 ball
            steepness:  Egri chiziq qiyaligi

        Returns:
            Score 0.0-100.0
        """
        shifted = x - midpoint
        sigmoid = 1.0 / (1.0 + math.exp(-steepness * shifted))
        score   = 5.0 + sigmoid * 90.0
        return max(0.0, min(100.0, score))

    @staticmethod
    def _linear_regression_slope(values: list[float]) -> float:
        """
        Oddiy chiziqli regressiya — slope hisoblash.
        O'sish trendini aniqlash uchun.

        Args:
            values: Vaqt bo'yicha tartibga solingan qiymatlar

        Returns:
            Slope qiymati (manfiy = kamayish, musbat = o'sish)
        """
        n = len(values)
        if n < 2:
            return 0.0

        x_mean = (n - 1) / 2.0
        y_mean = sum(values) / n

        numerator   = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        return 0.0 if denominator == 0 else numerator / denominator

    @staticmethod
    def _expected_growth_slope(age_months: float, species: str) -> float:
        """
        Yosh va turga qarab kutilgan bbox o'sish tezligi.

        Args:
            age_months: Jonivor yoshi (oyda)
            species:    Tur: cattle | sheep | ...

        Returns:
            Kutilgan slope qiymati
        """
        cattle_growth = {
            (0,   6):  0.0008,
            (6,  18):  0.0005,
            (18, 36):  0.0002,
            (36, 999): 0.0000,
        }
        sheep_growth = {
            (0,   4):  0.0010,
            (4,  12):  0.0005,
            (12, 24):  0.0001,
            (24, 999): 0.0000,
        }

        growth_map = {"cattle": cattle_growth, "sheep": sheep_growth}.get(
            species, cattle_growth
        )

        for (min_age, max_age), slope in growth_map.items():
            if min_age <= age_months < max_age:
                return slope

        return 0.0

    @staticmethod
    def _in_zone(cx: float, cy: float, zone: dict[str, float]) -> bool:
        """
        Bbox markazi zonada ekanligini tekshirish.

        Args:
            cx, cy: Normalized bbox center (0.0-1.0)
            zone:   {x_min, x_max, y_min, y_max}

        Returns:
            True agar zonada bo'lsa
        """
        return (
            zone["x_min"] <= cx <= zone["x_max"]
            and zone["y_min"] <= cy <= zone["y_max"]
        )

    @staticmethod
    def _std_dev(values: list[float]) -> float:
        """
        Standart og'ish hisoblash.

        Args:
            values: Raqamlar ro'yxati

        Returns:
            Standart og'ish qiymati
        """
        if len(values) < 2:
            return 0.0
        mean     = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        return math.sqrt(variance)

    @staticmethod
    def _get_period_bounds(date_str: str) -> tuple[datetime, datetime]:
        """
        YYYY-MM-DD dan 24 soatlik UTC oraliq hisoblash.

        Args:
            date_str: YYYY-MM-DD format

        Returns:
            (period_start, period_end) UTC datetime
        """
        date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        return date, date + timedelta(days=1)

    def _generate_notes(
        self,
        components: dict[str, ComponentResult],
        adi_score: float,
        summary: DetectionSummary,
    ) -> Optional[str]:
        """
        ADI natijasiga asosida avtomatik izoh yaratish.

        Args:
            components: 8 ta ComponentResult
            adi_score:  Yakuniy score
            summary:    Deteksiya xulosasi

        Returns:
            Izoh matni yoki None
        """
        issues: list[str] = []

        if summary.total_count == 0:
            issues.append("Bugun kamera tomonidan ko'rilmadi")
        elif summary.total_count < 5:
            issues.append(f"Kamdan-kam ko'rindi ({summary.total_count} marta)")

        feeding = components.get("feeding")
        if feeding and feeding.score is not None and feeding.score < 40:
            issues.append("Oziqlanish past")

        drinking = components.get("drinking")
        if drinking and drinking.score is not None and drinking.score < 40:
            issues.append("Suv iste'moli past")

        growth = components.get("growth")
        if growth and growth.score is not None and growth.score < 40:
            issues.append("O'sish trendi salbiy")

        if not issues:
            if adi_score >= 75:
                return "Jonivor sog'lom va faol"
            return None

        return " | ".join(issues)

    @staticmethod
    def _build_raw_data(
        summary: DetectionSummary,
        components: dict[str, ComponentResult],
        historical_bbox: list[tuple[str, float]],
        sensor_data: Optional[dict[str, float]],
    ) -> dict[str, Any]:
        """
        Debug va retraining uchun to'liq ma'lumot yig'ish.

        Args:
            summary:         Deteksiya xulosasi
            components:      8 ta ComponentResult
            historical_bbox: O'sish uchun tarixiy data
            sensor_data:     IoT sensor ma'lumoti

        Returns:
            JSON-serializable raw data dict
        """
        return {
            "detection_summary": {
                "total_count":      summary.total_count,
                "feeding_visits":   summary.feeding_visits,
                "drinking_visits":  summary.drinking_visits,
                "co_detections":    summary.co_detection_count,
                "bbox_count":       len(summary.bbox_sizes),
                "velocity_samples": len(summary.bbox_velocities),
            },
            "components": {
                name: {
                    "score":    comp.score,
                    "weight":   comp.weight,
                    "has_data": comp.has_data,
                    "detail":   comp.detail,
                }
                for name, comp in components.items()
            },
            "historical_bbox_points": len(historical_bbox),
            "sensor_data":            sensor_data,
            "weights_used":           WEIGHTS,
        }

    @staticmethod
    def _adi_log_to_result(log: ADILog) -> ADIResult:
        """
        ADILog DB modelidan ADIResult ga o'tkazish.

        Args:
            log: ADILog ORM instance

        Returns:
            ADIResult dataclass instance
        """
        components = {
            name: ComponentResult(
                score=getattr(log, f"{name}_score"),
                weight=WEIGHTS[name],
                detail={},
                has_data=getattr(log, f"{name}_score") is not None,
            )
            for name in WEIGHTS
        }

        return ADIResult(
            animal_id=        log.animal_id,
            calculation_date= log.calculation_date,
            calculated_at=    log.calculated_at,
            adi_score=        log.adi_score,
            category=         log.category,
            data_quality=     log.data_quality,
            components=       components,
            raw_data=         log.raw_data or {},
            notes=            log.notes,
        )