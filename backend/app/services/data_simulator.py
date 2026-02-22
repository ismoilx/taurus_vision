"""
Taurus Vision — Real-time ma'lumot simulatori

Pipeline yoqilganda ishga tushadi va barcha aktiv jonivorlar uchun
haqiqiyga o'xshash Detection + WeightMeasurement yozuvlari yaratadi.
Bu ADI hisoblanishi uchun yetarli ma'lumot beradi.

FOYDALANISH:
    pipeline.py da DataSimulator yaratiladi va pipeline bilan birga ishga tushiriladi.
    Har 30 soniyada barcha aktiv jonivorlar uchun 1-3 ta detection yoziladi.
"""

import asyncio
import random
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from app.core.database import AsyncSessionLocal
from app.models.animal import Animal, AnimalStatus
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement

logger = logging.getLogger(__name__)

# Kamera ID lari — simulatsiya
SIM_CAMERAS = ["CAM-SIM-001", "CAM-SIM-002", "CAM-SIM-003"]

# Ferma zonalari (normalized koordinatalar)
FEEDING_ZONE  = (0.1, 0.2, 0.5, 0.6)   # (x1, y1, x2, y2)
RESTING_ZONE  = (0.5, 0.5, 0.9, 0.9)
MOVEMENT_ZONE = (0.1, 0.1, 0.9, 0.9)


def _random_bbox(zone: Optional[tuple] = None) -> dict:
    """Tasodifiy bounding box — zona ichida."""
    if zone:
        x1, y1, x2, y2 = zone
        cx = random.uniform(x1, x2)
        cy = random.uniform(y1, y2)
    else:
        cx = random.uniform(0.1, 0.9)
        cy = random.uniform(0.1, 0.9)

    w = random.uniform(0.12, 0.35)
    h = random.uniform(0.15, 0.40)
    x = max(0.0, cx - w / 2)
    y = max(0.0, cy - h / 2)

    return {
        "x": round(x, 4),
        "y": round(y, 4),
        "w": round(w, 4),
        "h": round(h, 4),
    }


def _weight_from_bbox(bbox: dict, base_weight: float) -> float:
    """Bbox o'lchamidan vazn taxmini."""
    area = bbox["w"] * bbox["h"]
    # Base formula + individual variation
    estimated = (area * 4000) + 80
    # Actual weight bilan interpolatsiya
    blended = estimated * 0.3 + base_weight * 0.7
    noise   = random.gauss(0, 2.5)
    return round(max(50, min(800, blended + noise)), 1)


def _get_hour_activity(hour: int) -> float:
    """Soatga qarab faollik darajasi (0-1)."""
    # Sigirlar erta ertalab va kechqurun faol
    activity_curve = {
        range(0, 5):   0.1,   # Kechasi — uxlaydi
        range(5, 8):   0.8,   # Erta ertalab — faol
        range(8, 11):  0.6,   # Ertalab — o'rtacha
        range(11, 14): 0.3,   # Tush — dam oladi
        range(14, 17): 0.5,   # Tushdan keyin
        range(17, 20): 0.9,   # Kechqurun — juda faol
        range(20, 24): 0.2,   # Kech kechqurun
    }
    for hours_range, level in activity_curve.items():
        if hour in hours_range:
            return level
    return 0.5


