"""
Taurus Vision — Health Prediction Schemas

Prediction API endpointlari uchun barcha Pydantic v2 sxemalari.

IMPORT ZANJIRI:
    predictions_endpoint.py → (bu modul) → HealthPrediction ORM

DIZAYN QOIDALARI:
    - Response sxemalari ORM dan mustaqil — to'g'ridan-to'g'ri maydon
      nusxalash o'rniga `from_orm_obj` classmethod ishlatiladi.
      Sabab: `lazy="selectin"` muammolarini oldini oladi.
    - Barcha optional maydonlar uchun default None belgilangan.
    - model_config = ConfigDict(from_attributes=True) — ORM mos kelishi uchun.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Any

from pydantic import BaseModel, Field, ConfigDict


# =============================================================================
# BUILDING BLOCKS
# =============================================================================

class EnsembleWeights(BaseModel):
    """Ensemble model og'irlik taqsimoti."""

    rule_based:    float = Field(..., ge=0.0, le=1.0, description="Rule Engine og'irligi")
    random_forest: float = Field(..., ge=0.0, le=1.0, description="RandomForest og'irligi")
    isolation:     float = Field(..., ge=0.0, le=1.0, description="IsolationForest og'irligi")


class FeatureImportance(BaseModel):
    """RandomForest feature ahamiyati."""

    feature:    str   = Field(..., description="Feature nomi")
    importance: float = Field(..., ge=0.0, le=1.0, description="Nisbiy ahamiyat")


# =============================================================================
# CORE RESPONSE SCHEMAS
# =============================================================================

class HealthPredictionResponse(BaseModel):
    """
    Bitta jonivorning to'liq bashorat natijasi.

    GET /predictions/animal/{id} va POST /predictions/animal/{id}/predict
    endpointlari tomonidan qaytariladi.
    """

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),   # model_version field uchun Pydantic warning ni o'chirish
    )

    id:              int     = Field(..., description="Bashorat yozuvi ID")
    animal_id:       int     = Field(..., description="Jonivor ID")
    prediction_date: str     = Field(..., description="Bashorat sanasi YYYY-MM-DD")

    # Asosiy natija
    risk_level:  str   = Field(..., description="low | medium | high | critical")
    risk_score:  float = Field(..., ge=0.0, le=100.0, description="Xavf bali 0–100")
    confidence:  float = Field(..., ge=0.0, le=1.0,   description="Model ishonchi 0–1")

    # Ensemble komponentlari
    rule_risk:        float = Field(..., description="Rule-based xavf 0–100")
    rf_risk:          float = Field(..., description="RandomForest xavf 0–100")
    isolation_score:  float = Field(..., description="IsolationForest anomaly 0–100")

    # Ma'lumot sifati
    adi_days_available: int = Field(..., description="Ishlatilgan ADI kunlari soni")
    features_used:      int = Field(..., description="Feature vektori o'lchami")

    # Trend bashorat
    predicted_adi_7day: Optional[float] = Field(None, description="7 kundan keyin kutilayotgan ADI")
    trend_direction:    Optional[str]   = Field(None, description="improving | stable | declining")

    # Tushuntirish
    risk_factors:    Optional[list[str]] = Field(None, description="Aniqlangan xavf omillari")
    recommendations: Optional[list[str]] = Field(None, description="Tavsiyalar ro'yxati")

    # Meta
    model_version: str                  = Field(..., description="Model versiyasi")
    created_at:    Optional[datetime]   = Field(None, description="Yaratilgan vaqt")

    # Hisoblangan maydonlar
    needs_attention:    bool             = Field(..., description="Darhol e'tibor kerakmi")
    ensemble_breakdown: dict[str, float] = Field(..., description="Ensemble komponent taqsimoti")

    @classmethod
    def from_orm_obj(cls, obj: Any) -> "HealthPredictionResponse":
        """
        HealthPrediction ORM instancedan schema yaratish.

        ORM property larini (needs_attention, ensemble_breakdown) to'g'ri
        seriallaydi — model_validate(obj) da lazy-load muammolari bo'lishi mumkin.

        Args:
            obj: HealthPrediction ORM instance

        Returns:
            HealthPredictionResponse
        """
        return cls(
            id               = obj.id,
            animal_id        = obj.animal_id,
            prediction_date  = obj.prediction_date,
            risk_level       = obj.risk_level,
            risk_score       = round(obj.risk_score, 2),
            confidence       = round(obj.confidence, 3),
            rule_risk        = round(obj.rule_risk, 2),
            rf_risk          = round(obj.rf_risk, 2),
            isolation_score  = round(obj.isolation_score, 2),
            adi_days_available = obj.adi_days_available,
            features_used    = obj.features_used,
            predicted_adi_7day = (
                round(obj.predicted_adi_7day, 1)
                if obj.predicted_adi_7day is not None else None
            ),
            trend_direction  = obj.trend_direction,
            risk_factors     = obj.risk_factors,
            recommendations  = obj.recommendations,
            model_version    = obj.model_version,
            created_at       = getattr(obj, "created_at", None),
            needs_attention  = obj.needs_attention,
            ensemble_breakdown = obj.ensemble_breakdown,
        )


# =============================================================================
# FARM-LEVEL SCHEMAS
# =============================================================================

