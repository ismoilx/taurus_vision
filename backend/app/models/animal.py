"""
Animal database model.

This module defines the Animal model which represents individual animals
in the farm monitoring system.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Enum as SQLEnum, Index, CheckConstraint, Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.models.base import BaseModel
from app.models.animal_category import AnimalCategory, SPECIES_CATEGORIES, CATEGORY_LABELS


class AnimalSpecies(str, enum.Enum):
    CATTLE = "cattle"
    SHEEP  = "sheep"
    GOAT   = "goat"
    HORSE  = "horse"
    OTHER  = "other"


class AnimalGender(str, enum.Enum):
    MALE    = "male"
    FEMALE  = "female"
    UNKNOWN = "unknown"


class AnimalStatus(str, enum.Enum):
    ACTIVE      = "active"
    QUARANTINE  = "quarantine"
    SICK        = "sick"
    SOLD        = "sold"
    DECEASED    = "deceased"
    TRANSFERRED = "transferred"


class Animal(BaseModel):
    """
    Animal entity model.

    Represents a single animal in the farm with all its attributes,
    tracking information, and relationships to all monitoring subsystems.

    LAZY LOADING STRATEGY:
        - detections, weight_measurements, health_records, embeddings:
          lazy='noload' — API endpointlarda explicit selectinload() ishlatiladi.
          Bu 1000+ jonivor bo'lganda N+1 query muammosini oldini oladi.
        - adi_logs, alerts, health_predictions:
          lazy='dynamic' — time-series, faqat kerak bo'lganda chaqiriladi.
    """

    __tablename__ = "animals"

    # ------------------------------------------------------------------ #
    # Basic Information                                                    #
    # ------------------------------------------------------------------ #

    tag_id: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique tag identifier (e.g., JNV-001)",
    )

    species: Mapped[AnimalSpecies] = mapped_column(
        SQLEnum(AnimalSpecies, name="animal_species"),
        nullable=False,
        index=True,
    )

    breed: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    gender: Mapped[AnimalGender] = mapped_column(
        SQLEnum(AnimalGender, name="animal_gender"),
        default=AnimalGender.UNKNOWN,
        nullable=False,
    )

    # ------------------------------------------------------------------ #
    # Dates                                                                #
    # ------------------------------------------------------------------ #

    birth_date: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        comment="Date of birth (if known)",
    )

    acquisition_date: Mapped[datetime] = mapped_column(
        nullable=False,
        comment="Date when animal was acquired",
    )

    # ------------------------------------------------------------------ #
    # Status                                                               #
    # ------------------------------------------------------------------ #

    status: Mapped[AnimalStatus] = mapped_column(
        SQLEnum(AnimalStatus, name="animal_status"),
        default=AnimalStatus.ACTIVE,
        nullable=False,
        index=True,
    )

    # ------------------------------------------------------------------ #
    # Detection Tracking                                                   #
    # ------------------------------------------------------------------ #

    first_detected_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    last_detected_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
        index=True,
    )

    total_detections: Mapped[int] = mapped_column(
        default=0,
        nullable=False,
    )

    notes: Mapped[Optional[str]] = mapped_column(
        String(1000),
        nullable=True,
    )

    # ------------------------------------------------------------------ #
    # Category (maqsad bo'yicha tasnif)                                   #
    # ------------------------------------------------------------------ #

    category: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Jonivor kategoriyasi: buzoq, sut_uchun, gosht_uchun, nasl_uchun...",
    )

    profile_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Profil rasmi fayl yo'li (data/images/animals/ ichida)",
    )

    muzzle_image: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Tumshuq (muzzle) rasmi fayl yo'li — identifikatsiya uchun asosiy",
    )

    # ------------------------------------------------------------------ #
    # Multi-Farm                                                           #
    # ------------------------------------------------------------------ #

    farm_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("farms.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Jonivor tegishli bo'lgan ferma ID si",
    )

    # ------------------------------------------------------------------ #
    # Relationships                                                        #
    # ------------------------------------------------------------------ #

    farm: Mapped[Optional["Farm"]] = relationship(  # type: ignore[name-defined]
        "Farm",
        back_populates="animals",
        lazy="noload",
    )

    # noload: API endpointda kerak bo'lganda selectinload() ishlatiladi
    detections: Mapped[list["Detection"]] = relationship(  # type: ignore[name-defined]
        "Detection",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="Detection.timestamp.desc()",
    )

    weight_measurements: Mapped[list["WeightMeasurement"]] = relationship(  # type: ignore[name-defined]
        "WeightMeasurement",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="WeightMeasurement.timestamp.desc()",
    )

    embeddings: Mapped[list["AnimalEmbedding"]] = relationship(  # type: ignore[name-defined]
        "AnimalEmbedding",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="AnimalEmbedding.created_at.desc()",
    )

    health_records: Mapped[list["HealthRecord"]] = relationship(  # type: ignore[name-defined]
        "HealthRecord",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="HealthRecord.recorded_at.desc()",
    )

    # dynamic: katta time-series, lazy load optimal
    adi_logs: Mapped[list["ADILog"]] = relationship(  # type: ignore[name-defined]
        "ADILog",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="ADILog.calculation_date.desc()",
    )

    alerts: Mapped[list["Alert"]] = relationship(  # type: ignore[name-defined]
        "Alert",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="Alert.triggered_at.desc()",
    )

    health_predictions: Mapped[list["HealthPrediction"]] = relationship(  # type: ignore[name-defined]
        "HealthPrediction",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="dynamic",
        order_by="HealthPrediction.prediction_date.desc()",
    )

    photos: Mapped[list["AnimalPhoto"]] = relationship(  # type: ignore[name-defined]
        "AnimalPhoto",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="AnimalPhoto.created_at.desc()",
    )

    milk_productions: Mapped[list["MilkProduction"]] = relationship(  # type: ignore[name-defined]
        "MilkProduction",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="MilkProduction.record_date.desc()",
    )

    medicine_usages: Mapped[list["MedicineUsage"]] = relationship(  # type: ignore[name-defined]
        "MedicineUsage",
        back_populates="animal",
        cascade="all, delete-orphan",
        lazy="noload",
        order_by="MedicineUsage.given_date.desc()",
    )

    # ------------------------------------------------------------------ #
    # Table Constraints                                                    #
    # ------------------------------------------------------------------ #

    __table_args__ = (
        CheckConstraint(
            "birth_date IS NULL OR birth_date <= acquisition_date",
            name="check_birth_before_acquisition",
        ),
        CheckConstraint(
            "total_detections >= 0",
            name="check_detections_non_negative",
        ),
        Index("ix_animals_species_status",       "species", "status"),
        Index("ix_animals_status_last_detected", "status",  "last_detected_at"),
    )

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"<Animal("
            f"id={self.id}, "
            f"tag_id='{self.tag_id}', "
            f"species={self.species.value}, "
            f"status={self.status.value}"
            f")>"
        )

    @property
    def age_days(self) -> Optional[int]:
        """Yoshini kunlarda hisoblash."""
        if not self.birth_date:
            return None
        return (datetime.utcnow() - self.birth_date).days

    @property
    def age_months(self) -> Optional[float]:
        """Yoshini oyda hisoblash (o'sish normasi uchun)."""
        if not self.age_days:
            return None
        return round(self.age_days / 30.44, 1)

    @property
    def is_active(self) -> bool:
        """Jonivor hozir fermada faolmi."""
        return self.status == AnimalStatus.ACTIVE

    def mark_detected(
        self,
        detected_at: Optional[datetime] = None,
    ) -> None:
        """
        Deteksiya vaqtini yangilash.

        Args:
            detected_at: Deteksiya vaqti (default: hozir)
        """
        ts = detected_at or datetime.utcnow()

        if self.first_detected_at is None:
            self.first_detected_at = ts

        self.last_detected_at = ts
        self.total_detections += 1