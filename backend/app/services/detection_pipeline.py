"""
Automated Detection Pipeline — ADI integratsiyasi bilan.

PIPELINE FLOW:
    Camera Frame
        ↓
    YOLO Detection
        ↓
    Animal Identification (muzzle embedding)
        ↓
    Detection Log (DB)
        ↓
    ADI Trigger Check      ← YANGI
        ↓
    Alert Check            ← YANGI
        ↓
    WebSocket Broadcast

ADI INTEGRATSIYA STRATEGIYASI:
    Har deteksiyada ADI qayta hisoblanmaydi —
    bu juda qimmat operatsiya.

    Buning o'rniga:
    1. Har deteksiyada animal.last_detected_at yangilanadi
    2. Agar jonivor missing alert ostida bo'lsa — avtomatik yopiladi
    3. Kunlik ADI Celery task orqali hisoblanadi (00:30 UTC)
    4. Real vaqt ADI faqat so'rov bo'lganda hisoblanadi (on-demand)
"""

# detection_pipeline.py — TO'G'RI IMPORTLAR
import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.camera.base import CameraServiceInterface
from app.services.ai.yolo_service import YoloService
from app.services.ai.base import Detection as YOLODetection
from app.services.identification_service import IdentificationService
from app.services.alert_service import AlertService
from app.api.v1.websocket import ConnectionManager
from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.animal import Animal
from app.models.detection import Detection
from app.models.alert import Alert, AlertType, AlertStatus
from app.models.weight_measurement import WeightMeasurement
from app.utils.image_utils import extract_muzzle_region

# Minimal confidence — past bo'lsa WeightMeasurement yaratilmaydi
WEIGHT_CONFIDENCE_THRESHOLD = 0.70

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------ #
# Pipeline Stats                                                       #
# ------------------------------------------------------------------ #

class PipelineStats:
    """
    Pipeline ishlash statistikasi.
    Thread-safe emas — faqat bitta pipeline instance uchun.
    """

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.started_at:         Optional[datetime] = None
        self.total_frames:       int   = 0
        self.processed_frames:   int   = 0
        self.yolo_detections:    int   = 0
        self.identified:         int   = 0
        self.unidentified:       int   = 0
        self.db_writes:          int   = 0
        self.alert_checks:       int   = 0
        self.missing_resolved:   int   = 0
        self.errors:             int   = 0
        self.total_inference_ms: float = 0.0
        self.total_identify_ms:  float = 0.0

    @property
    def uptime_seconds(self) -> float:
        if not self.started_at:
            return 0.0
        return (datetime.now(timezone.utc) - self.started_at).total_seconds()

    @property
    def fps(self) -> float:
        uptime = self.uptime_seconds
        if uptime == 0:
            return 0.0
        return round(self.processed_frames / uptime, 2)

    @property
    def avg_inference_ms(self) -> float:
        if self.processed_frames == 0:
            return 0.0
        return round(self.total_inference_ms / self.processed_frames, 2)

    def to_dict(self) -> dict:
        return {
            "uptime_seconds":    round(self.uptime_seconds, 1),
            "total_frames":      self.total_frames,
            "processed_frames":  self.processed_frames,
            "yolo_detections":   self.yolo_detections,
            "identified":        self.identified,
            "unidentified":      self.unidentified,
            "db_writes":         self.db_writes,
            "alert_checks":      self.alert_checks,
            "missing_resolved":  self.missing_resolved,
            "errors":            self.errors,
            "fps":               self.fps,
            "avg_inference_ms":  self.avg_inference_ms,
        }


# ------------------------------------------------------------------ #
# Detection Pipeline                                                   #
# ------------------------------------------------------------------ #

