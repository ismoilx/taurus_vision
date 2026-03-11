"""
Taurus Vision — Analytics Schemas (Sprint 21-24)

Pydantic v2 request/response modellari barcha analytics endpoint'lar uchun.

SPRINT 21-24 QO'SHIMCHALAR:
    - ADI trend schemas        (GET /analytics/trends/adi)
    - Growth trend schemas     (GET /analytics/trends/growth)
    - Behavior trend schemas   (GET /analytics/trends/behavior)
    - Animal comparison        (GET /analytics/compare/animals)
    - Period comparison        (GET /analytics/compare/periods)
    - Herd statistics          (GET /analytics/herd/statistics)
    - Automated insights       (GET /analytics/insights)
"""

from datetime import datetime, date
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator, ConfigDict


# =============================================================================
# DASHBOARD OVERVIEW SCHEMAS (Sprint 1-8, unchanged)
# =============================================================================

class AnimalStatistics(BaseModel):
    """Animal count statistics."""

    total: int = Field(..., description="Total number of animals", ge=0)
    active: int = Field(..., description="Number of active animals", ge=0)
    by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Animal counts per status",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total": 45,
                "active": 42,
                "by_status": {"active": 42, "sold": 2, "deceased": 1},
            }
        }
    )


class DetectionStatistics(BaseModel):
    """Detection count statistics."""

    today: int = Field(..., description="Detections today", ge=0)
    week: int = Field(..., description="Detections in past 7 days", ge=0)
    month: int = Field(..., description="Detections in past 30 days", ge=0)
    total: int = Field(..., description="Total detections all-time", ge=0)


class WeightStatistics(BaseModel):
    """Weight-related statistics."""

    average_kg: Optional[float] = Field(None, description="Farm-wide average weight", ge=0)
    change_percentage_7d: Optional[float] = Field(
        None, description="Weight change % over last 7 days"
    )


class CameraSystemStatus(BaseModel):
    """Camera system status."""

    total: int = Field(..., description="Total cameras", ge=0)
    running: int = Field(..., description="Running cameras", ge=0)
    healthy: int = Field(..., description="Healthy cameras", ge=0)
    status: Literal["healthy", "degraded", "down"] = Field(
        ..., description="Overall camera health"
    )


class SystemStatus(BaseModel):
    cameras: CameraSystemStatus


class RecentDetection(BaseModel):
    """Single recent detection item."""

    animal_tag: str = Field(..., min_length=1, max_length=50)
    camera_id: str = Field(..., min_length=1, max_length=100)
    confidence: float = Field(..., ge=0.0, le=1.0)
    detected_at: str = Field(..., description="ISO 8601 timestamp")


class Alert(BaseModel):
    """System alert for dashboard."""

    type: str
    severity: Literal["info", "warning", "critical"]
    animal_tag: str = Field(..., max_length=50)
    message: str
    days: Optional[int] = Field(None, ge=0)
    loss_percentage: Optional[float] = Field(None, ge=0)
    previous_weight: Optional[float] = Field(None, ge=0)
    current_weight: Optional[float] = Field(None, ge=0)


class DashboardOverview(BaseModel):
    """Complete dashboard overview response."""

    timestamp: str
    animals: AnimalStatistics
    detections: DetectionStatistics
    weight: WeightStatistics
    system: SystemStatus
    recent_activity: List[RecentDetection] = Field(default_factory=list)
    alerts: List[Alert] = Field(default_factory=list)


# =============================================================================
# WEIGHT TRENDS SCHEMAS (Sprint 7-8, unchanged)
# =============================================================================

