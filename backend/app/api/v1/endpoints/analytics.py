"""
Taurus Vision — Analytics API Endpoints (Sprint 21-24)

MAVJUD ENDPOINT'LAR (Sprint 1-20):
    GET /analytics/overview              — Dashboard ko'rsatkichlari
    GET /analytics/trends/weight         — Vazn o'zgarish grafigi
    GET /analytics/patterns/detection    — Deteksiya naqshlari
    GET /analytics/health/metrics        — Sog'liq ko'rsatkichlari
    GET /analytics/cameras/performance   — Kamera samaradorligi

SPRINT 21-24 YANGI ENDPOINT'LAR:
    GET /analytics/trends/adi            — ADI ball trendi (individual yoki poda)
    GET /analytics/trends/growth         — O'sish egri chizig'i + regressiya
    GET /analytics/trends/behavior       — Xatti-harakat komponentlari trenди
    GET /analytics/compare/animals       — Ko'p jonivorni yonma-yon taqqoslash
    GET /analytics/compare/periods       — Davr-davr taqqoslash
    GET /analytics/herd/statistics       — Poda to'liq statistikasi
    GET /analytics/insights              — Avtomatik tushunchalar

KESH STRATEGIYASI:
    /overview            → 60s  (real-time muhim)
    /trends/*            → 5 daqiqa (tarixiy ma'lumot)
    /patterns/*          → 5 daqiqa
    /health/metrics      → 2 daqiqa
    /herd/statistics     → 3 daqiqa
    /insights            → 10 daqiqa (qoidalar nisbatan barqaror)
    /compare/*           → keshlanmaydi (dinamik parametrlar)
"""

from datetime import date, timedelta, datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.core.logging_config import get_logger
from app.core.cache import cache_get, cache_set, CacheKeys
from app.services.analytics_service import AnalyticsService
from app.schemas.analytics import (
    # Sprint 1-20
    DashboardOverview,
    WeightTrendsResponse,
    WeightTrendPoint,
    DetectionPatternsResponse,
    HealthMetricsResponse,
    CameraPerformanceResponse,
    # Sprint 21-24
    ADITrendsResponse,
    ADITrendPoint,
    ADITrendStats,
    GrowthTrendsResponse,
    GrowthPoint,
    LinearRegressionStats,
    BehaviorTrendsResponse,
    BehaviorTrendPoint,
    AnimalComparisonResponse,
    AnimalMetricSummary,
    PeriodComparisonResponse,
    PeriodMetrics,
    PeriodDelta,
    HerdStatisticsResponse,
    InsightsResponse,
    InsightItem,
    InsightsSummary,
)

logger = get_logger(__name__)

router = APIRouter(
    prefix="/analytics",
    tags=["Analytics"],
    dependencies=[Depends(get_current_active_user)],
)

# ---------------------------------------------------------------------------
# Singleton servis — modul yuklanishida bir marta yaratiladi
# ---------------------------------------------------------------------------
_analytics_service = AnalyticsService()


# =============================================================================
# DASHBOARD OVERVIEW  (Sprint 1-8)
# =============================================================================

@router.get(
    "/overview",
    response_model=DashboardOverview,
    summary="Dashboard uchun asosiy ko'rsatkichlar",
    description=(
        "Barcha asosiy metrikalar bitta so'rovda: jonivorlar, deteksiyalar, "
        "vazn, kamera holati, so'nggi faollik, alertlar.\n\n"
        "**Kesh**: 60 soniya (Redis)."
    ),
)
async def get_dashboard_overview(
    db: AsyncSession = Depends(get_db),
) -> DashboardOverview:
    """Dashboard overview — Redis cache 60s."""
    cached = await cache_get(CacheKeys.OVERVIEW)
    if cached is not None:
        logger.debug("Cache HIT: analytics:overview")
        return DashboardOverview(**cached)

    try:
        overview = await _analytics_service.get_dashboard_overview(db)
        await cache_set(CacheKeys.OVERVIEW, overview, ttl=60)
        return DashboardOverview(**overview)
    except Exception as exc:
        logger.error(f"Dashboard overview error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate dashboard overview")


# =============================================================================
# WEIGHT TRENDS  (Sprint 7-8)
# =============================================================================

