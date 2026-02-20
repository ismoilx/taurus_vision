"""
Integration Tests — Detection → WeightMeasurement Pipeline

Bu tizimning YURAGIni tekshiradi:
  Jonivor aniqlanganda → WeightMeasurement avtomatik yaratilishi kerak

Test scenarios:
  1. Inject → WeightMeasurement DB da paydo bo'ladi
  2. Past confidence → WeightMeasurement yaratilmaydi
  3. Tanilmagan jonivor → WeightMeasurement yaratilmaydi
  4. Bir necha injection → bir necha o'lchov
"""

import pytest
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


class TestWeightPipeline:
    """Detection → WeightMeasurement integratsiya testlari."""

    async def test_inject_creates_weight(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_animal,
    ):
        """
        Inject endpoint → WeightMeasurement yaratadi.

        Bu tizimning asosiy funksiyasi.
        """
        from app.models.weight_measurement import WeightMeasurement

        # Oldingi holatni saqlaymiz
        before = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id == sample_animal.id
            )
        )

        # Inject
        r = await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "TEST-CAM-001",
            "confidence": 0.92,
            "count":      1,
        })
        assert r.status_code == 200
        assert r.json()["injected"] == 1

        # WeightMeasurement yaratildimi?
        after = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id == sample_animal.id
            )
        )

        # Session ni yangilaymiz (inject boshqa transaction da bo'ldi)
        await db.expire_all()
        after_fresh = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id == sample_animal.id
            )
        )

        assert after_fresh >= 1, (
            "Inject qilinganda WeightMeasurement yaratilishi kerak edi, "
            f"lekin {after_fresh} ta topildi"
        )

    async def test_inject_weight_values(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_animal,
    ):
        """
        Yaratilgan WeightMeasurement qiymatlari to'g'ri.
        """
        from app.models.weight_measurement import WeightMeasurement

        r = await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "VERIFY-CAM",
            "confidence": 0.95,
            "count":      1,
        })
        assert r.status_code == 200

        await db.expire_all()

        # So'nggi yaratilgan o'lchovni olamiz
        stmt = (
            select(WeightMeasurement)
            .where(WeightMeasurement.animal_id == sample_animal.id)
            .where(WeightMeasurement.camera_id == "VERIFY-CAM")
            .order_by(WeightMeasurement.timestamp.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        weight = result.scalar_one_or_none()

        assert weight is not None, "WeightMeasurement DB da topilmadi"
        assert weight.animal_id      == sample_animal.id
        assert weight.camera_id      == "VERIFY-CAM"
        assert weight.confidence_score >= 0.90
        assert weight.estimated_weight_kg > 0
        assert weight.estimated_weight_kg < 1000  # Realistik chegara

    async def test_low_confidence_no_weight(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_animal,
    ):
        """
        Past confidence (< 0.70) → WeightMeasurement yaratilmaydi.

        Detection saqlanadi, lekin sifatsiz o'lchov sifatida rad etiladi.
        """
        from app.models.weight_measurement import WeightMeasurement
        from app.models.detection import Detection

        # Oldingi detection soni
        det_before = await db.scalar(
            select(func.count(Detection.id)).where(
                Detection.animal_id == sample_animal.id
            )
        )

        # Past confidence bilan inject
        r = await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "LOW-CONF-CAM",
            "confidence": 0.50,  # Threshold dan past
            "count":      1,
        })
        assert r.status_code == 200

        await db.expire_all()

        # Detection yaratilgan bo'lishi kerak
        det_after = await db.scalar(
            select(func.count(Detection.id)).where(
                Detection.animal_id == sample_animal.id
            )
        )
        assert det_after > det_before, "Detection yaratilmadi"

        # Lekin WeightMeasurement yaratilmagan bo'lishi kerak
        # (agar threshold = 0.70 bo'lsa)
        weight_count = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id == sample_animal.id,
                WeightMeasurement.camera_id == "LOW-CONF-CAM",
            )
        )
        assert weight_count == 0, (
            f"Past confidence ({0.50}) da WeightMeasurement "
            f"yaratilmasligi kerak edi, lekin {weight_count} ta topildi"
        )

    async def test_multiple_inject_multiple_weights(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_animal,
    ):
        """
        count=3 → 3 ta WeightMeasurement.
        """
        from app.models.weight_measurement import WeightMeasurement

        r = await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "MULTI-CAM",
            "confidence": 0.88,
            "count":      3,
        })
        assert r.status_code == 200
        assert r.json()["injected"] == 3

        await db.expire_all()

        weight_count = await db.scalar(
            select(func.count(WeightMeasurement.id)).where(
                WeightMeasurement.animal_id == sample_animal.id,
                WeightMeasurement.camera_id == "MULTI-CAM",
            )
        )
        assert weight_count == 3, (
            f"3 ta inject → 3 ta WeightMeasurement kutilgan, "
            f"{weight_count} ta topildi"
        )

    async def test_unidentified_no_weight(
        self,
        client: AsyncClient,
        db: AsyncSession,
    ):
        """
        animal_id=None (tanilmagan) → WeightMeasurement yaratilmaydi.

        Aniqlanmagan jonivorning vaznini saqlamasligimiz kerak.
        """
        from app.models.weight_measurement import WeightMeasurement

        before = await db.scalar(
            select(func.count(WeightMeasurement.id))
        )

        r = await client.post("/api/v1/pipeline/inject", params={
            "camera_id":  "UNKNOWN-CAM",
            "confidence": 0.95,
            "count":      2,
        })
        assert r.status_code == 200

        await db.expire_all()

        after = await db.scalar(
            select(func.count(WeightMeasurement.id))
        )
        assert after == before, (
            "Tanilmagan jonivor uchun WeightMeasurement yaratilmasligi kerak"
        )

    async def test_inject_updates_animal_last_detected(
        self,
        client: AsyncClient,
        db: AsyncSession,
        sample_animal,
    ):
        """
        Inject → Animal.last_detected_at va total_detections yangilanadi.
        """
        from app.models.animal import Animal

        old_detections = sample_animal.total_detections

        r = await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "UPDATE-CAM",
            "confidence": 0.88,
            "count":      1,
        })
        assert r.status_code == 200

        await db.expire_all()

        stmt = select(Animal).where(Animal.id == sample_animal.id)
        result = await db.execute(stmt)
        updated_animal = result.scalar_one()

        assert updated_animal.last_detected_at is not None
        assert updated_animal.total_detections > old_detections


class TestWeightDashboard:
    """Dashboard da WeightMeasurement lar ko'rinyaptimi."""

    async def test_weights_list_after_inject(
        self,
        client: AsyncClient,
        sample_animal,
    ):
        """
        Inject qilingandan keyin /weights/ da ko'rinishi kerak.
        """
        # Inject
        await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "DASH-CAM",
            "confidence": 0.91,
            "count":      2,
        })

        # Dashboard endpoint
        r = await client.get("/api/v1/weights/?limit=20")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 2

    async def test_animal_weights_after_inject(
        self,
        client: AsyncClient,
        sample_animal,
    ):
        """
        Inject qilingandan keyin /weights/animal/{id} da ko'rinadi.
        """
        await client.post("/api/v1/pipeline/inject", params={
            "animal_id":  sample_animal.id,
            "camera_id":  "ANIMAL-CAM",
            "confidence": 0.88,
            "count":      1,
        })

        r = await client.get(f"/api/v1/weights/animal/{sample_animal.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["total"] >= 1
        # Barcha o'lchovlar shu jonivorga tegishli
        for item in data["items"]:
            assert item["animal_id"] == sample_animal.id