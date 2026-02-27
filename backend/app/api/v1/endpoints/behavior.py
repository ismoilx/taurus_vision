"""
Taurus Vision — Behavior Analysis API (Sprint 11-12)

Jonivorlar xatti-harakatini real-time tahlil qilish va natijalarni
REST API orqali olish uchun endpointlar.

ENDPOINTLAR:
    GET  /behavior/{animal_id}                  — Bitta jonivor tahlili
    POST /behavior/{animal_id}/analyze          — Darhol tahlil qilish
    GET  /behavior/herd/summary                 — Butun podadan umumiy ko'rinish
    GET  /behavior/{animal_id}/timeline         — Xatti-harakat vaqt chizig'i
    GET  /behavior/{animal_id}/anomalies        — Aniqlangan anomaliyalar

XATTI-HARAKAT MODELI:
    Faollik:     kun davomida detection soniga qarab (high/medium/low/critical)
    Oziqlanish:  feeding zona tashrif davriyligi
    Harakat:     bbox markazining standart og'ishi
    Ijtimoiy:    boshqa jonivorlar bilan birgalikda aniqlanish nisbati
    ADI trend:   so'nggi 7 kunlik ADI o'zgarishi

AUTENTIFIKATSIYA:
    O'qish: VIEWER+
    Darhol tahlil: MANAGER+
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy import select, func, and_, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/behavior", tags=["Behavior Analysis"])

# ─── Zona koordinatalari (normalized) ────────────────────────────────────────
_FEEDING_ZONE  = {"x1": 0.10, "y1": 0.20, "x2": 0.50, "y2": 0.60}
_RESTING_ZONE  = {"x1": 0.50, "y1": 0.50, "x2": 0.90, "y2": 0.90}
_DRINKING_ZONE = {"x1": 0.55, "y1": 0.10, "x2": 0.95, "y2": 0.45}

# ─── Chegaralar ───────────────────────────────────────────────────────────────
_HIGH_ACTIVITY     = 48     # Kuniga detection
_NORMAL_ACTIVITY   = 24
_LOW_ACTIVITY      = 8
_FEEDING_GAP_H     = 12     # Soat
_MOVEMENT_ACTIVE   = 0.15   # bbox std
_MOVEMENT_INACTIVE = 0.05


# =============================================================================
# SCHEMAS
# =============================================================================

class BehaviorScore(PydanticModel):
    """Bitta xatti-harakat o'lchovi uchun ball va talqin."""
    value:       float
    max_value:   float
    percentage:  float
    status:      str   # excellent / good / fair / poor / critical
    description: str


class BehaviorAnalysis(PydanticModel):
    """Jonivor xatti-harakat tahlili natijasi."""
    animal_id:       int
    animal_tag:      Optional[str]
    period_start:    str
    period_end:      str
    detection_count: int

    # Komponentlar
    activity:   BehaviorScore
    feeding:    BehaviorScore
    movement:   BehaviorScore
    social:     BehaviorScore

    # Umumiy ball
    overall_score:  float         # 0–100
    overall_status: str           # excellent/good/fair/poor/critical

    # Anomaliyalar
    anomalies:      list[str]
    recommendations: list[str]

    # ADI trend
    adi_trend:      Optional[str]  # improving / stable / declining
    adi_7day:       list[float]    # So'nggi 7 kun ADI

    analyzed_at: str


class HerdBehaviorSummary(PydanticModel):
    """Butun podaning umumiy xatti-harakat holati."""
    total_animals:    int
    analyzed_count:   int
    period:           str

    # Taqsimot
    excellent_count:  int
    good_count:       int
    fair_count:       int
    poor_count:       int
    critical_count:   int
    no_data_count:    int

    # O'rtacha ko'rsatkichlar
    avg_activity:     float
    avg_feeding:      float
    avg_movement:     float
    avg_social:       float
    avg_overall:      float

    # Diqqat talab qiladiganlar
    attention_needed: list[dict]   # {animal_id, tag, issue, score}

    generated_at: str


