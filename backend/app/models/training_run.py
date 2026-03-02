"""
Taurus Vision — Training Run ORM Model (Sprint 15-16)

Har bir YOLO fine-tuning sessiyasining to'liq tarixini saqlaydi.
Bir yozuv = bitta training run (start → complete/failed).

DIZAYN:
    - status enum: training jarayonini kuzatish
    - metrics JSON: mAP50, precision, recall, loss
    - is_deployed: hozir ishlatilayotgan model shu run ekanligini bildiradi
    - base_model_name: qaysi modeldan boshlangan (yolo11n.pt yoki avvalgi custom)
    - dataset_info JSON: qancha rasm, train/val split
"""

import enum
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import BaseModel


class TrainingStatus(str, enum.Enum):
    """Training run holati."""
    PENDING    = "pending"    # Navbatda kutmoqda
    COLLECTING = "collecting" # Framlar yig'ilmoqda
    BUILDING   = "building"   # Dataset yaratilmoqda
    TRAINING   = "training"   # Model o'qitilmoqda
    EVALUATING = "evaluating" # Natijalar tekshirilmoqda
    COMPLETED  = "completed"  # Muvaffaqiyatli yakunlandi
    FAILED     = "failed"     # Xato bilan to'xtadi
    DEPLOYED   = "deployed"   # Ishlatishga olingan


class TrainingRun(BaseModel):
    """
    YOLO fine-tuning run yozuvi.

    Bir training sessiyasining barcha ma'lumotlari:
    dataset, hyperparametrlar, natijalar va deploy holati.
    """

    __tablename__ = "training_runs"

    # =========================================================================
    # IDENTIFICATION
    # =========================================================================

    run_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="",
        comment="Foydalanuvchi uchun qulay nom (masalan: 'Mart-2026-v1')",
    )

    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=TrainingStatus.PENDING,
        index=True,
        comment="pending | collecting | building | training | evaluating | completed | failed | deployed",
    )

    # =========================================================================
    # MODEL KONFIGURATSIYA
    # =========================================================================

    base_model_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="yolo11n.pt",
        comment="Boshlang'ich model fayli nomi",
    )

    epochs: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=50,
        comment="O'qitish epochlari soni",
    )

    batch_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=8,
        comment="Batch o'lchami",
    )

    img_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=640,
        comment="Kirish rasm o'lchami",
    )

    freeze_layers: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
        comment="Muzlatilgan backbone qatlamlari soni",
    )

    # =========================================================================
    # DATASET MA'LUMOTLARI
    # =========================================================================

    dataset_info: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Dataset statistikasi: "
            "{n_total, n_train, n_val, dataset_dir, yaml_path, classes}"
        ),
    )

    # =========================================================================
    # VAQT
    # =========================================================================

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Training boshlanish vaqti",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Training yakunlanish vaqti (muvaffaqiyatli yoki xato)",
    )

    # =========================================================================
    # NATIJALAR
    # =========================================================================

    metrics: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON,
        nullable=True,
        comment=(
            "Training metrikalari: "
            "{map50, map50_95, precision, recall, "
            "box_loss, cls_loss, epochs_done, best_epoch, duration_sec}"
        ),
    )

    error_message: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Xato xabari (status=failed bo'lsa)",
    )

    # =========================================================================
    # MODEL DEPLOY
    # =========================================================================

    model_path: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Saqlangan best.pt fayl yo'li",
    )

    is_deployed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="True = hozir ishlatilayotgan model shu run",
    )

    deployed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deploy qilingan vaqt",
    )

    # =========================================================================
    # IZOHLLAR
    # =========================================================================

    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Foydalanuvchi izohlari",
    )

    # =========================================================================
    # INDEXLAR
    # =========================================================================

    __table_args__ = (
        Index("ix_training_runs_status",      "status"),
        Index("ix_training_runs_is_deployed", "is_deployed"),
        Index("ix_training_runs_created_at",  "created_at"),
    )

    # =========================================================================
    # PROPERTIES
    # =========================================================================

    @property
    def duration_seconds(self) -> Optional[float]:
        """Training davomiyligi soniyalarda."""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

    @property
    def map50(self) -> Optional[float]:
        """mAP50 metriki (deploy qarorlari uchun)."""
        if self.metrics:
            return self.metrics.get("map50")
        return None

    def __repr__(self) -> str:
        return (
            f"<TrainingRun("
            f"id={self.id}, "
            f"name='{self.run_name}', "
            f"status={self.status}, "
            f"is_deployed={self.is_deployed}"
            f")>"
        )