@router.get(
    "/trends/weight",
    response_model=WeightTrendsResponse,
    summary="Vazn o'zgarish grafigi",
    description=(
        "Belgilangan davr uchun vazn time-series ma'lumotlari.\n\n"
        "- `animal_id` ko'rsatilsa: o'sha jonivorning individual grafikasi.\n"
        "- Ko'rsatilmasa: butun ferma bo'yicha o'rtacha.\n\n"
        "**Kesh**: 5 daqiqa (farm-wide)."
    ),
)
async def get_weight_trends(
    animal_id: Optional[int] = Query(None, gt=0, description="Jonivor ID (ixtiyoriy)"),
    days:      int            = Query(30, ge=1, le=365, description="Necha kunlik tarix"),
    aggregation: str          = Query("daily", pattern="^(daily|weekly|monthly)$"),
    db: AsyncSession = Depends(get_db),
) -> WeightTrendsResponse:
    """Vazn trenди — Redis 5 daqiqa (farm-wide so'rovlar uchun)."""
    cache_key = CacheKeys.weight_trend(days) if animal_id is None else None
    if cache_key:
        cached = await cache_get(cache_key)
        if cached is not None:
            return WeightTrendsResponse(**cached)

    try:
        if animal_id is not None:
            from app.repositories.animal import AnimalRepository
            if not await AnimalRepository().get_by_id(db, animal_id):
                raise HTTPException(status.HTTP_404_NOT_FOUND, f"Animal {animal_id} not found")

        trends = await _analytics_service.get_weight_trends(db, animal_id=animal_id, days=days, aggregation=aggregation)
        response = WeightTrendsResponse(
            data=[WeightTrendPoint(**p) for p in trends],
            animal_id=animal_id,
            period_days=days,
        )
        if cache_key:
            await cache_set(cache_key, response.model_dump(), ttl=300)
        return response

    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Weight trends error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate weight trends")


# =============================================================================
# DETECTION PATTERNS  (Sprint 7-8)
# =============================================================================

@router.get(
    "/patterns/detection",
    response_model=DetectionPatternsResponse,
    summary="Deteksiya naqshlari tahlili",
    description=(
        "Sana oralig'i uchun soat/kun/kamera bo'yicha deteksiya statistikasi.\n\n"
        "24 soatlik heatmap, kundagi jadval, top-10 jonivorlar."
    ),
)
async def get_detection_patterns(
    date_from: date = Query(..., description="Boshlanish sanasi YYYY-MM-DD"),
    date_to:   date = Query(..., description="Tugash sanasi YYYY-MM-DD"),
    db: AsyncSession = Depends(get_db),
) -> DetectionPatternsResponse:
    if date_to < date_from:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "date_to must be >= date_from")
    if (date_to - date_from).days > 365:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Date range cannot exceed 365 days")

    try:
        patterns = await _analytics_service.get_detection_patterns(db, date_from, date_to)
        return DetectionPatternsResponse(**patterns)
    except Exception as exc:
        logger.error(f"Detection patterns error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to analyze detection patterns")


# =============================================================================
# HEALTH METRICS  (Sprint 11-12)
# =============================================================================

@router.get(
    "/health/metrics",
    response_model=HealthMetricsResponse,
    summary="Sog'liq ko'rsatkichlari",
    description=(
        "Jonivorlar holati taqsimoti, vazn tarqalishi, alertlar va "
        "umumiy xavf balli (0-100).\n\n"
        "**Kesh**: 2 daqiqa."
    ),
)
async def get_health_metrics(db: AsyncSession = Depends(get_db)) -> HealthMetricsResponse:
    cached = await cache_get(CacheKeys.HEALTH_METRICS)
    if cached is not None:
        return HealthMetricsResponse(**cached)

    try:
        metrics = await _analytics_service.get_health_metrics(db)
        await cache_set(CacheKeys.HEALTH_METRICS, metrics, ttl=120)
        return HealthMetricsResponse(**metrics)
    except Exception as exc:
        logger.error(f"Health metrics error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to calculate health metrics")


# =============================================================================
# CAMERA PERFORMANCE  (Sprint 9-10)
# =============================================================================