class WeightTrendPoint(BaseModel):
    """Single time-series weight data point."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    average_weight: float = Field(..., ge=0)
    min_weight: float = Field(..., ge=0)
    max_weight: float = Field(..., ge=0)
    measurement_count: int = Field(..., ge=0)
    animal_count: int = Field(..., ge=0)

    @field_validator("max_weight")
    @classmethod
    def validate_max_gte_min(cls, v: float, info: Any) -> float:
        if "min_weight" in info.data and v < info.data["min_weight"]:
            raise ValueError("max_weight must be >= min_weight")
        return v


class WeightTrendsResponse(BaseModel):
    data: List[WeightTrendPoint]
    animal_id: Optional[int] = None
    period_days: int = Field(..., ge=1)


# =============================================================================
# DETECTION PATTERNS SCHEMAS (Sprint 7-8, unchanged)
# =============================================================================

class DailyDetectionCount(BaseModel):
    date: str
    count: int = Field(..., ge=0)


class CameraDetectionStats(BaseModel):
    camera_id: str
    detections: int = Field(..., ge=0)
    average_confidence: float = Field(..., ge=0.0, le=1.0)


class TopDetectedAnimal(BaseModel):
    tag_id: str
    species: str
    detections: int = Field(..., ge=0)


class DetectionPatternStatistics(BaseModel):
    total_detections: int = Field(..., ge=0)
    detection_rate_per_hour: float = Field(..., ge=0.0)
    peak_hour: Optional[int] = Field(None, ge=0, le=23)


class DateRange(BaseModel):
    from_: str = Field(..., alias="from")
    to: str
    days: int = Field(..., ge=1)

    model_config = ConfigDict(populate_by_name=True)


class DetectionPatternsResponse(BaseModel):
    date_range: DateRange
    detections_by_hour: List[int] = Field(..., min_length=24, max_length=24)
    detections_by_day: List[DailyDetectionCount]
    detections_by_camera: List[CameraDetectionStats]
    top_detected_animals: List[TopDetectedAnimal]
    statistics: DetectionPatternStatistics


# =============================================================================
# HEALTH METRICS SCHEMAS (Sprint 11-12, unchanged)
# =============================================================================

class AlertSummary(BaseModel):
    total: int = Field(..., ge=0)
    critical: int = Field(..., ge=0)
    warning: int = Field(..., ge=0)


class HealthMetricsResponse(BaseModel):
    animals_by_status: Dict[str, int]
    status_distribution: Dict[str, int]  # alias for animals_by_status — backward compat
    weight_distribution: Dict[str, int]
    alerts: List[Alert]
    alert_summary: AlertSummary
    risk_score: int = Field(..., ge=0, le=100)
    timestamp: str


# =============================================================================
# CAMERA PERFORMANCE SCHEMAS (Sprint 9-10, unchanged)
# =============================================================================

class CameraPerformanceData(BaseModel):
    camera_id: str
    status: Literal["running", "stopped", "error"]
    uptime_percentage: float = Field(..., ge=0.0, le=100.0)
    total_detections: int = Field(..., ge=0)
    detections_per_hour: float = Field(..., ge=0.0)
    average_confidence: float = Field(..., ge=0.0, le=1.0)
    fps: float = Field(..., ge=0.0)
    errors: int = Field(..., ge=0)
    total_frames: int = Field(..., ge=0)


class PerformancePeriod(BaseModel):
    days: int = Field(..., ge=1)
    from_: str = Field(..., alias="from")
    to: str

    model_config = ConfigDict(populate_by_name=True)


class PerformanceSummary(BaseModel):
    total_cameras: int = Field(..., ge=0)
    running_cameras: int = Field(..., ge=0)
    total_detections: int = Field(..., ge=0)
    average_fps: float = Field(..., ge=0.0)


class CameraPerformanceResponse(BaseModel):
    period: PerformancePeriod
    cameras: List[CameraPerformanceData]
    summary: PerformanceSummary


# =============================================================================
# SPRINT 21 — ADI TREND SCHEMAS
# =============================================================================

class ADITrendPoint(BaseModel):
    """
    Bitta sana uchun ADI ko'rsatkich ma'lumoti.

    Herd-wide so'rovlarda average/min/max qaytariladi.
    Individual so'rovlarda faqat adi_score va category.
    """

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    adi_score: float = Field(..., ge=0.0, le=100.0, description="ADI score (0-100)")
    category: str = Field(
        ..., description="healthy | average | warning | critical"
    )
    activity_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    feeding_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    drinking_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    movement_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    growth_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    social_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    sensor_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    veterinary_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    data_quality: Optional[float] = Field(None, ge=0.0, le=1.0)
    animal_count: int = Field(
        default=1,
        ge=1,
        description="Animals included (>1 for herd-wide averages)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "date": "2026-03-01",
                "adi_score": 78.5,
                "category": "healthy",
                "activity_score": 82.0,
                "feeding_score": 75.5,
                "animal_count": 1,
            }
        }
    )


class ADITrendStats(BaseModel):
    """Statistik xulosalar trend davri uchun."""

    period_days: int = Field(..., ge=1)
    avg_adi: float = Field(..., ge=0.0, le=100.0, description="O'rtacha ADI balli")
    min_adi: float = Field(..., ge=0.0, le=100.0)
    max_adi: float = Field(..., ge=0.0, le=100.0)
    trend_direction: Literal[
        "improving", "declining", "stable", "insufficient_data"
    ] = Field(
        ..., description="Umumiy trend yo'nalishi (oxirgi 7 kun vs oldingi 7 kun)"
    )
    trend_delta: float = Field(
        ..., description="Oxirgi 7 kun va oldingi 7 kun o'rtasidagi ADI farqi"
    )
    days_healthy: int = Field(..., ge=0, description="healthy kategoriyasidagi kunlar soni")
    days_critical: int = Field(..., ge=0, description="critical kategoriyasidagi kunlar soni")


class ADITrendsResponse(BaseModel):
    """ADI trend tahlili javobi."""

    animal_id: Optional[int] = Field(None, description="Animal ID (None = herd-wide)")
    animal_tag: Optional[str] = Field(None, description="Animal tag (agar individual)")
    data: List[ADITrendPoint]
    stats: ADITrendStats
    period_days: int = Field(..., ge=1)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_id": 5,
                "animal_tag": "JNV-005",
                "period_days": 30,
                "data": [],
                "stats": {
                    "period_days": 30,
                    "avg_adi": 76.2,
                    "min_adi": 61.0,
                    "max_adi": 89.5,
                    "trend_direction": "improving",
                    "trend_delta": 4.3,
                    "days_healthy": 22,
                    "days_critical": 0,
                },
            }
        }
    )


# =============================================================================
# SPRINT 21 — GROWTH TREND SCHEMAS (linear regression)
# =============================================================================

class GrowthPoint(BaseModel):
    """Bitta sana uchun o'sish ma'lumoti."""

    date: str = Field(..., description="Date (YYYY-MM-DD)")
    average_weight_kg: float = Field(..., ge=0.0)
    bbox_area_normalized: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="O'rtacha normalized bbox maydoni (kamera o'lchami surogati)",
    )
    measurement_count: int = Field(..., ge=0)
    animal_count: int = Field(..., ge=0)


class LinearRegressionStats(BaseModel):
    """Chiziqli regressiya natijalari."""

    slope_kg_per_day: float = Field(
        ..., description="Kunlik o'rtacha o'sish kg/kun (manfiy = ozayish)"
    )
    slope_kg_per_week: float = Field(..., description="Haftalik o'sish kg/hafta")
    slope_kg_per_month: float = Field(..., description="Oylik o'sish kg/oy")
    r_squared: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Determinatsiya koeffitsienti (1.0 = mukammal chiziq)",
    )
    projected_weight_30d: Optional[float] = Field(
        None, ge=0.0, description="30 kun keyingi prognoz vazni (kg)"
    )
    data_points_used: int = Field(..., ge=0)


class GrowthTrendsResponse(BaseModel):
    """O'sish trend va regressiya tahlili."""

    animal_id: Optional[int] = None
    animal_tag: Optional[str] = None
    period_days: int = Field(..., ge=1)
    data: List[GrowthPoint]
    regression: Optional[LinearRegressionStats] = Field(
        None,
        description="Faqat >= 3 o'lchov mavjud bo'lsa hisoblanadi",
    )
    summary: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "animal_id": None,
                "period_days": 90,
                "data": [],
                "regression": {
                    "slope_kg_per_day": 0.42,
                    "slope_kg_per_week": 2.94,
                    "slope_kg_per_month": 12.6,
                    "r_squared": 0.87,
                    "projected_weight_30d": 265.3,
                    "data_points_used": 85,
                },
            }
        }
    )


