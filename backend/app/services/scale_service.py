"""
Taurus Vision — Scale Service

JAVOBGARLIK: Tarozi biznes logikasi.
  - Tarozi CRUD
  - Qo'lda vazn kiritish
  - Webhook orqali avtomatik vazn
  - AI kalibratsiya (median koeffitsiyent)
  - AI vs haqiqiy vazn taqqoslash hisoboti
"""

from __future__ import annotations

import statistics
from typing import Optional
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError
from app.core.logging_config import get_logger
from app.models.scale import Scale
from app.models.weight_measurement import WeightMeasurement, WeightSource
from app.models.animal import Animal
from app.repositories.scale_repository import ScaleRepository
from app.schemas.scale import (
    ScaleCreate,
    ScaleUpdate,
    ScaleResponse,
    ScaleListResponse,
    ManualWeightCreate,
    ScaleWebhookPayload,
    CalibrationDataPoint,
    CalibrationResponse,
    WeightComparisonResponse,
    WeightComparisonItem,
    WeightMeasurementExtended,
)

logger = get_logger(__name__)


class ScaleService:
    """Tarozi biznes logikasi servisi."""

    def __init__(self, db: AsyncSession) -> None:
        self.db   = db
        self.repo = ScaleRepository(db)

    # =========================================================================
    # TAROZI CRUD
    # =========================================================================

    async def list_scales(self, active_only: bool = False) -> ScaleListResponse:
        """Barcha tarozlar ro'yxati."""
        scales = await self.repo.get_all(active_only=active_only)
        return ScaleListResponse(
            items=[ScaleResponse.model_validate(s) for s in scales],
            total=len(scales),
        )

    async def get_scale(self, scale_id: int) -> ScaleResponse:
        """Tarozi tafsiloti."""
        scale = await self.repo.get_by_id(scale_id)
        if not scale:
            raise EntityNotFoundError(entity="Scale", entity_id=scale_id)
        return ScaleResponse.model_validate(scale)

    async def create_scale(self, data: ScaleCreate) -> ScaleResponse:
        """Yangi tarozi yaratish."""
        scale = await self.repo.create(data)
        logger.info(f"Scale created: id={scale.id}, name='{scale.name}', type={scale.scale_type}")
        return ScaleResponse.model_validate(scale)

    async def update_scale(self, scale_id: int, data: ScaleUpdate) -> ScaleResponse:
        """Tarozi ma'lumotlarini yangilash."""
        scale = await self.repo.get_by_id(scale_id)
        if not scale:
            raise EntityNotFoundError(entity="Scale", entity_id=scale_id)
        updated = await self.repo.update(scale, data)
        return ScaleResponse.model_validate(updated)

    async def delete_scale(self, scale_id: int) -> None:
        """Tarozi o'chirish."""
        scale = await self.repo.get_by_id(scale_id)
        if not scale:
            raise EntityNotFoundError(entity="Scale", entity_id=scale_id)
        await self.repo.delete(scale)
        logger.info(f"Scale deleted: id={scale_id}")

    # =========================================================================
    # VAZN O'LCHOVLARI
    # =========================================================================

    async def record_manual_weight(self, data: ManualWeightCreate) -> WeightMeasurementExtended:
        """
        Foydalanuvchi tarozidan o'qib, qo'lda kiritadigan vazn.

        Confidence: 1.0 (manual = to'liq ishonch).
        actual_weight_kg = estimated_weight_kg (bir xil) — haqiqiy o'lchov.
        """
        # Jonivor mavjudligini tekshirish
        animal = await self.db.get(Animal, data.animal_id)
        if not animal:
            raise EntityNotFoundError(entity="Animal", entity_id=data.animal_id)

        # Tarozi mavjudligini tekshirish (agar ko'rsatilgan bo'lsa)
        if data.scale_id:
            scale = await self.repo.get_by_id(data.scale_id)
            if not scale:
                raise EntityNotFoundError(entity="Scale", entity_id=data.scale_id)
            if not scale.is_active:
                raise BusinessRuleViolationError(
                    message="Tarozi faol emas.",
                    details={"scale_id": data.scale_id},
                )

        # O'lchov yozuvini yaratish
        measurement = await self.repo.create_weight_measurement(
            animal_id        = data.animal_id,
            weight_kg        = data.weight_kg,
            source           = WeightSource.MANUAL,
            scale_id         = data.scale_id,
            actual_weight_kg = data.weight_kg,  # manual = haqiqiy vazn
            confidence_score = 1.0,
            notes            = data.notes,
            timestamp        = data.measured_at,
        )

        # Tarozining so'nggi o'lchov vaqtini yangilash
        if data.scale_id:
            scale = await self.repo.get_by_id(data.scale_id)
            if scale:
                await self.repo.update_last_reading(scale, data.weight_kg)

        logger.info(
            f"Manual weight recorded: animal={data.animal_id}, "
            f"weight={data.weight_kg}kg, scale={data.scale_id}"
        )
        return WeightMeasurementExtended.model_validate(measurement)

    async def process_scale_webhook(
        self,
        scale_id: int,
        payload:  ScaleWebhookPayload,
    ) -> WeightMeasurementExtended:
        """
        Tarozi qurilmadan kelgan webhook (serial/api).

        Autentifikatsiya: api_token orqali.
        """
        # Tarozi mavjudligini tekshirish
        scale = await self.repo.get_by_id(scale_id)
        if not scale:
            raise EntityNotFoundError(entity="Scale", entity_id=scale_id)

        # Token tekshirish
        if scale.api_token != payload.api_token:
            raise BusinessRuleViolationError(
                message="Noto'g'ri API token.",
                details={"scale_id": scale_id},
            )

        if not scale.is_active:
            raise BusinessRuleViolationError(
                message="Tarozi faol emas.",
                details={"scale_id": scale_id},
            )

        # Agar animal_id berilmagan bo'lsa — measurement yaratmaymiz, faqat log
        animal_id = payload.animal_id
        if not animal_id:
            logger.warning(f"Webhook received without animal_id: scale={scale_id}, weight={payload.weight_kg}kg")
            await self.repo.update_last_reading(scale, payload.weight_kg)
            raise BusinessRuleViolationError(
                message="animal_id majburiy (hozircha).",
                details={"scale_id": scale_id},
            )

        # Jonivor mavjudligini tekshirish
        animal = await self.db.get(Animal, animal_id)
        if not animal:
            raise EntityNotFoundError(entity="Animal", entity_id=animal_id)

        measurement = await self.repo.create_weight_measurement(
            animal_id        = animal_id,
            weight_kg        = payload.weight_kg,
            source           = WeightSource.SCALE_API,
            scale_id         = scale_id,
            actual_weight_kg = payload.weight_kg,
            confidence_score = 1.0,
            notes            = f"Webhook: {payload.raw_data[:100]}" if payload.raw_data else None,
        )

        await self.repo.update_last_reading(scale, payload.weight_kg)
        logger.info(f"Webhook weight recorded: scale={scale_id}, animal={animal_id}, weight={payload.weight_kg}kg")
        return WeightMeasurementExtended.model_validate(measurement)

    async def attach_actual_weight(
        self,
        measurement_id:   int,
        actual_weight_kg: float,
    ) -> WeightMeasurementExtended:
        """Mavjud AI o'lchoviga haqiqiy tarozi vazni biriktirish."""
        measurement = await self.repo.attach_actual_weight(measurement_id, actual_weight_kg)
        if not measurement:
            raise EntityNotFoundError(entity="WeightMeasurement", entity_id=measurement_id)
        logger.info(f"Actual weight attached: measurement={measurement_id}, actual={actual_weight_kg}kg")
        return WeightMeasurementExtended.model_validate(measurement)

    # =========================================================================
    # KALIBRATSIYA
    # =========================================================================

    async def calibrate(
        self,
        scale_id:    int,
        data_points: list[CalibrationDataPoint],
    ) -> CalibrationResponse:
        """
        AI taxmin modelini kalibratsiya qilish.

        Algoritm: Median(actual / ai_estimated) — outlier ga chidamli.
        Kamida 3 ta nuqta kerak.
        """
        scale = await self.repo.get_by_id(scale_id)
        if not scale:
            raise EntityNotFoundError(entity="Scale", entity_id=scale_id)

        if len(data_points) < 3:
            raise BusinessRuleViolationError(
                message="Kamida 3 ta kalibratsiya nuqtasi kerak.",
                details={"provided": len(data_points)},
            )

        # Har bir nuqta uchun measurement ni DB dan olib, ratios hisoblash
        ratios: list[float] = []
        valid_points: list[tuple[float, float]] = []

        for point in data_points:
            result = await self.db.execute(
                select(WeightMeasurement).where(WeightMeasurement.id == point.measurement_id)
            )
            m = result.scalar_one_or_none()
            if m is None:
                logger.warning(f"Calibration: measurement {point.measurement_id} not found, skipping")
                continue

            if m.estimated_weight_kg <= 0:
                continue

            ratio = point.actual_weight_kg / m.estimated_weight_kg
            # Outlier filtr: ratio 0.5–2.0 orasida bo'lsin
            if 0.5 <= ratio <= 2.0:
                ratios.append(ratio)
                valid_points.append((m.estimated_weight_kg, point.actual_weight_kg))

        if len(ratios) < 3:
            raise BusinessRuleViolationError(
                message="Yetarli darajada yaroqli kalibratsiya nuqtalari yo'q (kamida 3 ta kerak).",
                details={"valid": len(ratios)},
            )

        old_factor = scale.calibration_factor

        # Median koeffitsiyent — outlier ga chidamli
        new_factor = statistics.median(ratios)

        # Xato hisoblash
        errors = [abs(ai * new_factor - actual) for ai, actual in valid_points]
        errors_pct = [abs(ai * new_factor - actual) / actual * 100 for ai, actual in valid_points]

        mean_abs_error = round(statistics.mean(errors), 2)
        mean_rel_error = round(statistics.mean(errors_pct), 2)

        # Yangi faktorni saqlash
        updated_scale = await self.repo.update_calibration(
            scale,
            new_factor   = new_factor,
            sample_count = len(ratios),
        )

        improvement = abs(old_factor - 1.0) - abs(new_factor - 1.0)
        if improvement > 0.01:
            message = f"Kalibratsiya yaxshilandi: faktor {old_factor:.4f} → {new_factor:.4f}"
        elif abs(new_factor - 1.0) < 0.02:
            message = f"AI taxmini yaxshi kalibratlangan (faktor ≈ 1.0)"
        else:
            message = f"Kalibratsiya yangilandi: {old_factor:.4f} → {new_factor:.4f}"

        logger.info(
            f"Scale {scale_id} calibrated: "
            f"old={old_factor:.4f}, new={new_factor:.4f}, "
            f"n={len(ratios)}, mae={mean_abs_error}kg"
        )

        return CalibrationResponse(
            scale_id             = scale_id,
            scale_name           = updated_scale.name,
            old_factor           = old_factor,
            new_factor           = new_factor,
            sample_count         = len(ratios),
            mean_absolute_error  = mean_abs_error,
            mean_relative_error  = mean_rel_error,
            message              = message,
        )

    # =========================================================================
    # AI vs HAQIQIY TAQQOSLASH HISOBOTI
    # =========================================================================

    async def get_comparison_report(self, limit: int = 50) -> WeightComparisonResponse:
        """
        AI taxmin vs haqiqiy vazn taqqoslash hisoboti.

        Faqat actual_weight_kg bor bo'lgan o'lchovlarni taqqoslaydi.
        """
        # Barcha o'lchovlarni olish (actual_weight_kg bor yoki yo'q)
        result = await self.db.execute(
            select(WeightMeasurement)
            .order_by(WeightMeasurement.timestamp.desc())
            .limit(limit)
        )
        measurements = result.scalars().all()

        # Animal tag_id larini olish
        animal_ids = list({m.animal_id for m in measurements})
        animals_map: dict[int, str] = {}
        if animal_ids:
            a_result = await self.db.execute(
                select(Animal).where(Animal.id.in_(animal_ids))
            )
            for a in a_result.scalars().all():
                animals_map[a.id] = a.tag_id

        # Joriy faktor (birinchi aktiv tarozidan)
        scales_result = await self.db.execute(
            select(Scale).where(Scale.is_active == True).limit(1)  # noqa: E712
        )
        first_scale = scales_result.scalar_one_or_none()
        current_factor = first_scale.calibration_factor if first_scale else 1.0

        # Taqqoslash itemlarini yaratish
        items: list[WeightComparisonItem] = []
        errors_kg:  list[float] = []
        errors_pct: list[float] = []

        for m in measurements:
            diff_kg  = None
            diff_pct = None

            if m.actual_weight_kg is not None:
                diff_kg  = round(m.estimated_weight_kg - m.actual_weight_kg, 2)
                if m.actual_weight_kg > 0:
                    diff_pct = round(diff_kg / m.actual_weight_kg * 100, 1)
                    errors_kg.append(abs(diff_kg))
                    errors_pct.append(abs(diff_pct))

            items.append(WeightComparisonItem(
                measurement_id   = m.id,
                animal_id        = m.animal_id,
                animal_tag_id    = animals_map.get(m.animal_id, f"ID-{m.animal_id}"),
                timestamp        = m.timestamp,
                ai_weight_kg     = m.estimated_weight_kg,
                actual_weight_kg = m.actual_weight_kg,
                difference_kg    = diff_kg,
                difference_pct   = diff_pct,
                source           = m.source.value if hasattr(m.source, 'value') else str(m.source),
            ))

        mean_error_kg  = round(statistics.mean(errors_kg),  2) if errors_kg  else None
        mean_error_pct = round(statistics.mean(errors_pct), 2) if errors_pct else None

        # Tavsiya etilgan faktor (agar yetarli ma'lumot bo'lsa)
        recommended_factor: Optional[float] = None
        if len(errors_kg) >= 3:
            ratios = []
            for m in measurements:
                if m.actual_weight_kg and m.estimated_weight_kg > 0:
                    r = m.actual_weight_kg / m.estimated_weight_kg
                    if 0.5 <= r <= 2.0:
                        ratios.append(r)
            if len(ratios) >= 3:
                recommended_factor = round(statistics.median(ratios), 4)

        return WeightComparisonResponse(
            items              = items,
            total              = len(items),
            mean_error_kg      = mean_error_kg,
            mean_error_pct     = mean_error_pct,
            current_factor     = current_factor,
            recommended_factor = recommended_factor,
        )