@router.get(
    "/cameras/performance",
    response_model=CameraPerformanceResponse,
    summary="Kamera ishlash samaradorligi",
    description=(
        "Har bir kamera uchun: uptime, deteksiya soni, o'rtacha confidence, FPS, xatoliklar.\n\n"
        "Real-time pipeline_manager holati bilan boyitiladi."
    ),
)
async def get_camera_performance(
    camera_id: Optional[str] = Query(None, min_length=1, max_length=100),
    days:      int            = Query(7, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
) -> CameraPerformanceResponse:
    try:
        performance = await _analytics_service.get_camera_performance(db, camera_id=camera_id, days=days)
        return CameraPerformanceResponse(**performance)
    except Exception as exc:
        logger.error(f"Camera performance error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to analyze camera performance")


# =============================================================================
# SPRINT 21 — ADI TRENDS
# =============================================================================

@router.get(
    "/trends/adi",
    response_model=ADITrendsResponse,
    summary="ADI ball trenди (Sprint 21)",
    description=(
        "Animal Development Index (ADI) ball o'zgarishi grafigi.\n\n"
        "- `animal_id` ko'rsatilsa: individual jonivorning 8 komponentli ADI tarixи.\n"
        "- Ko'rsatilmasa: poda darajasidagi o'rtacha ADI.\n\n"
        "Trend yo'nalishi (improving/declining/stable) ham qaytariladi.\n\n"
        "**Kesh**: 5 daqiqa."
    ),
    responses={
        200: {"description": "ADI trend muvaffaqiyatli qaytarildi"},
        404: {"description": "Jonivor topilmadi"},
    },
)
async def get_adi_trends(
    animal_id: Optional[int] = Query(None, gt=0, description="Jonivor ID (ixtiyoriy — bo'sh = butun poda)"),
    days:      int            = Query(30, ge=7, le=365, description="Qancha kunlik tarix (7-365)"),
    db: AsyncSession = Depends(get_db),
) -> ADITrendsResponse:
    """ADI trend — individual yoki herd-wide."""
    cache_key = CacheKeys.adi_trend(animal_id, days)
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT: {cache_key}")
        return ADITrendsResponse(**cached)

    try:
        result = await _analytics_service.get_adi_trends(db, animal_id=animal_id, days=days)

        response = ADITrendsResponse(
            animal_id=result["animal_id"],
            animal_tag=result["animal_tag"],
            period_days=result["period_days"],
            data=[ADITrendPoint(**p) for p in result["data"]],
            stats=ADITrendStats(**result["stats"]),
        )
        await cache_set(cache_key, response.model_dump(), ttl=300)
        return response

    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except Exception as exc:
        logger.error(f"ADI trends error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate ADI trends")


# =============================================================================
# SPRINT 21 — GROWTH TRENDS
# =============================================================================

@router.get(
    "/trends/growth",
    response_model=GrowthTrendsResponse,
    summary="O'sish egri chizig'i + regressiya (Sprint 21)",
    description=(
        "Vazn o'zgarishi time-series va chiziqli regressiya tahlili.\n\n"
        "**Regressiya** (faqat >= 3 o'lchov bo'lganda):\n"
        "- `slope_kg_per_day`: kunlik o'rtacha o'sish\n"
        "- `r_squared`: regressiya sifati\n"
        "- `projected_weight_30d`: 30 kunlik prognoz\n\n"
        "**Kesh**: 5 daqiqa."
    ),
)
async def get_growth_trends(
    animal_id: Optional[int] = Query(None, gt=0, description="Jonivor ID (bo'sh = butun poda)"),
    days:      int            = Query(90, ge=14, le=365, description="Tahlil davri kunlarda (14-365)"),
    db: AsyncSession = Depends(get_db),
) -> GrowthTrendsResponse:
    """O'sish egri chizig'i va linear regressiya."""
    cache_key = CacheKeys.growth_trend(animal_id, days)
    cached = await cache_get(cache_key)
    if cached is not None:
        return GrowthTrendsResponse(**cached)

    try:
        result = await _analytics_service.get_growth_trends(db, animal_id=animal_id, days=days)

        regression = LinearRegressionStats(**result["regression"]) if result.get("regression") else None

        response = GrowthTrendsResponse(
            animal_id=result["animal_id"],
            animal_tag=result["animal_tag"],
            period_days=result["period_days"],
            data=[GrowthPoint(**p) for p in result["data"]],
            regression=regression,
            summary=result["summary"],
        )
        await cache_set(cache_key, response.model_dump(), ttl=300)
        return response

    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except Exception as exc:
        logger.error(f"Growth trends error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate growth trends")


# =============================================================================
# SPRINT 21 — BEHAVIOR TRENDS
# =============================================================================

@router.get(
    "/trends/behavior",
    response_model=BehaviorTrendsResponse,
    summary="Xatti-harakat komponentlari trenди (Sprint 21)",
    description=(
        "ADILog dan 8 komponent ball (faollik, oziqlanish, ichish, harakat, "
        "o'sish, ijtimoiylik, sensor, veterinar) kunlik grafigi.\n\n"
        "Har komponent uchun trend yo'nalishi va "
        "eng kuchsiz/kuchli komponentlar aniqlanadi.\n\n"
        "**Kesh**: 5 daqiqa."
    ),
)
async def get_behavior_trends(
    animal_id: Optional[int] = Query(None, gt=0),
    days:      int            = Query(30, ge=7, le=180),
    db: AsyncSession = Depends(get_db),
) -> BehaviorTrendsResponse:
    """Xatti-harakat komponentlari trenди."""
    cache_key = CacheKeys.behavior_trend(animal_id, days)
    cached = await cache_get(cache_key)
    if cached is not None:
        return BehaviorTrendsResponse(**cached)

    try:
        result = await _analytics_service.get_behavior_trends(db, animal_id=animal_id, days=days)
        response = BehaviorTrendsResponse(**result)
        await cache_set(cache_key, response.model_dump(), ttl=300)
        return response

    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    except Exception as exc:
        logger.error(f"Behavior trends error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate behavior trends")


# =============================================================================
# SPRINT 22 — ANIMAL COMPARISON
# =============================================================================

@router.get(
    "/compare/animals",
    response_model=AnimalComparisonResponse,
    summary="Ko'p jonivorni yonma-yon taqqoslash (Sprint 22)",
    description=(
        "Bir nechta jonivorning ADI, vazn, faollik va xavf ko'rsatkichlarini "
        "bir jadvalda taqdim etadi.\n\n"
        "- Maksimal **10 ta** jonivor bir vaqtda.\n"
        "- `animal_ids` vergul bilan ajratilgan ID'lar ro'yxati.\n\n"
        "**Kesh**: yo'q (dinamik parametrlar)."
    ),
    responses={
        400: {"description": "Noto'g'ri parametrlar (bo'sh ro'yxat yoki > 10 ta)"},
        404: {"description": "Bir yoki bir nechta jonivor topilmadi"},
    },
)
async def compare_animals(
    animal_ids: str = Query(
        ...,
        description="Vergul bilan ajratilgan jonivor ID'lari. Masalan: 1,2,3,4",
        example="1,2,5,8",
    ),
    days: int = Query(30, ge=7, le=180, description="Taqqoslash davri"),
    db: AsyncSession = Depends(get_db),
) -> AnimalComparisonResponse:
    """Ko'p jonivorni taqqoslash — keshsiz (parametrlar o'zgaruvchan)."""
    try:
        id_list = [int(x.strip()) for x in animal_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "animal_ids faqat raqamlardan iborat bo'lishi kerak")

    if not id_list:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "animal_ids bo'sh bo'lishi mumkin emas")
    if len(id_list) > 10:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Maksimal 10 ta jonivor taqqoslanadi")

    try:
        result = await _analytics_service.compare_animals(db, animal_ids=id_list, days=days)
        return AnimalComparisonResponse(
            period_days=result["period_days"],
            animals=[AnimalMetricSummary(**a) for a in result["animals"]],
            best_adi_animal=result.get("best_adi_animal"),
            worst_adi_animal=result.get("worst_adi_animal"),
            highest_weight_animal=result.get("highest_weight_animal"),
            most_active_animal=result.get("most_active_animal"),
        )

    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    except Exception as exc:
        logger.error(f"Animal comparison error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to compare animals")