# =============================================================================
# SPRINT 21 — BEHAVIOR TREND SCHEMAS
# =============================================================================

class BehaviorTrendPoint(BaseModel):
    """
    Bitta sana uchun xatti-harakat komponentlari.

    ADILog dan olingan 8 ta komponent ball.
    Kunlik o'rtacha (bir nechta jonivor bo'lsa).
    """

    date: str
    activity_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    feeding_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    drinking_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    movement_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    growth_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    social_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    sensor_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    veterinary_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    composite_behavior: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="activity+feeding+movement og'irlikli o'rtachasi",
    )
    animal_count: int = Field(default=1, ge=1)


class BehaviorComponentSummary(BaseModel):
    """Har bir komponent uchun davr xulosasi."""

    component: str
    average: float = Field(..., ge=0.0, le=100.0)
    trend: Literal["improving", "declining", "stable"]
    delta: float


class BehaviorTrendsResponse(BaseModel):
    """Xatti-harakat komponentlari trend javobi."""

    animal_id: Optional[int] = None
    animal_tag: Optional[str] = None
    period_days: int = Field(..., ge=1)
    data: List[BehaviorTrendPoint]
    component_summaries: List[BehaviorComponentSummary] = Field(default_factory=list)
    weakest_component: Optional[str] = Field(
        None, description="Eng past o'rtachali komponent"
    )
    strongest_component: Optional[str] = Field(
        None, description="Eng yuqori o'rtachali komponent"
    )