class DetectionPipeline:
    """
    Asosiy detection pipeline.

    Camera → YOLO → Identify → DB → Alert Check → WebSocket

    RESILIENCE:
        - Bitta frame xatosi pipeline ni to'xtatmaydi
        - Har bir bosqich mustaqil try/except bilan o'ralgan
        - Xatolar logga yoziladi va statistikaga qo'shiladi

    PERFORMANCE:
        - Frame throttling: MIN_FRAME_INTERVAL soniya kutish
        - Non-blocking DB writes
        - Parallel identification (bir nechta detection uchun)
    """

    # Minimum kadrlar orasidagi interval (sekund)
    # 0.5 = sekundiga max 2 kadr qayta ishlash
    MIN_FRAME_INTERVAL = 0.5
    def get_stats(self) -> dict:
        """
        Pipeline real vaqt statistikasini qaytaradi.

        Returns:
            PipelineStats dan olingan to'liq statistika dict,
            qo'shimcha status va camera_id ma'lumotlari bilan.
        """
        base = self.stats.to_dict()
        base["status"]    = "running" if self._running else "stopped"
        base["camera_id"] = self.camera.camera_id
        return base
    def __init__(
        self,
        camera_service: CameraServiceInterface,
        yolo_service:   YoloService,
        ws_manager:     Optional[ConnectionManager] = None,
    ) -> None:
        self.camera    = camera_service
        self.yolo      = yolo_service
        self.ws_manager = ws_manager

        self._running  = False
        self._task:    Optional[asyncio.Task] = None
        self.stats     = PipelineStats()

        logger.info(
            f"DetectionPipeline initialized | "
            f"camera={camera_service.__class__.__name__}"
        )

    # ================================================================ #
    # LIFECYCLE                                                          #
    # ================================================================ #

    async def start(self) -> None:
        """Pipeline ni ishga tushirish."""
        if self._running:
            logger.warning("Pipeline already running")
            return

        self._running = True
        self.stats.reset()
        self.stats.started_at = datetime.now(timezone.utc)

        logger.info("Detection pipeline starting...")

        await self.camera.start()
        self._task = asyncio.create_task(self._run_loop())

        logger.info("Detection pipeline started ✓")

    async def stop(self) -> None:
        """Pipeline ni to'xtatish."""
        if not self._running:
            return

        logger.info("Detection pipeline stopping...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self.camera.stop()

        logger.info(
            f"Pipeline stopped | stats={self.stats.to_dict()}"
        )

    @property
    def is_running(self) -> bool:
        return self._running

    # ================================================================ #
    # MAIN LOOP                                                          #
    # ================================================================ #

    async def _run_loop(self) -> None:
        """
        Asosiy tsikl — kameradan kadr olib qayta ishlaydi.
        """
        last_frame_time = 0.0

        while self._running:
            try:
                # Frame throttling
                now = time.monotonic()
                elapsed = now - last_frame_time
                if elapsed < self.MIN_FRAME_INTERVAL:
                    await asyncio.sleep(
                        self.MIN_FRAME_INTERVAL - elapsed
                    )

                # Kadr olish
                frame = await self.camera.get_frame()
                self.stats.total_frames += 1

                if frame is None:
                    await asyncio.sleep(0.1)
                    continue

                last_frame_time = time.monotonic()

                # Kadrni qayta ishlash
                await self._process_frame(frame)
                self.stats.processed_frames += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats.errors += 1
                logger.error(
                    f"Pipeline loop error: {e}",
                    exc_info=True,
                )
                await asyncio.sleep(1.0)

    # ================================================================ #
    # FRAME PROCESSING                                                   #
    # ================================================================ #

    async def _process_frame(self, frame) -> None:
        """
        Bitta kadrni to'liq qayta ishlash.

        Bosqichlar:
            1. YOLO detection
            2. Har bir detection uchun identifikatsiya
            3. DB ga saqlash
            4. ADI/Alert tekshiruvi
            5. WebSocket broadcast
        """
        # STEP 1: YOLO Detection
        t0 = time.monotonic()
        try:
            inference_result = await self.yolo.detect(frame.frame)
            detections = inference_result.detections
        except Exception as e:
            logger.error(f"YOLO inference failed: {e}")
            self.stats.errors += 1
            return

        inference_ms = (time.monotonic() - t0) * 1000
        self.stats.total_inference_ms += inference_ms
        self.stats.yolo_detections    += len(detections)

        if not detections:
            return

        # STEP 2-5: Har bir detection uchun
        async with AsyncSessionLocal() as db:
            for det in detections:
                await self._process_single_detection(
                    db=        db,
                    detection= det,
                    frame=     frame,
                    inference_ms=inference_ms,
                )

    async def _process_single_detection(
        self,
        db:           AsyncSession,
        detection:    YOLODetection,
        frame,
        inference_ms: float,
    ) -> None:
        """
        Bitta YOLO detection ni qayta ishlash.

        Args:
            db:           DB session
            detection:    YOLO detection natijasi
            frame:        Asl kadr (identification uchun)
            inference_ms: YOLO latency
        """
        # STEP 2: Identifikatsiya
        t_identify = time.monotonic()
        animal_id: Optional[int] = None

        try:
            animal_id = await self._identify_animal(
                db=        db,
                detection= detection,
                frame=     frame,
            )
            identify_ms = (time.monotonic() - t_identify) * 1000
            self.stats.total_identify_ms += identify_ms

            if animal_id:
                self.stats.identified += 1
            else:
                self.stats.unidentified += 1

        except Exception as e:
            logger.warning(f"Identification failed: {e}")
            self.stats.errors += 1

        # STEP 3: DB ga saqlash
        try:
            animal_tag_id: Optional[str] = None
            saved_detection, animal_tag_id = await self._save_detection(
                db=           db,
                detection=    detection,
                animal_id=    animal_id,
                inference_ms= inference_ms,
            )
            self.stats.db_writes += 1
        except Exception as e:
            logger.error(f"Detection save failed: {e}", exc_info=True)
            self.stats.errors += 1
            return

        # STEP 4: ADI / Alert tekshiruvi
        if animal_id:
            try:
                await self._handle_adi_integration(
                    db=        db,
                    animal_id= animal_id,
                )
                self.stats.alert_checks += 1
            except Exception as e:
                # Alert xatosi pipeline ni to'xtatmasin
                logger.warning(
                    f"ADI integration failed for animal {animal_id}: {e}"
                )

        # STEP 5: WebSocket broadcast
        if self.ws_manager and saved_detection:
            try:
                await self._broadcast_detection(
                    detection=     saved_detection,
                    animal_id=     animal_id,
                    animal_tag_id= animal_tag_id,
                )
            except Exception as e:
                logger.warning(f"WebSocket broadcast failed: {e}")

    # ================================================================ #
    # IDENTIFICATION                                                     #
    # ================================================================ #

    async def _identify_animal(
        self,
        db:        AsyncSession,
        detection: YOLODetection,
        frame,
    ) -> Optional[int]:
        """
        Detected jonivorni bazadagi embeddinglar bilan taqqoslash.

        Args:
            db:        DB session
            detection: YOLO detection (bbox ma'lumotlari bilan)
            frame:     Asl kadr

        Returns:
            animal_id yoki None (tanilmasa)
        """
        # Muzzle regionni kesib olish
        muzzle_crop = extract_muzzle_region(
            frame=frame,
            bbox=detection.bbox,
        )
        if muzzle_crop is None:
            return None

        # Identifikatsiya servisi
        id_service = IdentificationService(db)
        result = await id_service.identify(muzzle_crop)

        return result.animal_id if result.is_identified else None

    # ================================================================ #
    # DB SAVE                                                           #
    # ================================================================ #

    async def _save_detection(
        self,
        db:           AsyncSession,
        detection:    YOLODetection,
        animal_id:    Optional[int],
        inference_ms: float,
    ) -> tuple[Optional[Detection], Optional[str]]:
        """
        Detection + WeightMeasurement DB ga saqlash.

        PIPELINE:
            1. Detection → detections jadvali (har doim)
            2. WeightMeasurement → weight_measurements jadvali
               FAQAT: animal tanilgan + confidence >= WEIGHT_CONFIDENCE_THRESHOLD
            3. Animal.last_detected_at yangilash

        Returns:
            (Saqlangan Detection ORM obyekti, animal tag_id yoki None)
        """
        now = datetime.now(timezone.utc)

        # Bbox dict va vazn taxmin
        bbox_dict = {
            "x": detection.bbox.x,
            "y": detection.bbox.y,
            "w": detection.bbox.w,
            "h": detection.bbox.h,
        }
        w, h = detection.bbox.w, detection.bbox.h
        estimated_weight_kg = round(
            max(50.0, min(800.0, (w * h * 4000) + 80)), 1
        )

        # ── 1. Detection yozuvi ──────────────────────────────────
        det_record = Detection(
            animal_id=        animal_id,
            camera_id=        self.camera.camera_id,
            timestamp=        now,
            confidence=       detection.confidence,
            class_id=         detection.class_id,
            class_name=       detection.class_name,
            bbox=             bbox_dict,
            estimated_weight= estimated_weight_kg,
            frame_number=     getattr(detection, "frame_number", None),
            inference_time_ms=inference_ms,
        )
        db.add(det_record)

        # ── 2. Animal + WeightMeasurement ───────────────────────
        animal_tag_id: Optional[str] = None
        if animal_id:
            stmt   = select(Animal).where(Animal.id == animal_id)
            result = await db.execute(stmt)
            animal = result.scalar_one_or_none()

            if animal:
                animal.mark_detected(now)
                animal_tag_id = animal.tag_id

                # Yuqori confidence → WeightMeasurement yaratish
                if detection.confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
                    weight_record = WeightMeasurement(
                        animal_id=          animal_id,
                        timestamp=          now,
                        estimated_weight_kg=estimated_weight_kg,
                        confidence_score=   round(detection.confidence, 3),
                        camera_id=          self.camera.camera_id,
                        raw_ai_data={
                            "bbox":         bbox_dict,
                            "class_name":   detection.class_name,
                            "class_id":     detection.class_id,
                            "inference_ms": round(inference_ms, 1),
                            "source":       "yolo_pipeline",
                        },
                    )
                    db.add(weight_record)
                    logger.debug(
                        f"WeightMeasurement | animal={animal_tag_id} | "
                        f"weight={estimated_weight_kg}kg | "
                        f"conf={detection.confidence:.2f}"
                    )

        await db.commit()
        await db.refresh(det_record)
        return det_record, animal_tag_id

    # ================================================================ #
    # ADI INTEGRATSIYA                                                   #
    # ================================================================ #

    async def _handle_adi_integration(
        self,
        db:        AsyncSession,
        animal_id: int,
    ) -> None:
        """
        Deteksiyadan keyin ADI bog'liq tekshiruvlar.

        NIMA QILADI:
            1. Jonivor "missing" alert ostida bo'lsa — avtomatik yopadi
               (chunki jonivor ko'rindi — muammo hal bo'ldi)
            2. Boshqa real vaqt triggerlar kelajakda qo'shiladi

        NIMA QILMAYDI:
            ADI ni hisoblmaydi — bu kunlik Celery task vazifasi.
            Har kadrda ADI hisoblash:
            - CPU intensive (30+ DB query)
            - Rate: 2 FPS × 24h = 172,800 hisoblash/kun — qabul qilib bo'lmaydi
        """
        alert_service = AlertService(db)

        # Missing alertlarni tekshirish va yopish
        missing_types = [
            AlertType.ANIMAL_MISSING.value,
            AlertType.ANIMAL_MISSING_LONG.value,
        ]

        stmt = select(Alert).where(
            Alert.animal_id   == animal_id,
            Alert.alert_type.in_(missing_types),
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
        )
        result = await db.execute(stmt)
        open_missing = result.scalars().all()

        if open_missing:
            # Jonivor qaytib ko'rindi — missing alertlarni yop
            for alert in open_missing:
                alert.resolve(
                    resolved_by="pipeline",
                    note=(
                        f"Jonivor kamerada aniqlandi: "
                        f"{self.camera.camera_id}. "
                        f"Avtomatik yopildi."
                    ),
                )
            await db.commit()
            self.stats.missing_resolved += len(open_missing)

            logger.info(
                f"Missing alerts resolved for animal {animal_id} | "
                f"camera={self.camera.camera_id} | "
                f"count={len(open_missing)}"
            )

    # ================================================================ #
    # WEBSOCKET BROADCAST                                                #
    # ================================================================ #

    async def _broadcast_detection(
        self,
        detection:     Detection,
        animal_id:     Optional[int],
        animal_tag_id: Optional[str],
    ) -> None:
        """
        Real vaqt yangilanishni WebSocket orqali yuborish.

        Payload frontend LiveFeed uchun optimallashtirilgan.
        Frontend LiveWeightUpdate formatiga mos keladi.
        """
        if not self.ws_manager:
            return

        # Bbox dan og'irlik taxminiy hisoblash (mvp formula)
        # w * h * konstantа — real model tayyor bo'lgunga qadar
        bbox = detection.bbox or {}
        w = bbox.get("w", 0.1)
        h = bbox.get("h", 0.2)
        estimated_weight_kg = round(
            max(50.0, min(800.0, (w * h * 4000) + 80)), 1
        )

        payload = {
            "type":                 "detection",
            "timestamp":            detection.timestamp.isoformat(),
            "camera_id":            detection.camera_id,
            "animal_id":            animal_id,
            "animal_tag_id":        animal_tag_id or "UNKNOWN",
            "class_name":           detection.class_name,
            "confidence":           round(detection.confidence, 3),
            "confidence_score":     round(detection.confidence, 3),
            "estimated_weight_kg":  estimated_weight_kg,
            "bbox":                 detection.bbox,
            "identified":           animal_id is not None,
            "pipeline_stats": {
                "fps":    self.stats.fps,
                "frames": self.stats.processed_frames,
            },
        }

        await self.ws_manager.broadcast(payload)