# =============================================================================
# SPRINT 22 — PERIOD COMPARISON
# =============================================================================

@router.get(
    "/compare/periods",
    response_model=PeriodComparisonResponse,
    summary="Davr-davr taqqoslash (Sprint 22)",
    description=(
        "Joriy davr vs oldingi davr taqqoslash.\n\n"
        "`days=30` bo'lganda:\n"
        "- **Joriy**: so'nggi 30 kun\n"
        "- **Oldingi**: 30-60 kun avval\n\n"
        "Asosiy metrikalar bo'yicha delta va umumiy holat bahosi qaytariladi.\n\n"
        "**Kesh**: yo'q (har doim yangi ma'lumot)."
    ),
)
async def compare_periods(
    days: int = Query(30, ge=7, le=90, description="Har bir davr uzunligi (7-90 kun)"),
    db: AsyncSession = Depends(get_db),
) -> PeriodComparisonResponse:
    """Joriy davr vs oldingi davr."""
    try:
        result = await _analytics_service.compare_periods(db, days=days)
        return PeriodComparisonResponse(
            current_period=PeriodMetrics(**result["current_period"]),
            previous_period=PeriodMetrics(**result["previous_period"]),
            deltas=[PeriodDelta(**d) for d in result["deltas"]],
            overall_assessment=result["overall_assessment"],
            key_changes=result["key_changes"],
        )
    except Exception as exc:
        logger.error(f"Period comparison error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to compare periods")