# =============================================================================
# SPRINT 22 — ANIMAL COMPARISON SCHEMAS
# =============================================================================

class AnimalMetricSummary(BaseModel):
    """Bitta jonivor uchun taqqoslash metrikalar to'plami."""

    animal_id: int
    tag_id: str
    species: str
    status: str

    # ADI
    average_adi: Optional[float] = Field(None, ge=0.0, le=100.0)
    latest_adi: Optional[float] = Field(None, ge=0.0, le=100.0)
    adi_trend: Optional[Literal["improving", "declining", "stable"]] = None

    # Vazn
    latest_weight_kg: Optional[float] = Field(None, ge=0.0)
    weight_change_kg: Optional[float] = None
    weight_change_pct: Optional[float] = None

    # Deteksiya
    detections_period: int = Field(default=0, ge=0)
    detection_rate_per_day: float = Field(default=0.0, ge=0.0)

    # Xatti-harakat
    avg_activity_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    avg_feeding_score: Optional[float] = Field(None, ge=0.0, le=100.0)

    # Xavf
    risk_level: Literal["low", "moderate", "high", "critical"] = "low"
    active_alerts_count: int = Field(default=0, ge=0)


class AnimalComparisonResponse(BaseModel):
    """
    Bir nechta jonivorni yonma-yon taqqoslash.

    Maksimal 10 ta jonivor qo'llab-quvvatlanadi.
    """

    period_days: int = Field(..., ge=1)
    animals: List[AnimalMetricSummary]
    best_adi_animal: Optional[str] = Field(None, description="Eng yuqori ADI li jonivor tag'i")
    worst_adi_animal: Optional[str] = Field(None, description="Eng past ADI li jonivor tag'i")
    highest_weight_animal: Optional[str] = None
    most_active_animal: Optional[str] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "period_days": 30,
                "animals": [],
                "best_adi_animal": "JNV-012",
                "worst_adi_animal": "JNV-034",
            }
        }
    )


# =============================================================================
# SPRINT 22 — PERIOD COMPARISON SCHEMAS
# =============================================================================