class DataSimulator:
    """
    Real-time ma'lumot simulatori.

    Pipeline ishlayotganda barcha aktiv jonivvorlar uchun
    haqiqiyga o'xshash Detection va WeightMeasurement yaratadi.
    ADI hisoblash uchun yetarli ma'lumot ta'minlaydi.
    """

    INTERVAL_SECONDS = 30   # Har 30 soniyada yangilash
    MAX_DETECTIONS   = 3    # Har intervalda max deteksiya soni

    def __init__(self) -> None:
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._animal_weights: dict[int, float] = {}  # animal_id → base_weight
        logger.info("DataSimulator initialized")

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task    = asyncio.create_task(self._run_loop())
        logger.info("✅ DataSimulator started — har 30s da ma'lumot yaratiladi")

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("DataSimulator stopped")

    @property
    def is_running(self) -> bool:
        return self._running

    async def _run_loop(self) -> None:
        """Asosiy tsikl."""
        # Birinchi ishga tushganda bazaviy vazn olish/yaratish
        await self._init_animal_weights()

        while self._running:
            try:
                await self._generate_tick()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Simulator tick error: {e}", exc_info=True)

            await asyncio.sleep(self.INTERVAL_SECONDS)

    async def _init_animal_weights(self) -> None:
        """Aktiv jonivorlar uchun bazaviy vazn belgilash."""
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            )
            animals = result.scalars().all()
            for animal in animals:
                if animal.id not in self._animal_weights:
                    # Tur va jinsiga qarab bazaviy vazn
                    if animal.species.value == "cattle":
                        base = random.uniform(280, 450)
                    elif animal.species.value == "sheep":
                        base = random.uniform(40, 90)
                    else:
                        base = random.uniform(30, 70)
                    self._animal_weights[animal.id] = base

        logger.info(f"DataSimulator: {len(self._animal_weights)} ta jonivor bazaviy vazni belgilandi")

    async def _generate_tick(self) -> None:
        """Bitta tsikl — barcha aktiv jonivvorlar uchun ma'lumot yaratish."""
        now = datetime.utcnow()  # timezone-naive — DB TIMESTAMP WITHOUT TIME ZONE
        hour = now.hour
        activity_level = _get_hour_activity(hour)

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Animal).where(Animal.status == AnimalStatus.ACTIVE)
            )
            animals = result.scalars().all()

            if not animals:
                return

            created_count = 0

            for animal in animals:
                # Faollikka qarab detection yaratish yoki yo'q
                if random.random() > activity_level + 0.1:
                    continue  # Bu intervalda ko'rinmadi

                # Bazaviy vazn — sekin o'sadi (0.05-0.2 kg/kun)
                if animal.id not in self._animal_weights:
                    self._animal_weights[animal.id] = random.uniform(250, 400)

                base_w = self._animal_weights[animal.id]
                # Kuniga ~0.1-0.3 kg o'sish
                daily_gain = random.uniform(0.1, 0.3) / (24 * 3600 / self.INTERVAL_SECONDS)
                self._animal_weights[animal.id] += daily_gain

                # 1-3 ta detection
                n_detections = random.randint(1, self.MAX_DETECTIONS)
                camera_id = random.choice(SIM_CAMERAS)

                for i in range(n_detections):
                    # Zona tanlash — soatga qarab
                    if 5 <= hour <= 9 or 17 <= hour <= 20:
                        zone = FEEDING_ZONE   # Ovqatlanish vaqti
                    elif 11 <= hour <= 14:
                        zone = RESTING_ZONE   # Dam olish vaqti
                    else:
                        zone = None           # Tasodifiy harakat

                    bbox = _random_bbox(zone)
                    weight = _weight_from_bbox(bbox, base_w)
                    confidence = round(random.uniform(0.72, 0.97), 3)

                    ts = now - timedelta(seconds=random.randint(0, self.INTERVAL_SECONDS - 1))  # naive

                    # Detection yozuvi
                    det = Detection(
                        animal_id=         animal.id,
                        camera_id=         camera_id,
                        timestamp=         ts,
                        confidence=        confidence,
                        class_id=          19,   # COCO: cow
                        class_name=        "cow",
                        bbox=              bbox,
                        estimated_weight=  weight,
                        inference_time_ms= round(random.uniform(45, 180), 1),
                    )
                    db.add(det)

                    # WeightMeasurement (confidence yetarli bo'lsa)
                    if confidence >= 0.75:
                        db.add(WeightMeasurement(
                            animal_id=           animal.id,
                            timestamp=           ts,
                            estimated_weight_kg= weight,
                            confidence_score=    confidence,
                            camera_id=           camera_id,
                            raw_ai_data={
                                "bbox":     bbox,
                                "source":   "simulator",
                                "activity": round(activity_level, 2),
                            },
                        ))

                    # Animal.mark_detected
                    animal.mark_detected(ts)
                    created_count += 1

            await db.commit()

            if created_count > 0:
                logger.debug(
                    f"Simulator tick | animals={len(animals)} | "
                    f"detections={created_count} | hour={hour} | "
                    f"activity={activity_level:.1f}"
                )

    async def force_generate(self, animal_id: int, n: int = 5) -> int:
        """
        Bitta jonivor uchun zudlik bilan n ta detection yaratish.
        ADI debug uchun ishlatiladi.
        """
        now = datetime.utcnow()  # timezone-naive — DB TIMESTAMP WITHOUT TIME ZONE
        base_w = self._animal_weights.get(animal_id, random.uniform(280, 400))

        async with AsyncSessionLocal() as db:
            # Jonivorni tekshirish
            result = await db.execute(select(Animal).where(Animal.id == animal_id))
            animal = result.scalar_one_or_none()
            if not animal:
                return 0

            for i in range(n):
                bbox = _random_bbox()
                weight = _weight_from_bbox(bbox, base_w)
                confidence = round(random.uniform(0.78, 0.96), 3)
                ts = now - timedelta(minutes=random.randint(0, 120))

                db.add(Detection(
                    animal_id=         animal_id,
                    camera_id=         "CAM-SIM-FORCE",
                    timestamp=         ts,
                    confidence=        confidence,
                    class_id=          19,
                    class_name=        "cow",
                    bbox=              bbox,
                    estimated_weight=  weight,
                    inference_time_ms= round(random.uniform(45, 150), 1),
                ))
                db.add(WeightMeasurement(
                    animal_id=           animal_id,
                    timestamp=           ts,
                    estimated_weight_kg= weight,
                    confidence_score=    confidence,
                    camera_id=           "CAM-SIM-FORCE",
                    raw_ai_data={"source": "force_simulate"},
                ))
                animal.mark_detected(ts)

            await db.commit()
            logger.info(f"Force generated {n} detections for animal {animal_id}")
            return n


# Singleton
_simulator: Optional[DataSimulator] = None

def get_simulator() -> DataSimulator:
    global _simulator
    if _simulator is None:
        _simulator = DataSimulator()
    return _simulator