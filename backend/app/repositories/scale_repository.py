"""
Taurus Vision — Scale Repository

JAVOBGARLIK: Faqat ma'lumotlar bazasi operatsiyalari.
"""

from __future__ import annotations

import secrets
from typing import Optional, Sequence
from datetime import datetime, timezone

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import DatabaseError
from app.core.logging_config import get_logger
from app.models.scale import Scale, ScaleStatus
from app.models.weight_measurement import WeightMeasurement, WeightSource
from app.schemas.scale import ScaleCreate, ScaleUpdate

logger = get_logger(__name__)


class ScaleRepository:
    """DB operatsiyalari uchun Scale Repository."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # =========================================================================
    # CREATE
    # =========================================================================

    async def create(self, data: ScaleCreate) -> Scale:
        """Yangi tarozi yaratish."""
        try:
            payload = data.model_dump()
            # API tarozi uchun token avtomatik yaratamiz
            if payload.get("scale_type") == "api":
                payload["api_token"] = secrets.token_urlsafe(32)
            scale = Scale(**payload)
            self.db.add(scale)
            await self.db.commit()
            await self.db.refresh(scale)
            logger.info(f"Scale created: id={scale.id}, name='{scale.name}'")
            return scale
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Tarozi yaratishda xato.", details={"error": str(exc)})

    # =========================================================================
    # READ
    # =========================================================================

    async def get_by_id(self, scale_id: int) -> Optional[Scale]:
        try:
            result = await self.db.execute(select(Scale).where(Scale.id == scale_id))
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(message="Tarozi olishda xato.", details={"error": str(exc)})

    async def get_by_api_token(self, token: str) -> Optional[Scale]:
        try:
            result = await self.db.execute(
                select(Scale).where(
                    and_(Scale.api_token == token, Scale.is_active == True)  # noqa: E712
                )
            )
            return result.scalar_one_or_none()
        except Exception as exc:
            raise DatabaseError(message="Token bo'yicha tarozi olishda xato.", details={"error": str(exc)})

    async def get_all(self, active_only: bool = False) -> Sequence[Scale]:
        try:
            q = select(Scale)
            if active_only:
                q = q.where(Scale.is_active == True)  # noqa: E712
            q = q.order_by(Scale.name)
            result = await self.db.execute(q)
            return result.scalars().all()
        except Exception as exc:
            raise DatabaseError(message="Tarozlar ro'yxatida xato.", details={"error": str(exc)})

    async def count(self) -> int:
        try:
            result = await self.db.execute(select(func.count(Scale.id)))
            return result.scalar_one() or 0
        except Exception as exc:
            raise DatabaseError(message="Tarozlar sonida xato.", details={"error": str(exc)})

    # =========================================================================
    # UPDATE
    # =========================================================================

    async def update(self, scale: Scale, data: ScaleUpdate) -> Scale:
        try:
            for field, value in data.model_dump(exclude_unset=True).items():
                setattr(scale, field, value)
            await self.db.commit()
            await self.db.refresh(scale)
            return scale
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Tarozi yangilashda xato.", details={"error": str(exc)})

    async def update_last_reading(
        self,
        scale: Scale,
        weight_kg: float,
    ) -> None:
        """So'nggi o'lchov vaqti va qiymatini yangilash."""
        try:
            scale.last_reading_at = datetime.now(timezone.utc)
            scale.last_weight_kg  = weight_kg
            scale.status          = ScaleStatus.ACTIVE
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            logger.warning(f"Scale last reading update failed: {exc}")

    async def update_calibration(
        self,
        scale: Scale,
        new_factor:   float,
        sample_count: int,
    ) -> Scale:
        """Kalibratsiya koeffitsiyentini yangilash."""
        try:
            scale.calibration_factor       = round(new_factor, 6)
            scale.calibration_sample_count = sample_count
            scale.last_calibrated_at       = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(scale)
            logger.info(f"Scale {scale.id} calibrated: factor={new_factor:.4f}, n={sample_count}")
            return scale
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Kalibratsiyani saqlashda xato.", details={"error": str(exc)})

    # =========================================================================
    # WEIGHT MEASUREMENTS
    # =========================================================================

    async def create_weight_measurement(
        self,
        animal_id:        int,
        weight_kg:        float,
        source:           WeightSource,
        scale_id:         Optional[int]   = None,
        actual_weight_kg: Optional[float] = None,
        confidence_score: float           = 1.0,
        notes:            Optional[str]   = None,
        timestamp:        Optional[datetime] = None,
    ) -> WeightMeasurement:
        """Yangi vazn o'lchovi yozuvi yaratish."""
        try:
            ts = timestamp or datetime.now(timezone.utc)
            measurement = WeightMeasurement(
                animal_id           = animal_id,
                timestamp           = ts,
                estimated_weight_kg = weight_kg,
                actual_weight_kg    = actual_weight_kg,
                confidence_score    = confidence_score,
                camera_id           = f"scale-{scale_id}" if scale_id else "manual",
                source              = source,
                scale_id            = scale_id,
                notes               = notes,
            )
            self.db.add(measurement)
            await self.db.commit()
            await self.db.refresh(measurement)
            return measurement
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Vazn o'lchovi yaratishda xato.", details={"error": str(exc)})

    async def get_measurements_for_calibration(
        self,
        limit: int = 50,
    ) -> Sequence[WeightMeasurement]:
        """
        Kalibratsiya uchun: actual_weight_kg VA estimated_weight_kg
        ikkalasi ham bor bo'lgan o'lchovlarni olish.
        """
        try:
            result = await self.db.execute(
                select(WeightMeasurement)
                .where(
                    and_(
                        WeightMeasurement.actual_weight_kg != None,  # noqa: E711
                        WeightMeasurement.source == WeightSource.CAMERA_AI,
                    )
                )
                .order_by(WeightMeasurement.timestamp.desc())
                .limit(limit)
            )
            return result.scalars().all()
        except Exception as exc:
            raise DatabaseError(message="Kalibratsiya ma'lumotlarini olishda xato.", details={"error": str(exc)})

    async def attach_actual_weight(
        self,
        measurement_id:   int,
        actual_weight_kg: float,
    ) -> Optional[WeightMeasurement]:
        """Mavjud AI o'lchoviga haqiqiy vazn biriktirish (kalibratsiya uchun)."""
        try:
            result = await self.db.execute(
                select(WeightMeasurement).where(WeightMeasurement.id == measurement_id)
            )
            m = result.scalar_one_or_none()
            if m:
                m.actual_weight_kg = actual_weight_kg
                await self.db.commit()
                await self.db.refresh(m)
            return m
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Haqiqiy vaznni biriktirish xatosi.", details={"error": str(exc)})

    # =========================================================================
    # DELETE
    # =========================================================================

    async def delete(self, scale: Scale) -> None:
        try:
            await self.db.delete(scale)
            await self.db.commit()
        except Exception as exc:
            await self.db.rollback()
            raise DatabaseError(message="Tarozi o'chirishda xato.", details={"error": str(exc)})