class PeriodMetrics(BaseModel):
    """Bitta davr uchun asosiy ko'rsatkichlar."""

    period_label: str = Field(..., description="Masalan: 'Feb 2026', 'Bu hafta'")
    date_from: str
    date_to: str

    # Deteksiya
    total_detections: int = Field(..., ge=0)
    avg_detections_per_day: float = Field(..., ge=0.0)
    avg_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)

    # ADI
    avg_adi: Optional[float] = Field(None, ge=0.0, le=100.0)
    animals_in_healthy: int = Field(default=0, ge=0)
    animals_in_critical: int = Field(default=0, ge=0)

    # Vazn
    avg_weight_kg: Optional[float] = Field(None, ge=0.0)

    # Alertlar
    total_alerts: int = Field(default=0, ge=0)
    critical_alerts: int = Field(default=0, ge=0)


class PeriodDelta(BaseModel):
    """Ikki davr o'rtasidagi farq (mutlaq va foizda)."""

    metric: str
    current_value: Optional[float]
    previous_value: Optional[float]
    absolute_change: Optional[float]
    percentage_change: Optional[float]
    direction: Literal["up", "down", "unchanged"]
    is_positive_change: bool = Field(
        ..., description="up yaxshimi yoki yomon ekanligini bildiradi"
    )


class PeriodComparisonResponse(BaseModel):
    """Joriy davr vs oldingi davr taqqoslash."""

    current_period: PeriodMetrics
    previous_period: PeriodMetrics
    deltas: List[PeriodDelta]
    overall_assessment: Literal["improved", "declined", "stable"] = Field(
        ..., description="Umumiy holat bahosi"
    )
    key_changes: List[str] = Field(
        default_factory=list,
        description="Eng muhim 3 ta o'zgarish (matn shaklida)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_assessment": "improved",
                "key_changes": [
                    "O'rtacha ADI 5.2 ball oshdi (+7.3%)",
                    "Deteksiya soni 12% ko'paydi",
                    "Critical alertlar 2 tadan 0 taga tushdi",
                ],
            }
        }
    )


# =============================================================================
# SPRINT 23 — HERD STATISTICS SCHEMAS
# =============================================================================

class SpeciesBreakdown(BaseModel):
    species: str
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)
    avg_weight_kg: Optional[float] = Field(None, ge=0.0)
    avg_adi: Optional[float] = Field(None, ge=0.0, le=100.0)


class ADIDistribution(BaseModel):
    """ADI kategoriya bo'yicha taqsimot."""

    healthy: int = Field(..., ge=0, description="75-100 ball")
    average: int = Field(..., ge=0, description="50-74 ball")
    warning: int = Field(..., ge=0, description="25-49 ball")
    critical: int = Field(..., ge=0, description="0-24 ball")
    no_data: int = Field(..., ge=0, description="ADI hisoblanmagan")
    healthy_pct: float = Field(..., ge=0.0, le=100.0)
    critical_pct: float = Field(..., ge=0.0, le=100.0)


class WeightDistributionBucket(BaseModel):
    range_label: str = Field(..., description="Masalan: '200-300kg'")
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)


class AgeDistributionBucket(BaseModel):
    range_label: str
    count: int = Field(..., ge=0)
    percentage: float = Field(..., ge=0.0, le=100.0)


class HerdHealthKPIs(BaseModel):
    """Podaning asosiy sog'liq ko'rsatkichlari."""

    overall_health_score: float = Field(
        ..., ge=0.0, le=100.0, description="Umumiy podaning sog'liq balli (ADI o'rtacha)"
    )
    detection_coverage_pct: float = Field(
        ...,
        ge=0.0,
        le=100.0,
        description="Oxirgi 7 kunda aniqlangan aktiv jonivorlar ulushi",
    )
    avg_daily_detections: float = Field(..., ge=0.0)
    animals_needing_attention: int = Field(
        ..., ge=0, description="warning yoki critical ADI'li jonivorlar"
    )
    animals_missing_7d: int = Field(
        ..., ge=0, description="7 kundan ko'p ko'rinmagan jonivorlar"
    )
    avg_weight_kg: Optional[float] = Field(None, ge=0.0)
    total_weight_gain_kg: Optional[float] = Field(
        None, description="So'nggi 30 kunda jami vazn o'sishi (butun poda)"
    )
    feed_efficiency_index: Optional[float] = Field(
        None,
        ge=0.0,
        description="Ozuqa samaradorligi indeksi (vazn o'sishi / sarf qilingan ozuqa)",
    )