# =============================================================================
# SPRINT 23 — HERD STATISTICS
# =============================================================================

@router.get(
    "/herd/statistics",
    response_model=HerdStatisticsResponse,
    summary="Poda to'liq statistikasi (Sprint 23)",
    description=(
        "Ferma darajasida to'liq statistik panorama:\n\n"
        "- **Taqsimotlar**: tur, ADI kategoriya, vazn, yosh\n"
        "- **KPI'lar**: umumiy sog'liq balli, deteksiya qamrovi, "
        "diqqat kerakli jonivorlar soni, ko'rinmayotganlar\n\n"
        "**Kesh**: 3 daqiqa."
    ),
)
async def get_herd_statistics(
    db: AsyncSession = Depends(get_db),
) -> HerdStatisticsResponse:
    """Poda to'liq statistikasi — Redis 3 daqiqa."""
    cache_key = CacheKeys.HERD_STATISTICS
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug("Cache HIT: analytics:herd_statistics")
        return HerdStatisticsResponse(**cached)

    try:
        result = await _analytics_service.get_herd_statistics(db)
        response = HerdStatisticsResponse(**result)
        await cache_set(cache_key, response.model_dump(), ttl=180)
        return response

    except Exception as exc:
        logger.error(f"Herd statistics error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate herd statistics")


# =============================================================================
# SPRINT 24 — AUTOMATED INSIGHTS
# =============================================================================

@router.get(
    "/insights",
    response_model=InsightsResponse,
    summary="Avtomatik tushunchalar — AI Insights (Sprint 24)",
    description=(
        "Qoidaga asoslangan deterministik tahlil asosida "
        "amaliy tavsiyalar generatsiya qiladi.\n\n"
        "**Tushuncha turlari**:\n"
        "- `health` — ADI pasayish, kritik jonivorlar\n"
        "- `growth` — O'sish dinamikasi\n"
        "- `behavior` — Faollik anomaliyalari\n"
        "- `detection` — Ko'rinmaslik\n"
        "- `alert_pattern` — Takroriy alertlar\n"
        "- `herd_trend` — Poda darajasidagi trendlar\n"
        "- `individual_spotlight` — Alohida e'tibor\n\n"
        "`action_required=true` bo'lgan insights darhol chora talab qiladi.\n\n"
        "**Kesh**: 10 daqiqa."
    ),
    responses={
        200: {"description": "Insights muvaffaqiyatli generatsiya qilindi"},
    },
)
async def get_automated_insights(
    days: int = Query(
        14,
        ge=7,
        le=90,
        description="Tahlil davri (7-90 kun). Ko'proq kun = ko'proq kontekst.",
    ),
    db: AsyncSession = Depends(get_db),
) -> InsightsResponse:
    """Avtomatik tushunchalar — Redis 10 daqiqa."""
    cache_key = CacheKeys.insights(days)
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.debug(f"Cache HIT: {cache_key}")
        return InsightsResponse(**cached)

    try:
        result = await _analytics_service.get_automated_insights(db, days=days)

        response = InsightsResponse(
            generated_at=result["generated_at"],
            insights=[InsightItem(**i) for i in result["insights"]],
            summary=InsightsSummary(**result["summary"]),
            analysis_period_days=result["analysis_period_days"],
            animals_analyzed=result["animals_analyzed"],
        )

        await cache_set(cache_key, response.model_dump(), ttl=600)

        logger.info(
            f"Insights generated and cached",
            extra={"extra_data": {"insights_count": len(result["insights"]), "days": days}},
        )

        return response

    except Exception as exc:
        logger.error(f"Automated insights error: {exc}", exc_info=True)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to generate automated insights")