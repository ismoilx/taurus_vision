"""
Taurus Vision — Behavior Analysis Service (Sprint 11-12)

Jonivorlar xatti-harakatini tahlil qiluvchi biznes mantiq qatlami.

ARXITEKTURA:
    API endpoint (behavior.py)
        ↓  faqat HTTP parametrlar va autentifikatsiya
    BehaviorService  ← bu fayl
        ↓  barcha biznes mantiq, DB so'rovlar, hisoblashlar
    SQLAlchemy ORM (Detection, Animal, ADILog)

KOMPONENTLAR VA OG'IRLIKLAR:
    Faollik   (activity):  35% — kunlik detection soni
    Oziqlanish (feeding):  35% — feeding zonasi tashrifi
    Harakat   (movement):  20% — bbox cx standart og'ishi
    Ijtimoiy  (social):    10% — birgalikda aniqlanish nisbati

ZONA KOORDINATALARI (normalized 0–1):
    Feeding zone:  x=[0.10, 0.50], y=[0.20, 0.60]
    Resting zone:  x=[0.50, 0.90], y=[0.50, 0.90]
    Drinking zone: x=[0.55, 0.95], y=[0.10, 0.45]
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession


def _ensure_tz(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC). SQLite returns naive datetimes."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt

from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.adi_log import ADILog
from app.schemas.behavior import (
    AnomalyEntry,
    BehaviorAnalysis,
    BehaviorScore,
    BehaviorTimelineEntry,
    HerdBehaviorSummary,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ZONA KOORDINATALARI VA CHEGARALAR
# =============================================================================

_FEEDING_ZONE: dict = {"x1": 0.10, "y1": 0.20, "x2": 0.50, "y2": 0.60}
_RESTING_ZONE: dict = {"x1": 0.50, "y1": 0.50, "x2": 0.90, "y2": 0.90}
_DRINKING_ZONE: dict = {"x1": 0.55, "y1": 0.10, "x2": 0.95, "y2": 0.45}

_HIGH_ACTIVITY: int = 48       # Kuniga detection soni (100% = bu)
_FEEDING_GAP_H: int = 12       # Soat — bu dan ko'p bo'lsa anomaliya
_MOVEMENT_ACTIVE: float = 0.15  # bbox cx std — bu dan yuqori = faol
_MOVEMENT_INACTIVE: float = 0.05  # bbox cx std — bu dan past = harakatsiz

# Herd summary uchun maksimal jonivor soni (performance)
_MAX_HERD_SIZE: int = 100


# =============================================================================
# SCORING HELPERS — sof funksiyalar, DB ga bog'liq emas
# =============================================================================

def _score_to_status(pct: float) -> str:
    """
    Foiz qiymatini holat nomiga aylantiradi.

    Args:
        pct: 0–100 oraliqidagi foiz qiymati

    Returns:
        Holat nomi: excellent / good / fair / poor / critical
    """
    if pct >= 90:
        return "excellent"
    if pct >= 75:
        return "good"
    if pct >= 55:
        return "fair"
    if pct >= 35:
        return "poor"
    return "critical"


def _compute_activity_score(det_count: int, period_hours: int) -> BehaviorScore:
    """
    Faollik darajasini hisoblaydi.

    Mezon: `period_hours / 24 * HIGH_ACTIVITY` detection = 100%.

    Args:
        det_count:    Davr ichidagi detection soni
        period_hours: Tahlil davri (soat)

    Returns:
        BehaviorScore — faollik ko'rsatkichi
    """
    expected = max(1, int(_HIGH_ACTIVITY * period_hours / 24))
    raw_pct = min(100.0, det_count / expected * 100)
    status = _score_to_status(raw_pct)

    if det_count == 0:
        desc = "Hech qanday aktivlik aniqlanmadi"
    elif raw_pct >= 80:
        desc = f"Yuqori faollik ({det_count} ta detection)"
    elif raw_pct >= 50:
        desc = f"O'rtacha faollik ({det_count} ta detection)"
    else:
        desc = f"Past faollik ({det_count} ta detection, kutilgan: {expected})"

    return BehaviorScore(
        value=float(det_count),
        max_value=float(expected),
        percentage=round(raw_pct, 1),
        status=status,
        description=desc,
    )


def _compute_feeding_score(
    feeding_visits: int,
    period_hours: int,
    last_feeding_h: Optional[float],
) -> BehaviorScore:
    """
    Oziqlanish ko'rsatkichini hisoblaydi.

    Mezon: har 6 soatda bir marta oziqlanish normal.
    So'nggi oziqlanish FEEDING_GAP_H dan uzoq bo'lsa — jazo qo'shiladi.

    Args:
        feeding_visits:  Feeding zonasiga tashrif soni
        period_hours:    Tahlil davri (soat)
        last_feeding_h:  So'nggi oziqlanishdan o'tgan soat (None = ma'lumot yo'q)

    Returns:
        BehaviorScore — oziqlanish ko'rsatkichi
    """
    expected = max(1, period_hours // 6)
    raw_pct = min(100.0, feeding_visits / expected * 100)

    # So'nggi oziqlanish uzoq vaqt oldin bo'lsa — jazo
    if last_feeding_h is not None and last_feeding_h > _FEEDING_GAP_H:
        penalty = min(40.0, (last_feeding_h - _FEEDING_GAP_H) * 3)
        raw_pct = max(0.0, raw_pct - penalty)

    status = _score_to_status(raw_pct)

    if raw_pct >= 75:
        desc = f"Muntazam oziqlanmoqda ({feeding_visits} ta tashrif)"
    elif raw_pct >= 40:
        desc = f"Oziqlanish kam ({feeding_visits} ta tashrif, kutilgan: {expected})"
    else:
        desc = "Oziqlanish juda kam yoki to'xtagan"

    if last_feeding_h is not None:
        desc += f". Oxirgi: {last_feeding_h:.1f} soat oldin"

    return BehaviorScore(
        value=round(float(feeding_visits), 0),
        max_value=float(expected),
        percentage=round(raw_pct, 1),
        status=status,
        description=desc,
    )


def _compute_movement_score(std_cx: float) -> BehaviorScore:
    """
    Harakat intensivligini hisoblaydi.

    bbox markaz nuqtasi (cx) standart og'ishi asosida baholash:
        0.15+ → juda faol
        0.08+ → o'rtacha
        0.05+ → kam harakat
        0+    → deyarli harakatsiz

    Args:
        std_cx: bbox cx standart og'ishi (0 dan yuqori)

    Returns:
        BehaviorScore — harakat ko'rsatkichi
    """
    if std_cx >= _MOVEMENT_ACTIVE:
        pct = 90.0
        desc = f"Faol harakat (std={std_cx:.3f})"
    elif std_cx >= 0.08:
        pct = 75.0
        desc = f"O'rtacha harakat (std={std_cx:.3f})"
    elif std_cx >= _MOVEMENT_INACTIVE:
        pct = 40.0
        desc = f"Kam harakat (std={std_cx:.3f})"
    elif std_cx > 0:
        pct = 20.0
        desc = f"Deyarli harakatsiz (std={std_cx:.3f})"
    else:
        pct = 0.0
        desc = "Harakat ma'lumoti yo'q"

    return BehaviorScore(
        value=round(std_cx, 4),
        max_value=_MOVEMENT_ACTIVE,
        percentage=round(pct, 1),
        status=_score_to_status(pct),
        description=desc,
    )


def _compute_social_score(social_ratio: float) -> BehaviorScore:
    """
    Ijtimoiy xulq ko'rsatkichini hisoblaydi.

    social_ratio = birgalikda aniqlanish / jami detection.
    0.3+ → ijtimoiy, < 0.05 → izolyatsiya.

    Args:
        social_ratio: 0.0 dan 1.0 gacha bo'lgan nisbat

    Returns:
        BehaviorScore — ijtimoiy xulq ko'rsatkichi
    """
    if social_ratio >= 0.3:
        pct = 90.0
        desc = f"Ijtimoiy jonivor ({social_ratio:.0%} vaqt birgalikda)"
    elif social_ratio >= 0.1:
        pct = 75.0
        desc = f"O'rtacha ijtimoiy ({social_ratio:.0%} vaqt birgalikda)"
    elif social_ratio > 0:
        pct = 35.0
        desc = f"Kam ijtimoiy ({social_ratio:.0%} vaqt birgalikda)"
    else:
        pct = 15.0
        desc = "Boshqa jonivorlar bilan birgalikda aniqlanmadi"

    return BehaviorScore(
        value=round(social_ratio, 3),
        max_value=1.0,
        percentage=round(pct, 1),
        status=_score_to_status(pct),
        description=desc,
    )


def _compute_overall_score(
    activity: BehaviorScore,
    feeding: BehaviorScore,
    movement: BehaviorScore,
    social: BehaviorScore,
) -> float:
    """
    Umumiy xatti-harakat balini vazn bo'yicha hisoblaydi.

    Og'irliklar:
        Faollik:    35%
        Oziqlanish: 35%
        Harakat:    20%
        Ijtimoiy:   10%

    Args:
        activity:  Faollik ko'rsatkichi
        feeding:   Oziqlanish ko'rsatkichi
        movement:  Harakat ko'rsatkichi
        social:    Ijtimoiy xulq ko'rsatkichi

    Returns:
        Umumiy ball (0–100, bir o'nlikgacha yaxlitlangan)
    """
    return round(
        activity.percentage * 0.35
        + feeding.percentage * 0.35
        + movement.percentage * 0.20
        + social.percentage * 0.10,
        1,
    )


def _build_anomalies_and_recommendations(
    activity: BehaviorScore,
    feeding: BehaviorScore,
    movement: BehaviorScore,
    social: BehaviorScore,
    last_feeding_h: Optional[float],
    detection_count: int,
) -> tuple[list[str], list[str]]:
    """
    Anomaliya va tavsiyalar ro'yxatini tuzadi.

    Args:
        activity:        Faollik ko'rsatkichi
        feeding:         Oziqlanish ko'rsatkichi
        movement:        Harakat ko'rsatkichi
        social:          Ijtimoiy xulq ko'rsatkichi
        last_feeding_h:  So'nggi oziqlanishdan o'tgan soat
        detection_count: Jami detection soni

    Returns:
        (anomalies_list, recommendations_list) — ikkita ro'yxat
    """
    anomalies: list[str] = []
    recs: list[str] = []

    if detection_count == 0:
        anomalies.append("24 soat davomida hech qanday detection yo'q")
        recs.append(
            "Kamera ishlayotganini va jonivor ferma ichida ekanligini tekshiring"
        )

    if feeding.percentage < 30:
        anomalies.append(f"Oziqlanish juda kam: {feeding.value:.0f} ta tashrif")
        recs.append("Jonivorni yem-xashak bilan ta'minlashni tekshiring")

    if last_feeding_h is not None and last_feeding_h > _FEEDING_GAP_H:
        anomalies.append(
            f"So'nggi oziqlanishdan {last_feeding_h:.1f} soat o'tdi "
            f"(chegarasi: {_FEEDING_GAP_H} soat)"
        )
        recs.append(
            "Veterinar ko'rigini rejalashtiring — ishtaha yo'qolishi xavf belgisi"
        )

    if movement.percentage < 25 and detection_count > 0:
        anomalies.append(f"Juda kam harakat aniqlandi (std={movement.value:.3f})")
        recs.append("Jonivor yotib qolgan bo'lishi mumkin — ko'zdan kechiring")

    if activity.percentage < 20 and detection_count > 0:
        anomalies.append(f"Juda past faollik: {activity.value:.0f} ta detection")
        recs.append("Sog'liq tekshiruvi o'tkazing")

    if social.percentage < 20 and detection_count > 5:
        anomalies.append("Izolyatsiya belgilari — boshqa jonivorlardan ajralgan")
        recs.append(
            "Podadan ajralish — kasallik yoki stressning belgisi bo'lishi mumkin"
        )

    return anomalies, recs


def _detect_adi_trend(adi_7day: list[float]) -> Optional[str]:
    """
    7 kunlik ADI ma'lumotidan trend yo'nalishini aniqlaydi.

    Args:
        adi_7day: So'nggi 7 kunlik ADI ballari (eski → yangi)

    Returns:
        "improving" | "stable" | "declining" | None (ma'lumot yetarli emas)
    """
    if len(adi_7day) < 2:
        return None

    diff = adi_7day[-1] - adi_7day[0]
    if diff >= 5:
        return "improving"
    if diff <= -5:
        return "declining"
    return "stable"


def _classify_anomaly_type(anomaly_text: str) -> tuple[str, str]:
    """
    Anomaliya matnidan tur va darajani aniqlaydi.

    Args:
        anomaly_text: Anomaliya tavsifi (o'zbek tilida)

    Returns:
        (anomaly_type, severity) juftligi
    """
    text_lower = anomaly_text.lower()

    if "oziqlanmagan" in text_lower or "oziqlanish" in text_lower:
        severity = "critical" if "to'xtagan" in text_lower else "warning"
        return "feeding_gap", severity

    if "detection yo'q" in text_lower or "aktivlik" in text_lower:
        return "inactivity", "critical"

    if "harakat" in text_lower:
        return "low_movement", "warning"

    if "izolyatsiya" in text_lower:
        return "social_isolation", "warning"

    return "other", "warning"


# =============================================================================
# BEHAVIOR SERVICE
# =============================================================================


class BehaviorService:
    """
    Jonivor xatti-harakat tahlili uchun servis qatlami.

    Barcha biznes mantiq, DB so'rovlari va hisoblashlar shu yerda.
    API endpointlari faqat HTTP parametrlari va autentifikatsiyani boshqaradi.

    Foydalanish:
        service = BehaviorService(db)
        result = await service.analyze_animal(animal_id=1, period_hours=24)
    """

    def __init__(self, db: AsyncSession) -> None:
        """
        Servis misoli yaratadi.

        Args:
            db: Asinxron SQLAlchemy sessiyasi (FastAPI Depends orqali uzatiladi)
        """
        self._db = db

    # ─── Asosiy tahlil ────────────────────────────────────────────────────────

    async def analyze_animal(
        self,
        animal_id: int,
        period_hours: int = 24,
    ) -> BehaviorAnalysis:
        """
        Jonivor xatti-harakatini tahlil qiladi.

        Args:
            animal_id:    Tahlil qilinadigan jonivor ID
            period_hours: Tahlil davri soatlarda (1–168)

        Returns:
            BehaviorAnalysis — to'liq tahlil natijasi

        Raises:
            ValueError: Jonivor topilmasa
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=period_hours)

        # 1. Jonivorni olish
        animal = await self._db.get(Animal, animal_id)
        if not animal:
            raise ValueError(f"Jonivor #{animal_id} topilmadi")

        # 2. Davr ichidagi detectionlar
        detections = (
            await self._db.execute(
                select(Detection)
                .where(
                    and_(
                        Detection.animal_id == animal_id,
                        Detection.timestamp >= period_start,
                        Detection.timestamp <= now,
                    )
                )
                .order_by(Detection.timestamp)
            )
        ).scalars().all()

        det_count = len(detections)

        # 3. Faollik ko'rsatkichi (har doim hisoblanadi)
        activity_score = _compute_activity_score(det_count, period_hours)

        # 4. Ma'lumot bo'lmasa — nol ko'rsatkichlar
        if det_count == 0:
            return self._build_empty_analysis(
                animal_id=animal_id,
                animal_tag=animal.tag_id,
                period_start=period_start,
                period_end=now,
                activity_score=activity_score,
            )

        # 5. Oziqlanish ko'rsatkichi
        feeding_visits, last_feeding_h = self._extract_feeding_data(detections, now)
        feeding_score = _compute_feeding_score(feeding_visits, period_hours, last_feeding_h)

        # 6. Harakat ko'rsatkichi
        std_cx = self._compute_std_cx(detections)
        movement_score = _compute_movement_score(std_cx)

        # 7. Ijtimoiy xulq ko'rsatkichi
        social_ratio = await self._compute_social_ratio(detections, animal_id, det_count)
        social_score = _compute_social_score(social_ratio)

        # 8. Anomaliyalar va tavsiyalar
        anomalies, recs = _build_anomalies_and_recommendations(
            activity_score, feeding_score, movement_score, social_score,
            last_feeding_h, det_count,
        )

        # 9. Umumiy ball
        overall = _compute_overall_score(
            activity_score, feeding_score, movement_score, social_score
        )

        # 10. ADI 7 kunlik trend
        adi_7day = await self._fetch_adi_7day(animal_id, now)
        adi_trend = _detect_adi_trend(adi_7day)

        return BehaviorAnalysis(
            animal_id=animal_id,
            animal_tag=animal.tag_id,
            period_start=period_start.isoformat(),
            period_end=now.isoformat(),
            detection_count=det_count,
            activity=activity_score,
            feeding=feeding_score,
            movement=movement_score,
            social=social_score,
            overall_score=overall,
            overall_status=_score_to_status(overall),
            anomalies=anomalies,
            recommendations=recs,
            adi_trend=adi_trend,
            adi_7day=adi_7day,
            analyzed_at=now.isoformat(),
        )

    # ─── Poda xulosasi ────────────────────────────────────────────────────────

    async def get_herd_summary(
        self,
        period_hours: int = 24,
        attention_limit: int = 10,
    ) -> HerdBehaviorSummary:
        """
        Barcha aktiv jonivorlar uchun umumiy xatti-harakat xulosasi.

        Performance eslatmasi: Har jonivor uchun alohida DB so'rovi yuboriladi.
        Katta podalarda `attention_limit` parametrini pastroq qiling.

        Args:
            period_hours:     Tahlil davri soatlarda (1–72)
            attention_limit:  Diqqat talab qiladiganlar maksimal soni

        Returns:
            HerdBehaviorSummary — poda umumiy holati
        """
        now = datetime.now(timezone.utc)

        # Aktiv jonivorlarni olish (maksimal _MAX_HERD_SIZE)
        animals = (
            await self._db.execute(
                select(Animal)
                .where(Animal.status == AnimalStatus.ACTIVE)
                .order_by(Animal.id)
                .limit(_MAX_HERD_SIZE)
            )
        ).scalars().all()

        total = len(animals)

        counts: dict[str, int] = {
            "excellent": 0, "good": 0, "fair": 0,
            "poor": 0, "critical": 0, "no_data": 0,
        }
        activity_vals: list[float] = []
        feeding_vals: list[float] = []
        movement_vals: list[float] = []
        social_vals: list[float] = []
        overall_vals: list[float] = []
        attention_list: list[dict] = []

        for animal in animals:
            try:
                analysis = await self.analyze_animal(animal.id, period_hours)

                status = analysis.overall_status
                if analysis.detection_count == 0:
                    counts["no_data"] += 1
                else:
                    counts[status] = counts.get(status, 0) + 1

                activity_vals.append(analysis.activity.percentage)
                feeding_vals.append(analysis.feeding.percentage)
                movement_vals.append(analysis.movement.percentage)
                social_vals.append(analysis.social.percentage)
                overall_vals.append(analysis.overall_score)

                # Diqqat talab qiladigan jonivorlar
                if (
                    analysis.overall_score < 50 or len(analysis.anomalies) > 0
                ) and len(attention_list) < attention_limit:
                    attention_list.append(
                        {
                            "animal_id": animal.id,
                            "animal_tag": animal.tag_id,
                            "overall_score": analysis.overall_score,
                            "status": analysis.overall_status,
                            "anomalies": analysis.anomalies[:2],
                            "adi_trend": analysis.adi_trend,
                        }
                    )

            except Exception as exc:
                logger.warning(
                    "Herd summary: animal %s tahlil xatosi: %s",
                    animal.id,
                    exc,
                )
                counts["no_data"] += 1

        # Diqqat talab qiladiganlarni score bo'yicha saralash (eng pastdan)
        attention_list.sort(key=lambda x: x["overall_score"])

        def _avg(vals: list[float]) -> float:
            return round(sum(vals) / len(vals), 1) if vals else 0.0

        return HerdBehaviorSummary(
            total_animals=total,
            analyzed_count=total - counts["no_data"],
            period=f"So'nggi {period_hours} soat",
            excellent_count=counts["excellent"],
            good_count=counts["good"],
            fair_count=counts["fair"],
            poor_count=counts["poor"],
            critical_count=counts["critical"],
            no_data_count=counts["no_data"],
            avg_activity=_avg(activity_vals),
            avg_feeding=_avg(feeding_vals),
            avg_movement=_avg(movement_vals),
            avg_social=_avg(social_vals),
            avg_overall=_avg(overall_vals),
            attention_needed=attention_list,
            generated_at=now.isoformat(),
        )

    # ─── Timeline ─────────────────────────────────────────────────────────────

    async def get_animal_timeline(
        self,
        animal_id: int,
        period_hours: int = 24,
    ) -> list[BehaviorTimelineEntry]:
        """
        Jonivor xatti-harakatini soatlik kesimda qaytaradi.

        Frontend grafiklari uchun mo'ljallangan.

        Args:
            animal_id:    Jonivor ID
            period_hours: Necha soat orqaga qarash (6–168)

        Returns:
            Soatlik BehaviorTimelineEntry ro'yxati (xronologik tartibda)

        Raises:
            ValueError: Jonivor topilmasa
        """
        animal = await self._db.get(Animal, animal_id)
        if not animal:
            raise ValueError(f"Jonivor #{animal_id} topilmadi")

        now = datetime.now(timezone.utc)
        period_start = now - timedelta(hours=period_hours)

        detections = (
            await self._db.execute(
                select(Detection)
                .where(
                    and_(
                        Detection.animal_id == animal_id,
                        Detection.timestamp >= period_start,
                    )
                )
                .order_by(Detection.timestamp)
            )
        ).scalars().all()

        # Soat bo'yicha guruhlash
        timeline: dict[str, dict] = {}
        for det in detections:
            hour_key = det.timestamp.replace(
                minute=0, second=0, microsecond=0
            ).isoformat()

            if hour_key not in timeline:
                timeline[hour_key] = {
                    "hour": hour_key,
                    "detections": 0,
                    "feeding_visits": 0,
                    "cx_values": [],
                    "camera_id": det.camera_id,
                }

            timeline[hour_key]["detections"] += 1

            bbox = det.bbox or {}
            cx = bbox.get("x", 0) + bbox.get("w", 0) / 2
            cy = bbox.get("y", 0) + bbox.get("h", 0) / 2

            if (
                _FEEDING_ZONE["x1"] <= cx <= _FEEDING_ZONE["x2"]
                and _FEEDING_ZONE["y1"] <= cy <= _FEEDING_ZONE["y2"]
            ):
                timeline[hour_key]["feeding_visits"] += 1

            timeline[hour_key]["cx_values"].append(cx)

        result: list[BehaviorTimelineEntry] = []
        for hour_key in sorted(timeline.keys()):
            entry = timeline[hour_key]
            cx_values = entry["cx_values"]

            std_cx = 0.0
            if len(cx_values) >= 2:
                mean_cx = sum(cx_values) / len(cx_values)
                variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
                std_cx = variance ** 0.5

            result.append(
                BehaviorTimelineEntry(
                    hour=entry["hour"],
                    detections=entry["detections"],
                    feeding_visits=entry["feeding_visits"],
                    movement_score=round(std_cx, 4),
                    camera_id=entry["camera_id"],
                )
            )

        return result

    # ─── Anomaliyalar ─────────────────────────────────────────────────────────

    async def get_animal_anomalies(
        self,
        animal_id: int,
        days: int = 7,
    ) -> list[AnomalyEntry]:
        """
        Jonivor anomaliyalarini qaytaradi (so'nggi N kunlik).

        Args:
            animal_id: Jonivor ID
            days:      Necha kun orqaga qarash (1–30)

        Returns:
            AnomalyEntry ro'yxati (eng yangisi birinchi)

        Raises:
            ValueError: Jonivor topilmasa
        """
        animal = await self._db.get(Animal, animal_id)
        if not animal:
            raise ValueError(f"Jonivor #{animal_id} topilmadi")

        anomalies_result: list[AnomalyEntry] = []
        now = datetime.now(timezone.utc)

        for day_offset in range(days):
            day_end = now - timedelta(days=day_offset)

            try:
                analysis = await self.analyze_animal(animal_id, period_hours=24)

                for anomaly_text in analysis.anomalies:
                    anom_type, severity = _classify_anomaly_type(anomaly_text)
                    anomalies_result.append(
                        AnomalyEntry(
                            type=anom_type,
                            severity=severity,
                            description=anomaly_text,
                            detected_at=day_end.isoformat(),
                            value=None,
                            threshold=None,
                        )
                    )

            except Exception as exc:
                logger.warning(
                    "Anomaly check: animal %s, day -%s: %s",
                    animal_id,
                    day_offset,
                    exc,
                )

            # Faqat bugungi tahlil real-time
            if day_offset == 0:
                break

        return anomalies_result

    # ==========================================================================
    # PRIVATE HELPERS — ichki hisoblash metodlari
    # ==========================================================================

    def _extract_feeding_data(
        self,
        detections: list,
        now: datetime,
    ) -> tuple[int, Optional[float]]:
        """
        Detectionlar ro'yxatidan oziqlanish ma'lumotlarini ajratib oladi.

        Args:
            detections: Detection ORM ob'ektlari ro'yxati
            now:        Hozirgi vaqt (UTC)

        Returns:
            (feeding_visits, last_feeding_hours) juftligi
        """
        feeding_visits = 0
        last_feeding_ts: Optional[datetime] = None

        for det in detections:
            bbox = det.bbox or {}
            cx = bbox.get("x", 0) + bbox.get("w", 0) / 2
            cy = bbox.get("y", 0) + bbox.get("h", 0) / 2

            if (
                _FEEDING_ZONE["x1"] <= cx <= _FEEDING_ZONE["x2"]
                and _FEEDING_ZONE["y1"] <= cy <= _FEEDING_ZONE["y2"]
            ):
                feeding_visits += 1
                last_feeding_ts = det.timestamp

        last_feeding_h: Optional[float] = None
        if last_feeding_ts is not None:
            from datetime import timezone as _tz
            ts = last_feeding_ts
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=_tz.utc)
            last_feeding_h = (now - ts).total_seconds() / 3600

        return feeding_visits, last_feeding_h

    @staticmethod
    def _compute_std_cx(detections: list) -> float:
        """
        Detectionlar ro'yxatidan bbox cx standart og'ishini hisoblaydi.

        Args:
            detections: Detection ORM ob'ektlari ro'yxati

        Returns:
            Standart og'ish qiymati (0.0 — ma'lumot yetarli emas)
        """
        cx_values = [
            (d.bbox or {}).get("x", 0) + (d.bbox or {}).get("w", 0) / 2
            for d in detections
            if d.bbox
        ]

        if len(cx_values) < 2:
            return 0.0

        mean_cx = sum(cx_values) / len(cx_values)
        variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
        return variance ** 0.5

    async def _compute_social_ratio(
        self,
        detections: list,
        animal_id: int,
        det_count: int,
    ) -> float:
        """
        Ijtimoiy xulq nisbatini hisoblaydi.

        Bir xil vaqt va kamerada boshqa jonivorlar bilan birgalikda
        aniqlanish nisbatini qaytaradi.

        Args:
            detections: Detection ob'ektlari (birinchi 50 tasi ishlatiladi)
            animal_id:  Tahlil qilinayotgan jonivor ID
            det_count:  Jami detection soni

        Returns:
            0.0 dan 1.0 gacha bo'lgan nisbat
        """
        if det_count == 0:
            return 0.0

        social_count = 0
        sample_size = min(det_count, 50)  # Performance: maksimal 50 ta

        for det in detections[:sample_size]:
            nearby = await self._db.scalar(
                select(func.count(Detection.id)).where(
                    and_(
                        Detection.camera_id == det.camera_id,
                        Detection.timestamp.between(
                            det.timestamp - timedelta(seconds=15),
                            det.timestamp + timedelta(seconds=15),
                        ),
                        Detection.animal_id != animal_id,
                        Detection.animal_id.isnot(None),
                    )
                )
            )
            if nearby and nearby > 0:
                social_count += 1

        return social_count / sample_size

    async def _fetch_adi_7day(
        self,
        animal_id: int,
        now: datetime,
    ) -> list[float]:
        """
        So'nggi 7 kunlik ADI balllarini oladi.

        Args:
            animal_id: Jonivor ID
            now:       Hozirgi vaqt (UTC)

        Returns:
            ADI ballari ro'yxati (eski → yangi, bir o'nlikgacha yaxlitlangan)
        """
        adi_rows = (
            await self._db.execute(
                select(ADILog.adi_score, ADILog.calculated_at)
                .where(
                    and_(
                        ADILog.animal_id == animal_id,
                        ADILog.calculated_at >= now - timedelta(days=7),
                    )
                )
                .order_by(ADILog.calculated_at)
            )
        ).all()

        return [round(float(r.adi_score), 1) for r in adi_rows]

    @staticmethod
    def _build_empty_analysis(
        animal_id: int,
        animal_tag: Optional[str],
        period_start: datetime,
        period_end: datetime,
        activity_score: BehaviorScore,
    ) -> BehaviorAnalysis:
        """
        Detection yo'q bo'lganda nol ko'rsatkichli tahlil qaytaradi.

        Args:
            animal_id:      Jonivor ID
            animal_tag:     Jonivor tagi
            period_start:   Davr boshlanishi
            period_end:     Davr tugashi
            activity_score: Oldindan hisoblangan faollik ko'rsatkichi

        Returns:
            BehaviorAnalysis — barcha komponentlar 0/critical
        """
        zero_score = BehaviorScore(
            value=0.0,
            max_value=1.0,
            percentage=0.0,
            status="critical",
            description="Ma'lumot yo'q",
        )
        return BehaviorAnalysis(
            animal_id=animal_id,
            animal_tag=animal_tag,
            period_start=period_start.isoformat(),
            period_end=period_end.isoformat(),
            detection_count=0,
            activity=activity_score,
            feeding=zero_score,
            movement=zero_score,
            social=zero_score,
            overall_score=0.0,
            overall_status="critical",
            anomalies=["Tahlil davri uchun detection ma'lumoti topilmadi"],
            recommendations=["Kamera va pipeline ishlayotganini tekshiring"],
            adi_trend=None,
            adi_7day=[],
            analyzed_at=period_end.isoformat(),
        )