class HerdStatisticsResponse(BaseModel):
    """Podaning to'liq statistik xulosasi."""

    timestamp: str
    total_animals: int = Field(..., ge=0)
    active_animals: int = Field(..., ge=0)
    species_breakdown: List[SpeciesBreakdown]
    adi_distribution: ADIDistribution
    weight_distribution: List[WeightDistributionBucket]
    age_distribution: List[AgeDistributionBucket]
    kpis: HerdHealthKPIs

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_animals": 48,
                "active_animals": 45,
                "kpis": {
                    "overall_health_score": 74.2,
                    "detection_coverage_pct": 93.3,
                    "avg_daily_detections": 156.4,
                    "animals_needing_attention": 5,
                    "animals_missing_7d": 2,
                },
            }
        }
    )


# =============================================================================
# SPRINT 24 — AUTOMATED INSIGHTS SCHEMAS
# =============================================================================

class InsightSeverity(str):
    INFO     = "info"
    WARNING  = "warning"
    CRITICAL = "critical"
    POSITIVE = "positive"


class InsightItem(BaseModel):
    """
    AI-tomonidan yaratilgan matnli tushuncha.

    Aniqlik: deterministik qoidalar asosida (ML modeli emas).
    Kelajakda LLM integratsiyasi uchun mo'ljallangan struktura.
    """

    insight_id: str = Field(..., description="Unique insight identifikatori")
    category: Literal[
        "health", "growth", "behavior", "detection", "feeding",
        "alert_pattern", "herd_trend", "individual_spotlight",
    ]
    severity: Literal["info", "warning", "critical", "positive"]
    title: str = Field(..., max_length=120)
    description: str = Field(..., max_length=500)
    affected_animals: List[str] = Field(
        default_factory=list,
        description="Tegishli jonivor tag'lari (bo'sh = butun poda)",
    )
    metric_value: Optional[float] = Field(None, description="Asosiy metrik qiymati")
    metric_label: Optional[str] = Field(None, description="Metrik nomi")
    action_required: bool = Field(
        default=False, description="Darhol harakat talab qilinsa True"
    )
    generated_at: str = Field(..., description="ISO 8601 generatsiya vaqti")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "insight_id": "ins_health_001",
                "category": "health",
                "severity": "warning",
                "title": "5 ta jonivorning ADI balli pasaymoqda",
                "description": (
                    "Oxirgi 7 kunda JNV-012, JNV-023, JNV-031, JNV-040, JNV-044 "
                    "jonivorilarining ADI balli o'rtacha 8.3 ballga tushdi. "
                    "Veterinar tekshiruvi tavsiya etiladi."
                ),
                "affected_animals": ["JNV-012", "JNV-023", "JNV-031"],
                "metric_value": 8.3,
                "metric_label": "ADI pasayish (ball)",
                "action_required": True,
                "generated_at": "2026-03-04T08:00:00",
            }
        }
    )


class InsightsSummary(BaseModel):
    total: int = Field(..., ge=0)
    critical: int = Field(..., ge=0)
    warning: int = Field(..., ge=0)
    positive: int = Field(..., ge=0)
    info: int = Field(..., ge=0)
    actions_required: int = Field(..., ge=0)


class InsightsResponse(BaseModel):
    """
    Avtomatik yaratilgan tushunchalar to'plami.

    Har so'rovda qoidalar qayta hisoblanadi
    (so'nggi ma'lumotlar asosida).
    """

    generated_at: str
    insights: List[InsightItem]
    summary: InsightsSummary
    analysis_period_days: int = Field(..., ge=1)
    animals_analyzed: int = Field(..., ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "generated_at": "2026-03-04T08:00:00",
                "analysis_period_days": 14,
                "animals_analyzed": 45,
                "summary": {
                    "total": 7,
                    "critical": 1,
                    "warning": 3,
                    "positive": 2,
                    "info": 1,
                    "actions_required": 2,
                },
            }
        }
    )