"""
Taurus Vision — Training Schemas (Sprint 15-16)

API request/response Pydantic v2 modellari.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


# =============================================================================
# REQUEST SCHEMAS
# =============================================================================

class TrainingStartRequest(BaseModel):
    """Training run boshlash uchun so'rov."""

    run_name: str = Field(
        default="",
        max_length=100,
        description="Qulay nom (masalan: 'Mart-2026-v1'). Bo'sh bo'lsa avtomatik yaratiladi.",
        examples=["Mart-2026-v1"],
    )
    epochs: int = Field(
        default=50,
        ge=5,
        le=300,
        description="O'qitish epochlari (5-300). CPU da 50 tavsiya etiladi.",
    )
    batch_size: int = Field(
        default=8,
        ge=2,
        le=32,
        description="Batch o'lchami (2-32). 7.5GB RAM uchun 8 optimal.",
    )
    img_size: int = Field(
        default=640,
        ge=320,
        le=1280,
        description="Kirish rasm o'lchami (320-1280). 640 standart.",
    )
    freeze_layers: int = Field(
        default=10,
        ge=0,
        le=23,
        description="Muzlatilgan backbone qatlamlari (0-23). 10 tavsiya etiladi.",
    )
    auto_deploy: bool = Field(
        default=False,
        description="True — agar mAP50 +2% yaxshilansa avtomatik deploy.",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Ixtiyoriy izoh.",
    )


class TrainingDeployRequest(BaseModel):
    """Model deploy uchun so'rov."""
    force: bool = Field(
        default=False,
        description="True — mAP50 tekshiruvisiz majburan deploy.",
    )


# =============================================================================
# RESPONSE SCHEMAS
# =============================================================================

class TrainingRunResponse(BaseModel):
    """TrainingRun API javobi."""

    id:              int
    run_name:        str
    status:          str
    base_model_name: str
    epochs:          int
    batch_size:      int
    img_size:        int
    freeze_layers:   int
    dataset_info:    Optional[dict[str, Any]]
    started_at:      Optional[datetime]
    completed_at:    Optional[datetime]
    metrics:         Optional[dict[str, Any]]
    error_message:   Optional[str]
    model_path:      Optional[str]
    is_deployed:     bool
    deployed_at:     Optional[datetime]
    notes:           Optional[str]
    created_at:      datetime
    updated_at:      datetime
    duration_seconds: Optional[float] = None

    model_config = ConfigDict(
        from_attributes=True,
        protected_namespaces=(),   # model_path field uchun Pydantic warning ni o'chirish
    )


class TrainingListResponse(BaseModel):
    """Runlar ro'yxati javobi."""
    total:  int
    items:  list[TrainingRunResponse]


class DatasetStatsResponse(BaseModel):
    """Yig'ilgan kadrlar statistikasi."""
    total_frames:     int
    min_required:     int
    is_ready:         bool        # total_frames >= min_required
    cameras:          dict[str, int]
    frames_dir:       str
    collector_stats:  Optional[dict[str, Any]]


class TrainingStartResponse(BaseModel):
    """Training boshlanganda javob."""
    run_id:    int
    run_name:  str
    task_id:   str
    message:   str


class TrainingDeployResponse(BaseModel):
    """Deploy natijasi."""
    model_config = ConfigDict(protected_namespaces=())  # model_path uchun

    run_id:       int
    model_path:   str
    map50:        Optional[float]
    message:      str