"""
Training Data Builder — Feature Engineering Layer.

ML modellar uchun feature vector larni tayyorlaydi.
Barcha feature lar ADILog, Detection va HealthRecord dan olinadi.

FEATURE GROUPS:
    ADI Time-Series (12 ta feature):
        - So'nggi 7/14/30 kun ADI o'rtacha, standart og'ish, min/max
        - Trend slope (chiziqli regressor)
        - Peak dan pasayish nisbati
        - Ketma-ket warning/critical kunlar soni

    Component Features (8 ta feature):
        - Har bir ADI komponentning so'nggi 7 kunlik o'rtachasi
        - Feeding va activity ning keskin pasayishi

    Presence & Activity (4 ta feature):
        - So'nggi ko'rinishdan o'tgan kunlar
        - Detection zichligi
        - Aktiv hafta kunlari nisbati

    Health History (4 ta feature):
        - So'nggi 30 kunda health event soni
        - Kritik event soni
        - Eng so'nggi event jiddiyligini raqamda ifodalash
        - Unresolved eventlar soni

    Animal Meta (3 ta feature):
        - Yosh (oyda)
        - Tur (encoded)
        - Jins (encoded)

JAMI: 31 ta feature
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from typing import Optional

import numpy as np
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.adi_log import ADILog
from app.models.animal import Animal, AnimalSpecies
from app.models.detection import Detection
from app.models.health_record import HealthRecord, HealthRecordSeverity

logger = logging.getLogger(__name__)

# ── Feature konstantalari ─────────────────────────────────────────────────── #

FEATURE_NAMES: list[str] = [
    # ADI time-series
    "adi_mean_7d",
    "adi_mean_14d",
    "adi_mean_30d",
    "adi_std_7d",
    "adi_std_30d",
    "adi_min_7d",
    "adi_min_30d",
    "adi_max_30d",
    "adi_trend_slope",       # +: yaxshilanmoqda, -: yomonlashmoqda
    "adi_drop_from_peak",    # peak - hozirgi (katta = xavfli)
    "consecutive_warning_days",
    "days_in_warning_14d",

    # ADI komponentlar (so'nggi 7 kun o'rtacha)
    "activity_mean_7d",
    "feeding_mean_7d",
    "drinking_mean_7d",
    "movement_mean_7d",
    "growth_mean_7d",
    "social_mean_7d",
    "feeding_drop_ratio",    # so'nggi 7 / oldingi 7 (1.0 dan past = kamaymoqda)
    "activity_drop_ratio",

    # Presence & detection
    "days_since_last_detection",
    "detection_density_7d",  # detection/kun
    "active_days_ratio_14d", # deteksiya bo'lgan kunlar/14

    # Health history
    "health_events_30d",
    "critical_events_30d",
    "unresolved_events_count",
    "last_event_severity_score",  # normal=0, warning=1, critical=2

    # Animal meta
    "age_months",
    "species_encoded",       # cattle=0, sheep=1, goat=2, horse=3, other=4
    "gender_encoded",        # male=0, female=1, unknown=2
    "data_availability",     # nechta feature haqiqiy ma'lumot bor (0-1)
]

SPECIES_ENCODING = {
    "cattle": 0, "sheep": 1, "goat": 2, "horse": 3, "other": 4,
}
GENDER_ENCODING = {"male": 0, "female": 1, "unknown": 2}


class TrainingDataBuilder:
    """
    ML feature vector tayyorlovchi.

    Bir jonivor uchun bir sana (target_date) asosida
    barcha feature larni hisoblaydi.

    USAGE:
        builder = TrainingDataBuilder(db)
        features = await builder.build_features(animal_id=5, target_date="2026-02-28")
        # → {"adi_mean_7d": 72.3, "feeding_drop_ratio": 0.85, ...}
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # PUBLIC API
    # =========================================================================

    async def build_features(
        self,
        animal_id: int,
        target_date: str,
    ) -> Optional[dict[str, float]]:
        """
        Jonivor uchun ML feature vector hisoblash.

        Args:
            animal_id:   Tahlil qilinadigan jonivor ID
            target_date: Bashorat sanasi (YYYY-MM-DD)

        Returns:
            Feature dict yoki None (ADI ma'lumoti yetarli emas)
        """
        try:
            # Ma'lumotlarni parallel olish
            animal     = await self._get_animal(animal_id)
            adi_logs   = await self._get_adi_logs(animal_id, target_date, days=35)
            detections = await self._get_recent_detections(animal_id, target_date, days=14)
            health_recs = await self._get_health_records(animal_id, target_date, days=30)

            if not animal:
                logger.warning(f"[features] Animal {animal_id} not found")
                return None

            # Minimal ma'lumot talabi: kamida 3 ta ADI yozuv
            if len(adi_logs) < 3:
                logger.info(
                    f"[features] Animal {animal_id}: insufficient ADI data "
                    f"({len(adi_logs)} logs, need ≥3)"
                )
                return None

            features = {}

            # ── ADI time-series features ──────────────────────────────────── #
            features.update(self._compute_adi_features(adi_logs))

            # ── Component features ────────────────────────────────────────── #
            features.update(self._compute_component_features(adi_logs))

            # ── Presence features ─────────────────────────────────────────── #
            features.update(self._compute_presence_features(
                detections, target_date
            ))

            # ── Health history features ───────────────────────────────────── #
            features.update(self._compute_health_features(health_recs))

            # ── Animal meta features ──────────────────────────────────────── #
            features.update(self._compute_meta_features(animal))

            # ── Data availability (qancha feature haqiqiy) ───────────────── #
            real_count = sum(
                1 for v in features.values()
                if v is not None and not math.isnan(v)
            )
            features["data_availability"] = real_count / len(FEATURE_NAMES)

            # NaN / None → 0.0 (model None qabul qilmaydi)
            features = {
                k: float(v) if v is not None and not math.isnan(float(v)) else 0.0
                for k, v in features.items()
            }

            return features

        except Exception as exc:
            logger.error(
                f"[features] build_features failed for animal {animal_id}: {exc}",
                exc_info=True,
            )
            return None

    async def build_features_batch(
        self,
        animal_ids: list[int],
        target_date: str,
    ) -> dict[int, dict[str, float]]:
        """
        Bir nechta jonivor uchun feature vector batch hisoblash.

        Args:
            animal_ids:  Jonivor ID lari ro'yxati
            target_date: YYYY-MM-DD

        Returns:
            {animal_id: feature_dict} — ma'lumoti yetarli jonivorlar uchun
        """
        results: dict[int, dict[str, float]] = {}
        for aid in animal_ids:
            feats = await self.build_features(aid, target_date)
            if feats is not None:
                results[aid] = feats
        return results

    def feature_vector(self, features: dict[str, float]) -> np.ndarray:
        """
        Feature dict ni numpy array ga (ML modellar uchun) aylantirish.

        FEATURE_NAMES tartibida — model training bilan mos bo'lishi kerak.

        Args:
            features: build_features() natijasi

        Returns:
            shape (31,) float64 numpy array
        """
        return np.array(
            [features.get(name, 0.0) for name in FEATURE_NAMES],
            dtype=np.float64,
        )

    # =========================================================================
    # ADI TIME-SERIES FEATURES
    # =========================================================================

    def _compute_adi_features(self, logs: list[ADILog]) -> dict[str, float]:
        """ADI trend va statistik feature lar."""
        scores = [log.adi_score for log in logs]  # yangi → eski tartibda

        def window_scores(days: int) -> list[float]:
            return scores[:days] if len(scores) >= days else scores

        s7  = window_scores(7)
        s14 = window_scores(14)
        s30 = window_scores(30)

        # O'rtacha
        mean_7  = float(np.mean(s7))  if s7  else 50.0
        mean_14 = float(np.mean(s14)) if s14 else 50.0
        mean_30 = float(np.mean(s30)) if s30 else 50.0

        # Standart og'ish (volatillik)
        std_7  = float(np.std(s7))  if len(s7)  > 1 else 0.0
        std_30 = float(np.std(s30)) if len(s30) > 1 else 0.0

        # Min/max
        min_7  = float(min(s7))  if s7  else 50.0
        min_30 = float(min(s30)) if s30 else 50.0
        max_30 = float(max(s30)) if s30 else 50.0

        # Trend slope: chiziqli regressor (sklearn ishlatmasdan)
        # Yangi → eskiga x=-t tartibida: slope negatif = yomonlashmoqda
        slope = 0.0
        if len(s30) >= 5:
            n = len(s30)
            x = np.arange(n, 0, -1, dtype=float)  # [n, n-1, ..., 1]
            x_mean = float(np.mean(x))
            y_mean = float(np.mean(s30))
            numerator   = float(np.sum((x - x_mean) * (np.array(s30) - y_mean)))
            denominator = float(np.sum((x - x_mean) ** 2))
            if denominator > 0:
                slope = numerator / denominator  # kuniga o'zgarish

        # Peak dan pasayish (so'nggi 7 kun o'rtacha vs 30 kun max)
        drop_from_peak = max(0.0, max_30 - mean_7)

        # Ketma-ket warning/critical kunlar (eng so'nggi)
        consecutive_warn = 0
        for log in logs:
            if log.category in ("warning", "critical"):
                consecutive_warn += 1
            else:
                break  # birinchi yaxshi kun — to'xtaymiz

        # 14 kunda warning/critical kunlar soni
        days_in_warning = sum(
            1 for log in logs[:14]
            if log.category in ("warning", "critical")
        )

        return {
            "adi_mean_7d":             mean_7,
            "adi_mean_14d":            mean_14,
            "adi_mean_30d":            mean_30,
            "adi_std_7d":              std_7,
            "adi_std_30d":             std_30,
            "adi_min_7d":              min_7,
            "adi_min_30d":             min_30,
            "adi_max_30d":             max_30,
            "adi_trend_slope":         slope,
            "adi_drop_from_peak":      drop_from_peak,
            "consecutive_warning_days": float(consecutive_warn),
            "days_in_warning_14d":     float(days_in_warning),
        }

    # =========================================================================
    # COMPONENT FEATURES
    # =========================================================================

    def _compute_component_features(self, logs: list[ADILog]) -> dict[str, float]:
        """ADI komponent o'rtachalari va drop ratio lar."""

        def mean_component(attr: str, days: int) -> float:
            vals = [
                getattr(log, attr)
                for log in logs[:days]
                if getattr(log, attr) is not None
            ]
            return float(np.mean(vals)) if vals else 0.0

        activity_7  = mean_component("activity_score",  7)
        feeding_7   = mean_component("feeding_score",   7)
        drinking_7  = mean_component("drinking_score",  7)
        movement_7  = mean_component("movement_score",  7)
        growth_7    = mean_component("growth_score",    7)
        social_7    = mean_component("social_score",    7)

        # Drop ratio: so'nggi 7 kun vs oldingi 7 kun (8-14)
        activity_14_21 = mean_component("activity_score", 21)
        feeding_14_21  = mean_component("feeding_score",  21)

        feeding_drop  = (feeding_7  / feeding_14_21)  if feeding_14_21  > 1 else 1.0
        activity_drop = (activity_7 / activity_14_21) if activity_14_21 > 1 else 1.0

        # Klamp: [0.0, 2.0]
        feeding_drop  = max(0.0, min(2.0, feeding_drop))
        activity_drop = max(0.0, min(2.0, activity_drop))

        return {
            "activity_mean_7d":   activity_7,
            "feeding_mean_7d":    feeding_7,
            "drinking_mean_7d":   drinking_7,
            "movement_mean_7d":   movement_7,
            "growth_mean_7d":     growth_7,
            "social_mean_7d":     social_7,
            "feeding_drop_ratio": feeding_drop,
            "activity_drop_ratio": activity_drop,
        }

    # =========================================================================
    # PRESENCE FEATURES
    # =========================================================================

    def _compute_presence_features(
        self,
        detections: list[Detection],
        target_date: str,
    ) -> dict[str, float]:
        """Kamera ko'rinishi va detection zichligi."""
        target_dt = datetime.strptime(target_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )

        # So'nggi ko'rinishdan o'tgan kunlar
        if detections:
            last_ts = max(d.timestamp for d in detections)
            days_since = (target_dt - last_ts).total_seconds() / 86400
            days_since = max(0.0, days_since)
        else:
            days_since = 99.0  # Ma'lumot yo'q → yuqori xavf signali

        # So'nggi 7 kunda detection/kun zichligi
        cutoff_7 = target_dt - timedelta(days=7)
        det_7d = [d for d in detections if d.timestamp >= cutoff_7]
        density_7d = len(det_7d) / 7.0

        # 14 kunda kamida 1 ta detection bo'lgan kunlar nisbati
        cutoff_14 = target_dt - timedelta(days=14)
        det_14d = [d for d in detections if d.timestamp >= cutoff_14]
        active_dates = {d.timestamp.date() for d in det_14d}
        active_ratio = len(active_dates) / 14.0

        return {
            "days_since_last_detection": days_since,
            "detection_density_7d":     density_7d,
            "active_days_ratio_14d":    active_ratio,
        }

    # =========================================================================
    # HEALTH HISTORY FEATURES
    # =========================================================================

    def _compute_health_features(self, records: list[HealthRecord]) -> dict[str, float]:
        """Veterinar yozuvlari tarixidan feature lar."""
        severity_scores = {
            "normal": 0,
            "warning": 1,
            "critical": 2,
        }

        total_events    = len(records)
        critical_events = sum(
            1 for r in records
            if str(r.severity).lower() in ("critical", "healthrecordseverity.critical")
        )
        unresolved = sum(1 for r in records if not r.is_resolved)

        # Eng so'nggi event jiddiyligi
        last_severity = 0.0
        if records:
            sev_str = str(records[0].severity).lower().replace("healthrecordseverity.", "")
            last_severity = float(severity_scores.get(sev_str, 0))

        return {
            "health_events_30d":       float(total_events),
            "critical_events_30d":     float(critical_events),
            "unresolved_events_count": float(unresolved),
            "last_event_severity_score": last_severity,
        }

    # =========================================================================
    # ANIMAL META FEATURES
    # =========================================================================

    def _compute_meta_features(self, animal: Animal) -> dict[str, float]:
        """Jonivor xususiyatlaridan feature lar."""
        age_months = 0.0
        if animal.birth_date:
            age_months = (
                datetime.utcnow() - animal.birth_date.replace(tzinfo=None)
            ).days / 30.44

        species_enc = SPECIES_ENCODING.get(
            str(animal.species).lower().replace("animalspecies.", ""), 4
        )
        gender_enc = GENDER_ENCODING.get(
            str(animal.gender).lower().replace("animalgender.", ""), 2
        )

        return {
            "age_months":      age_months,
            "species_encoded": float(species_enc),
            "gender_encoded":  float(gender_enc),
        }

    # =========================================================================
    # DB QUERIES
    # =========================================================================

    async def _get_animal(self, animal_id: int) -> Optional[Animal]:
        result = await self.db.execute(
            select(Animal).where(Animal.id == animal_id)
        )
        return result.scalar_one_or_none()

    async def _get_adi_logs(
        self,
        animal_id: int,
        before_date: str,
        days: int,
    ) -> list[ADILog]:
        """Berilgan sanadan oldingi ADI loglar (yangi → eski)."""
        from_date = (
            datetime.strptime(before_date, "%Y-%m-%d") - timedelta(days=days)
        ).strftime("%Y-%m-%d")

        result = await self.db.execute(
            select(ADILog)
            .where(and_(
                ADILog.animal_id == animal_id,
                ADILog.calculation_date <= before_date,
                ADILog.calculation_date >= from_date,
            ))
            .order_by(ADILog.calculation_date.desc())
        )
        return list(result.scalars().all())

    async def _get_recent_detections(
        self,
        animal_id: int,
        before_date: str,
        days: int,
    ) -> list[Detection]:
        cutoff = datetime.strptime(before_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        ) - timedelta(days=days)

        result = await self.db.execute(
            select(Detection)
            .where(and_(
                Detection.animal_id == animal_id,
                Detection.timestamp  >= cutoff,
            ))
            .order_by(Detection.timestamp.desc())
        )
        return list(result.scalars().all())

    async def _get_health_records(
        self,
        animal_id: int,
        before_date: str,
        days: int,
    ) -> list[HealthRecord]:
        cutoff = datetime.strptime(before_date, "%Y-%m-%d") - timedelta(days=days)

        result = await self.db.execute(
            select(HealthRecord)
            .where(and_(
                HealthRecord.animal_id  == animal_id,
                HealthRecord.recorded_at >= cutoff,
            ))
            .order_by(HealthRecord.recorded_at.desc())
        )
        return list(result.scalars().all())