class BehaviorTimelineEntry(PydanticModel):
    """Bitta soatlik xatti-harakat ma'lumoti."""
    hour:        str   # "2026-02-15T14:00:00"
    detections:  int
    feeding_visits: int
    movement_score: float
    camera_id:   Optional[str]


class AnomalyEntry(PydanticModel):
    """Bitta aniqlangan anomaliya."""
    type:       str   # feeding_gap / inactivity / low_movement / social_isolation
    severity:   str   # warning / critical
    description: str
    detected_at: str
    value:       Optional[float]
    threshold:   Optional[float]


# =============================================================================
# HELPERS
# =============================================================================

def _score_to_status(pct: float) -> str:
    if pct >= 90: return "excellent"
    if pct >= 75: return "good"
    if pct >= 55: return "fair"
    if pct >= 35: return "poor"
    return "critical"


def _compute_feeding_score(
    feeding_visits: int,
    period_hours: int,
    last_feeding_h: Optional[float],
) -> BehaviorScore:
    """
    Oziqlanish ko'rsatkichini hisoblaydi.

    Mezon: {period_hours / 6} marta normal (har 6 soatda bir marta).
    """
    expected = max(1, period_hours // 6)
    raw_pct  = min(100.0, feeding_visits / expected * 100)

    # So'nggi oziqlanish juda uzoq vaqt oldin bo'lsa — jazo
    if last_feeding_h is not None and last_feeding_h > _FEEDING_GAP_H:
        penalty = min(40.0, (last_feeding_h - _FEEDING_GAP_H) * 3)
        raw_pct  = max(0.0, raw_pct - penalty)

    status = _score_to_status(raw_pct)

    if raw_pct >= 75:
        desc = f"Muntazam oziqlanmoqda ({feeding_visits} ta tashrif)"
    elif raw_pct >= 40:
        desc = f"Oziqlanish kam ({feeding_visits} ta tashrif, kutilgan: {expected})"
    else:
        desc = f"Oziqlanish juda kam yoki to'xtagan"

    if last_feeding_h:
        desc += f". Oxirgi: {last_feeding_h:.1f} soat oldin"

    return BehaviorScore(
        value=round(feeding_visits, 0),
        max_value=float(expected),
        percentage=round(raw_pct, 1),
        status=status,
        description=desc,
    )


def _compute_movement_score(std_cx: float) -> BehaviorScore:
    """
    Harakat intensivligini hisoblaydi.

    bbox markazi (cx) standart og'ishi asosida:
    0.15+ = juda faol, 0.05- = harakatsiz (yotib qolgan)
    """
    if std_cx >= _MOVEMENT_ACTIVE:
        pct  = 90.0
        desc = f"Faol harakat (std={std_cx:.3f})"
    elif std_cx >= 0.08:
        pct  = 65.0
        desc = f"O'rtacha harakat (std={std_cx:.3f})"
    elif std_cx >= _MOVEMENT_INACTIVE:
        pct  = 40.0
        desc = f"Kam harakat (std={std_cx:.3f})"
    elif std_cx > 0:
        pct  = 20.0
        desc = f"Deyarli harakatsiz (std={std_cx:.3f})"
    else:
        pct  = 0.0
        desc = "Harakat ma'lumoti yo'q"

    return BehaviorScore(
        value=round(std_cx, 4),
        max_value=_MOVEMENT_ACTIVE,
        percentage=round(pct, 1),
        status=_score_to_status(pct),
        description=desc,
    )


def _compute_activity_score(det_count: int, period_hours: int) -> BehaviorScore:
    """
    Faollik darajasini hisoblaydi.

    Mezon: {period_hours / 24 * HIGH_ACTIVITY} detection = 100%.
    """
    expected = max(1, int(_HIGH_ACTIVITY * period_hours / 24))
    raw_pct  = min(100.0, det_count / expected * 100)
    status   = _score_to_status(raw_pct)

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


def _compute_social_score(social_ratio: float) -> BehaviorScore:
    """
    Ijtimoiy xulq ko'rsatkichini hisoblaydi.

    social_ratio = boshqalar bilan birga aniqlanish / jami detection
    0.3+ = ijtimoiy, < 0.05 = izolyatsiya
    """
    pct = min(100.0, social_ratio * 200)  # 0.5 nisbat = 100%

    if social_ratio >= 0.3:
        desc = f"Ijtimoiy jonivor ({social_ratio:.0%} vaqt birgalikda)"
        pct  = 90.0
    elif social_ratio >= 0.1:
        desc = f"O'rtacha ijtimoiy ({social_ratio:.0%} vaqt birgalikda)"
        pct  = 65.0
    elif social_ratio > 0:
        desc = f"Kam ijtimoiy ({social_ratio:.0%} vaqt birgalikda)"
        pct  = 35.0
    else:
        desc = "Boshqa jonivorlar bilan birgalikda aniqlanmadi"
        pct  = 15.0

    return BehaviorScore(
        value=round(social_ratio, 3),
        max_value=1.0,
        percentage=round(pct, 1),
        status=_score_to_status(pct),
        description=desc,
    )


def _overall_score(
    activity: BehaviorScore,
    feeding: BehaviorScore,
    movement: BehaviorScore,
    social: BehaviorScore,
) -> float:
    """
    Umumiy xatti-harakat bali (vazn bo'yicha).

    Og'irliklar:
        Faollik:   35%
        Oziqlanish: 35%
        Harakat:   20%
        Ijtimoiy:  10%
    """
    return round(
        activity.percentage  * 0.35
        + feeding.percentage * 0.35
        + movement.percentage * 0.20
        + social.percentage  * 0.10,
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
    """Anomaliya va tavsiyalar ro'yxatini tuzadi."""
    anomalies: list[str] = []
    recs: list[str] = []

    if detection_count == 0:
        anomalies.append("24 soat davomida hech qanday detection yo'q")
        recs.append("Kamera ishlayotganini va jonivor ferma ichida ekanligini tekshiring")

    if feeding.percentage < 30:
        anomalies.append(f"Oziqlanish juda kam: {feeding.value:.0f} ta tashrif")
        recs.append("Jonivorni yem-xashak bilan ta'minlashni tekshiring")

    if last_feeding_h and last_feeding_h > _FEEDING_GAP_H:
        anomalies.append(
            f"So'nggi oziqlanishdan {last_feeding_h:.1f} soat o'tdi "
            f"(chegarasi: {_FEEDING_GAP_H} soat)"
        )
        recs.append("Veterinar ko'rigini rejalashtiring — ishtaha yo'qolishi xavf belgisi")

    if movement.percentage < 25 and detection_count > 0:
        anomalies.append(f"Juda kam harakat aniqlandi (std={movement.value:.3f})")
        recs.append("Jonivor yotib qolgan bo'lishi mumkin — ko'zdan kechiring")

    if activity.percentage < 20 and detection_count > 0:
        anomalies.append(f"Juda past faollik: {activity.value:.0f} ta detection")
        recs.append("Sog'liq tekshiruvi o'tkazing")

    if social.percentage < 20 and detection_count > 5:
        anomalies.append("Izolyatsiya belgilari — boshqa jonivorlardan ajralgan")
        recs.append("Podadan ajralish — kasallik yoki stressning belgisi bo'lishi mumkin")

    return anomalies, recs


# =============================================================================
# CORE ANALYSIS FUNCTION
# =============================================================================

async def _analyze_animal_behavior(
    db: AsyncSession,
    animal_id: int,
    period_hours: int = 24,
) -> BehaviorAnalysis:
    """
    Jonivor xatti-harakatini ma'lumotlar bazasidan tahlil qiladi.

    Args:
        db:           Asinxron DB session
        animal_id:    Jonivor ID
        period_hours: Tahlil davri (soat, default: 24)

    Returns:
        BehaviorAnalysis — to'liq tahlil natijasi

    Raises:
        HTTPException 404: Jonivor topilmasa
        HTTPException 400: Ma'lumot yetarli emas
    """
    from app.models.animal import Animal
    from app.models.detection import Detection
    from app.models.adi_log import ADILog

    now          = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=period_hours)

    # 1. Jonivor mavjudligini tekshirish
    animal = await db.get(Animal, animal_id)
    if not animal:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor #{animal_id} topilmadi",
        )

    # 2. Davr ichidagi detectionlar
    detections = (
        await db.execute(
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

    # 3. Faollik
    activity_score = _compute_activity_score(det_count, period_hours)

    if det_count == 0:
        # Ma'lumot yo'q — barcha score larni 0 ga o'rnatamiz
        feeding_score  = BehaviorScore(value=0, max_value=4, percentage=0,
                                       status="critical", description="Ma'lumot yo'q")
        movement_score = BehaviorScore(value=0, max_value=_MOVEMENT_ACTIVE,
                                       percentage=0, status="critical",
                                       description="Ma'lumot yo'q")
        social_score   = BehaviorScore(value=0, max_value=1, percentage=0,
                                       status="critical", description="Ma'lumot yo'q")
        anomalies = ["Tahlil davri uchun detection ma'lumoti topilmadi"]
        recs      = ["Kamera va pipeline ishlayotganini tekshiring"]
        overall   = 0.0
        adi_7day: list[float] = []
        adi_trend = None

    else:
        # 4. Oziqlanish zonasi tashrif
        feeding_visits  = 0
        last_feeding_ts: Optional[datetime] = None

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

        last_feeding_h: Optional[float] = None
        if last_feeding_ts:
            last_feeding_h = (now - last_feeding_ts).total_seconds() / 3600

        feeding_score = _compute_feeding_score(
            feeding_visits, period_hours, last_feeding_h
        )

        # 5. Harakat (bbox cx standart og'ishi)
        cx_values = [
            (d.bbox or {}).get("x", 0) + (d.bbox or {}).get("w", 0) / 2
            for d in detections if d.bbox
        ]
        std_cx = 0.0
        if len(cx_values) >= 2:
            mean_cx  = sum(cx_values) / len(cx_values)
            variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
            std_cx   = variance ** 0.5

        movement_score = _compute_movement_score(std_cx)

        # 6. Ijtimoiy xulq (bir vaqtda bir kamerada boshqa jonivorlar)
        social_count = 0
        if det_count > 0:
            for det in detections[:50]:  # Birinchi 50 ta — performance uchun
                nearby = await db.scalar(
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

        social_ratio  = social_count / min(det_count, 50) if det_count > 0 else 0.0
        social_score  = _compute_social_score(social_ratio)

        # 7. Anomaliya va tavsiyalar
        anomalies, recs = _build_anomalies_and_recommendations(
            activity_score, feeding_score, movement_score, social_score,
            last_feeding_h, det_count,
        )

        # 8. Umumiy ball
        overall = _overall_score(activity_score, feeding_score,
                                  movement_score, social_score)

        # 9. ADI 7 kunlik trend
        adi_rows = (
            await db.execute(
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

        adi_7day = [round(float(r.adi_score), 1) for r in adi_rows]

        if len(adi_7day) >= 2:
            diff = adi_7day[-1] - adi_7day[0]
            if diff >= 5:
                adi_trend = "improving"
            elif diff <= -5:
                adi_trend = "declining"
            else:
                adi_trend = "stable"
        else:
            adi_trend = None

    return BehaviorAnalysis(
        animal_id        = animal_id,
        animal_tag       = animal.tag_id,
        period_start     = period_start.isoformat(),
        period_end       = now.isoformat(),
        detection_count  = det_count,
        activity         = activity_score,
        feeding          = feeding_score,
        movement         = movement_score,
        social           = social_score,
        overall_score    = overall if det_count > 0 else 0.0,
        overall_status   = _score_to_status(overall) if det_count > 0 else "critical",
        anomalies        = anomalies,
        recommendations  = recs,
        adi_trend        = adi_trend,
        adi_7day         = adi_7day,
        analyzed_at      = now.isoformat(),
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get(
    "/{animal_id}",
    response_model=BehaviorAnalysis,
    summary="Jonivor xatti-harakat tahlili",
    description=(
        "So'nggi N soat uchun jonivor xatti-harakatini tahlil qiladi. "
        "Faollik, oziqlanish, harakat va ijtimoiy xulq ko'rsatkichlarini hisoblaydi. "
        "Ma'lumotlar asnxron qayta hisoblanadi — cache ishlatilmaydi."
    ),
)
async def get_animal_behavior(
    animal_id:    int,
    hours:        int = Query(
        default=24, ge=1, le=168,
        description="Tahlil davri (soat). Min: 1, Max: 168 (7 kun)"
    ),
    current_user: CurrentUser   = ...,
    db:           AsyncSession  = Depends(get_db),
) -> BehaviorAnalysis:
    """
    Jonivor xatti-harakat tahlilini qaytaradi.

    Args:
        animal_id: Tahlil qilinadigan jonivor ID
        hours:     Tahlil davri (1–168 soat)

    Returns:
        BehaviorAnalysis — to'liq tahlil natijasi

    Raises:
        404: Jonivor topilmasa
    """
    return await _analyze_animal_behavior(db, animal_id, period_hours=hours)


@router.post(
    "/{animal_id}/analyze",
    response_model=BehaviorAnalysis,
    status_code=http_status.HTTP_200_OK,
    summary="Darhol xatti-harakat tahlilini ishga tushirish",
    description=(
        "Jonivor uchun xatti-harakat tahlilini sinxron bajaradi va natijani qaytaradi. "
        "Celery task ni kutmasdan real-time natija kerak bo'lganda ishlatiladi. "
        "MANAGER va undan yuqori rol talab etiladi."
    ),
)
async def trigger_behavior_analysis(
    animal_id:    int,
    hours:        int = Query(
        default=24, ge=1, le=168,
        description="Tahlil davri (soat)"
    ),
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> BehaviorAnalysis:
    """
    Darhol xatti-harakat tahlili.

    GET /{animal_id} bilan bir xil natija qaytaradi,
    lekin MANAGER roli talab etiladi va log qilinadi.
    """
    logger.info(
        "Manual behavior analysis triggered",
        extra={"extra_data": {
            "animal_id":    animal_id,
            "hours":        hours,
            "requested_by": current_user.username,
        }},
    )
    return await _analyze_animal_behavior(db, animal_id, period_hours=hours)


@router.get(
    "/herd/summary",
    response_model=HerdBehaviorSummary,
    summary="Butun podaning xatti-harakat xulosasi",
    description=(
        "Barcha aktiv jonivorlar uchun xatti-harakat tahlili o'tkazadi va "
        "umumiy xulosa yaratadi. Diqqat talab qiladigan jonivorlarni ro'yxatga oladi."
    ),
)
async def get_herd_behavior_summary(
    hours:        int = Query(
        default=24, ge=1, le=72,
        description="Tahlil davri (soat). Katta qiymatlar sekinroq ishlaydi."
    ),
    limit:        int = Query(
        default=10, ge=1, le=50,
        description="Diqqat talab qiladiganlar maksimal soni"
    ),
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> HerdBehaviorSummary:
    """
    Butun podaning xatti-harakat xulosasi.

    Barcha ACTIVE jonivorlarni tahlil qiladi va:
    - Holat taqsimotini hisoblaydi
    - O'rtacha ko'rsatkichlarni beradi
    - Eng muammolilarni aniqlaydi

    Performance: Har jonivor uchun DB query — katta podalarda sekin.
    Katta podalar uchun limit parametridan foydalaning.
    """
    from app.models.animal import Animal, AnimalStatus

    now = datetime.now(timezone.utc)

    # Aktiv jonivorlar
    animals = (
        await db.execute(
            select(Animal)
            .where(Animal.status == AnimalStatus.ACTIVE)
            .order_by(Animal.id)
            .limit(100)  # Max 100 jonivor — performance uchun
        )
    ).scalars().all()

    total = len(animals)

    counts = {
        "excellent": 0, "good": 0, "fair": 0,
        "poor": 0, "critical": 0, "no_data": 0,
    }
    activity_vals:  list[float] = []
    feeding_vals:   list[float] = []
    movement_vals:  list[float] = []
    social_vals:    list[float] = []
    overall_vals:   list[float] = []
    attention_list: list[dict]  = []

    for animal in animals:
        try:
            analysis = await _analyze_animal_behavior(db, animal.id, period_hours=hours)

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

            # Diqqat talab qiladiganlar (poor/critical yoki anomaliyalar bor)
            if (analysis.overall_score < 50 or len(analysis.anomalies) > 0) \
                    and len(attention_list) < limit:
                attention_list.append({
                    "animal_id":     animal.id,
                    "animal_tag":    animal.tag_id,
                    "overall_score": analysis.overall_score,
                    "status":        analysis.overall_status,
                    "anomalies":     analysis.anomalies[:2],  # Max 2 ta
                    "adi_trend":     analysis.adi_trend,
                })

        except Exception as exc:
            logger.warning(
                f"Herd summary: animal {animal.id} tahlil xatosi: {exc}"
            )
            counts["no_data"] += 1

    def _avg(vals: list[float]) -> float:
        return round(sum(vals) / len(vals), 1) if vals else 0.0

    # Diqqat talab qiladiganlarni overall_score bo'yicha saralash
    attention_list.sort(key=lambda x: x["overall_score"])

    return HerdBehaviorSummary(
        total_animals   = total,
        analyzed_count  = total - counts["no_data"],
        period          = f"So'nggi {hours} soat",
        excellent_count = counts["excellent"],
        good_count      = counts["good"],
        fair_count      = counts["fair"],
        poor_count      = counts["poor"],
        critical_count  = counts["critical"],
        no_data_count   = counts["no_data"],
        avg_activity    = _avg(activity_vals),
        avg_feeding     = _avg(feeding_vals),
        avg_movement    = _avg(movement_vals),
        avg_social      = _avg(social_vals),
        avg_overall     = _avg(overall_vals),
        attention_needed= attention_list,
        generated_at    = now.isoformat(),
    )


@router.get(
    "/{animal_id}/timeline",
    response_model=list[BehaviorTimelineEntry],
    summary="Jonivor xatti-harakat vaqt chizig'i",
    description=(
        "So'nggi N soatlik xatti-harakat ma'lumotini soatlik "
        "kesimda qaytaradi. Grafik va trend ko'rsatish uchun mo'ljallangan."
    ),
)
async def get_behavior_timeline(
    animal_id:    int,
    hours:        int = Query(
        default=24, ge=6, le=168,
        description="Tahlil davri (soat)"
    ),
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> list[BehaviorTimelineEntry]:
    """
    Soatlik detection va xatti-harakat ma'lumotlari.

    Frontend uchun chart data:
        X: Vaqt (soat)
        Y: Detection soni, Oziqlanish tashrifi, Harakat
    """
    from app.models.animal import Animal
    from app.models.detection import Detection

    animal = await db.get(Animal, animal_id)
    if not animal:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor #{animal_id} topilmadi",
        )

    now          = datetime.now(timezone.utc)
    period_start = now - timedelta(hours=hours)

    detections = (
        await db.execute(
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
                "hour":           hour_key,
                "detections":     0,
                "feeding_visits": 0,
                "cx_values":      [],
                "camera_id":      det.camera_id,
            }

        timeline[hour_key]["detections"] += 1

        # Feeding zone tekshiruvi
        bbox = det.bbox or {}
        cx   = bbox.get("x", 0) + bbox.get("w", 0) / 2
        cy   = bbox.get("y", 0) + bbox.get("h", 0) / 2

        if (
            _FEEDING_ZONE["x1"] <= cx <= _FEEDING_ZONE["x2"]
            and _FEEDING_ZONE["y1"] <= cy <= _FEEDING_ZONE["y2"]
        ):
            timeline[hour_key]["feeding_visits"] += 1

        timeline[hour_key]["cx_values"].append(cx)

    # Harakat score hisoblash
    result = []
    for hour_key in sorted(timeline.keys()):
        entry     = timeline[hour_key]
        cx_values = entry["cx_values"]
        std_cx    = 0.0

        if len(cx_values) >= 2:
            mean_cx  = sum(cx_values) / len(cx_values)
            variance = sum((x - mean_cx) ** 2 for x in cx_values) / len(cx_values)
            std_cx   = variance ** 0.5

        result.append(BehaviorTimelineEntry(
            hour           = entry["hour"],
            detections     = entry["detections"],
            feeding_visits = entry["feeding_visits"],
            movement_score = round(std_cx, 4),
            camera_id      = entry["camera_id"],
        ))

    return result


@router.get(
    "/{animal_id}/anomalies",
    response_model=list[AnomalyEntry],
    summary="Jonivor anomaliyalari",
    description=(
        "So'nggi N kunlik xatti-harakat anomaliyalarini qaytaradi. "
        "Har kuni bir necha anomaliya aniqlanishi mumkin."
    ),
)
async def get_animal_anomalies(
    animal_id:    int,
    days:         int = Query(
        default=7, ge=1, le=30,
        description="Necha kun orqaga qarash"
    ),
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> list[AnomalyEntry]:
    """
    Jonivor anomaliyalari ro'yxati.

    Har kun uchun xatti-harakat tahlili o'tkazadi va anomaliyalarni
    xronologik tartibda qaytaradi.

    Args:
        animal_id: Jonivor ID
        days:      Necha kun orqaga qarash (1–30)

    Returns:
        Anomaliya ro'yxati, eng yangisi birinchi
    """
    from app.models.animal import Animal

    animal = await db.get(Animal, animal_id)
    if not animal:
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=f"Jonivor #{animal_id} topilmadi",
        )

    anomalies_result: list[AnomalyEntry] = []
    now = datetime.now(timezone.utc)

    for day_offset in range(days):
        day_end   = now - timedelta(days=day_offset)
        day_start = day_end - timedelta(hours=24)

        try:
            analysis = await _analyze_animal_behavior(
                db, animal_id, period_hours=24
            )

            for anomaly_text in analysis.anomalies:
                # Anomaliya turini aniqlash
                if "oziqlanmagan" in anomaly_text.lower() or "oziqlanish" in anomaly_text.lower():
                    anom_type = "feeding_gap"
                    severity  = "critical" if "to'xtagan" in anomaly_text.lower() else "warning"
                elif "detection yo'q" in anomaly_text.lower() or "aktivlik" in anomaly_text.lower():
                    anom_type = "inactivity"
                    severity  = "critical"
                elif "harakat" in anomaly_text.lower():
                    anom_type = "low_movement"
                    severity  = "warning"
                elif "izolyatsiya" in anomaly_text.lower():
                    anom_type = "social_isolation"
                    severity  = "warning"
                else:
                    anom_type = "other"
                    severity  = "warning"

                anomalies_result.append(AnomalyEntry(
                    type        = anom_type,
                    severity    = severity,
                    description = anomaly_text,
                    detected_at = day_end.isoformat(),
                    value       = None,
                    threshold   = None,
                ))

        except Exception as exc:
            logger.warning(
                f"Anomaly check: animal {animal_id}, day -{day_offset}: {exc}"
            )

        # Birinchi kunda to'liq, keyingilari summary
        if day_offset == 0:
            break  # Faqat bugungi tahlil — real-time

    return anomalies_result