class AnimalRiskSummary(BaseModel):
    """Xavfli jonivorlar ro'yxatidagi qisqa yozuv."""

    animal_id:       int            = Field(..., description="Jonivor ichki ID")
    tag_id:          str            = Field(..., description="Jonivor teg raqami")
    name:            Optional[str]  = Field(None, description="Jonivor ismi (ixtiyoriy)")
    species:         str            = Field(..., description="Tur: cattle | sheep | ...")

    risk_level:      str            = Field(..., description="low | medium | high | critical")
    risk_score:      float          = Field(..., ge=0.0, le=100.0)
    confidence:      float          = Field(..., ge=0.0, le=1.0)
    trend_direction: Optional[str]  = Field(None, description="improving | stable | declining")
    top_risk_factor: Optional[str]  = Field(None, description="Eng asosiy xavf omili")


class PredictionFarmSummary(BaseModel):
    """
    Ferma darajasidagi kunlik bashorat xulosasi.

    GET /predictions/farm-summary tomonidan qaytariladi.
    """

    date:            str   = Field(..., description="Bashorat sanasi YYYY-MM-DD")
    total_predicted: int   = Field(..., description="Bashorat qilingan jonivorlar soni")
    avg_risk_score:  float = Field(..., ge=0.0, le=100.0, description="O'rtacha xavf bali")
    max_risk_score:  float = Field(..., ge=0.0, le=100.0, description="Maksimal xavf bali")

    low_count:      int = Field(..., ge=0, description="Low risk jonivorlar")
    medium_count:   int = Field(..., ge=0, description="Medium risk jonivorlar")
    high_count:     int = Field(..., ge=0, description="High risk jonivorlar")
    critical_count: int = Field(..., ge=0, description="Critical risk jonivorlar")

    at_risk_animals: list[AnimalRiskSummary] = Field(
        default_factory=list,
        description="Medium+ xavfli jonivorlar (max 20 ta)",
    )


# =============================================================================
# HISTORY SCHEMAS
# =============================================================================

class PredictionHistoryPoint(BaseModel):
    """Bashorat tarixidagi bitta kun nuqtasi."""

    date:           str            = Field(..., description="YYYY-MM-DD")
    risk_score:     float          = Field(..., ge=0.0, le=100.0)
    risk_level:     str            = Field(..., description="low | medium | high | critical")
    adi_projection: Optional[float] = Field(None, description="7 kunlik ADI bashorat")


class PredictionHistory(BaseModel):
    """
    Jonivor bashorat tarixi.

    GET /predictions/animal/{id}/history tomonidan qaytariladi.
    """

    animal_id: int                          = Field(..., description="Jonivor ID")
    days:      int                          = Field(..., ge=7, le=90, description="Tarix davri (kun)")
    history:   list[PredictionHistoryPoint] = Field(
        default_factory=list,
        description="Tarix nuqtalari — eski → yangi tartibda",
    )


# =============================================================================
# FARM-WIDE RUN RESPONSE
# =============================================================================

class FarmPredictionRunResponse(BaseModel):
    """
    POST /predictions/run-farm natijasi.

    predict_all_active() dict ini deseriallashtiradi.
    """

    date:          str   = Field(..., description="Bashorat sanasi")
    total:         int   = Field(..., ge=0, description="Aktiv jonivorlar soni")
    succeeded:     int   = Field(..., ge=0, description="Muvaffaqiyatli bashoratlar")
    failed:        int   = Field(..., ge=0, description="Xato yuz bergan bashoratlar")
    at_risk_count: int   = Field(..., ge=0, description="HIGH yoki CRITICAL jonivorlar")
    duration_sec:  float = Field(..., ge=0.0, description="Ijro vaqti (soniya)")


# =============================================================================
# TRAINING SCHEMAS
# =============================================================================

class TrainModelsRequest(BaseModel):
    """POST /predictions/train so'rov tanasi."""

    days_back: int = Field(
        default=90,
        ge=14,
        le=365,
        description="Training uchun foydalaniladigan tarix (14–365 kun)",
    )


class TrainModelsResponse(BaseModel):
    """POST /predictions/train natijasi."""

    rf_trained:   bool  = Field(..., description="RandomForest muvaffaqiyatli o'rgatildimi")
    iso_trained:  bool  = Field(..., description="IsolationForest muvaffaqiyatli o'rgatildimi")
    n_samples:    int   = Field(..., ge=0, description="Training namunalar soni")
    n_positive:   int   = Field(..., ge=0, description="At-risk namunalar soni")
    rf_accuracy:  float = Field(..., ge=0.0, le=1.0, description="RF cross-val aniqligi")

    top_features: list[FeatureImportance] = Field(
        default_factory=list,
        description="Eng muhim featurelar (max 10)",
    )
    duration_sec: float          = Field(..., ge=0.0, description="O'rgatish vaqti (soniya)")
    trained_at:   Optional[str]  = Field(None, description="O'rgatilgan vaqt ISO string")
    message:      Optional[str]  = Field(None, description="Qo'shimcha ma'lumot")


# =============================================================================
# MODEL STATUS SCHEMA
# =============================================================================

class ModelStatusResponse(BaseModel):
    """
    GET /predictions/model-status natijasi.

    ML model holati va konfiguratsiyasini qaytaradi.
    """

    model_config = ConfigDict(protected_namespaces=())  # model_version uchun

    rf_trained:         bool   = Field(..., description="RF o'rgatilganmi")
    iso_trained:        bool   = Field(..., description="IsolationForest o'rgatilganmi")
    trained_at:         Optional[str]  = Field(None, description="So'nggi training vaqti")
    n_training_samples: int    = Field(..., ge=0, description="Training namunalar soni")
    model_version:      str    = Field(..., description="Model versiya string")

    ensemble_weights: EnsembleWeights = Field(
        ..., description="Ensemble og'irliklari"
    )
    top_features: list[FeatureImportance] = Field(
        default_factory=list,
        description="RF feature importances (max 10)",
    )
    status_message: str = Field(..., description="Foydalanuvchiga tushunarli holat xabari")