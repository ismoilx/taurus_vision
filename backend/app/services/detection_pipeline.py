"""
Automated Detection Pipeline — ADI integratsiyasi bilan.

PIPELINE FLOW:
    Camera Frame
        ↓
    YOLO Detection      (YOLODetection dataclass — .bounding_box)
        ↓
    Animal Identification (muzzle embedding)
        ↓
    Detection Log (DB)  (Detection ORM model — .bbox JSON dict)
        ↓
    ADI Trigger Check
        ↓
    Alert Check
        ↓
    WebSocket Broadcast

MUHIM FARQ:
    - YOLODetection (ai/base.py dataclass): .bounding_box (BoundingBox obj)
      → .bounding_box.x, .bounding_box.y, .bounding_box.width, .bounding_box.height
    - Detection (models/detection.py ORM): .bbox (JSON dict)
      → {"x": 0.5, "y": 0.6, "w": 0.3, "h": 0.4}
"""

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
from app.services.adi_service import ADIService
from typing import TYPE_CHECKING
if TYPE_CHECKING:
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
    """

    MIN_FRAME_INTERVAL = 0.5

    def __init__(
        self,
        camera_service: CameraServiceInterface,
        yolo_service:   YoloService,
        ws_manager:     Optional["ConnectionManager"] = None,  # noqa: F821
    ) -> None:
        self.camera     = camera_service
        self.yolo       = yolo_service
        self.ws_manager = ws_manager

        self._running = False
        self._task:   Optional[asyncio.Task] = None
        self.stats    = PipelineStats()

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
        logger.info(f"Pipeline stopped | stats={self.stats.to_dict()}")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        """Pipeline real vaqt statistikasini qaytaradi."""
        base = self.stats.to_dict()
        base["status"]    = "running" if self._running else "stopped"
        base["camera_id"] = self.camera.camera_id
        return base

    # ================================================================ #
    # MAIN LOOP                                                          #
    # ================================================================ #

    async def _run_loop(self) -> None:
        """Asosiy tsikl — kameradan kadr olib qayta ishlaydi."""
        last_frame_time = 0.0

        while self._running:
            try:
                now = time.monotonic()
                elapsed = now - last_frame_time
                if elapsed < self.MIN_FRAME_INTERVAL:
                    await asyncio.sleep(self.MIN_FRAME_INTERVAL - elapsed)

                frame = await self.camera.get_frame()
                self.stats.total_frames += 1

                if frame is None:
                    await asyncio.sleep(0.1)
                    continue

                last_frame_time = time.monotonic()
                await self._process_frame(frame)
                self.stats.processed_frames += 1

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"Pipeline loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    # ================================================================ #
    # FRAME PROCESSING                                                   #
    # ================================================================ #

    async def _process_frame(self, frame) -> None:
        """Bitta kadrni to'liq qayta ishlash."""
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

        async with AsyncSessionLocal() as db:
            for det in detections:
                await self._process_single_detection(
                    db=          db,
                    detection=   det,
                    frame=       frame,
                    inference_ms=inference_ms,
                )

    async def _process_single_detection(
        self,
        db:           AsyncSession,
        detection:    YOLODetection,
        frame,
        inference_ms: float,
    ) -> None:
        """Bitta YOLO detection ni qayta ishlash."""

        # STEP 2: Identifikatsiya
        # detection = YOLODetection dataclass → .bounding_box ishlatiladi
        t_identify = time.monotonic()
        animal_id: Optional[int] = None

        try:
            animal_id = await self._identify_animal(db, detection, frame)
            self.stats.total_identify_ms += (time.monotonic() - t_identify) * 1000

            if animal_id:
                self.stats.identified   += 1
                logger.info(
                    f"✓ Identified: animal_id={animal_id} | "
                    f"conf={detection.confidence:.2f}"
                )
            else:
                self.stats.unidentified += 1
                logger.debug(f"Unknown animal | conf={detection.confidence:.2f}")

        except Exception as e:
            logger.warning(f"Identification failed: {e}")
            self.stats.errors += 1

        # STEP 3: DB ga saqlash
        # _save_detection qaytargan detection = Detection ORM model → .bbox dict
        try:
            saved_detection, animal_tag_id = await self._save_detection(
                db=          db,
                detection=   detection,
                animal_id=   animal_id,
                inference_ms=inference_ms,
            )
            self.stats.db_writes += 1
        except Exception as e:
            logger.error(f"Detection save failed: {e}", exc_info=True)
            self.stats.errors += 1
            return

        # STEP 4: ADI / Alert tekshiruvi
        if animal_id:
            try:
                await self._handle_adi_integration(db, animal_id)
                self.stats.alert_checks += 1
            except Exception as e:
                logger.warning(f"ADI integration failed for animal {animal_id}: {e}")

        # STEP 5: WebSocket broadcast
        # saved_detection = Detection ORM model → .bbox dict ishlatiladi
        if self.ws_manager and saved_detection:
            try:
                await self._broadcast_detection(
                    detection=     saved_detection,
                    animal_id=     animal_id,
                    animal_tag_id= animal_tag_id,
                )
            except Exception as e:
                logger.warning(f"WebSocket broadcast failed: {e}")

        # STEP 6: MJPEG overlay uchun pipeline_manager ni yangilash
        if saved_detection and saved_detection.bbox:
            try:
                from app.services.pipeline_manager import get_pipeline_manager
                pm = get_pipeline_manager()
                pm.update_latest_detection(
                    camera_id=  self.camera.camera_id,
                    bbox=       saved_detection.bbox,
                    animal_tag= animal_tag_id,
                    confidence= saved_detection.confidence,
                    class_name= saved_detection.class_name or "animal",
                )
            except Exception:
                pass  # MJPEG overlay ixtiyoriy — xato pipeline ni to'xtatmaydi

    # ================================================================ #
    # IDENTIFICATION                                                     #
    # ================================================================ #

    async def _identify_animal(
        self,
        db:        AsyncSession,
        detection: YOLODetection,   # YOLODetection dataclass — .bounding_box
        frame,
    ) -> Optional[int]:
        """
        YOLO detection dan muzzle kesib olib, DB embeddinglar bilan taqqoslash.

        Args:
            detection: YOLODetection — .bounding_box.x/y/width/height
        """
        # YOLODetection.bounding_box — BoundingBox dataclass
        bb = detection.bounding_box
        muzzle_crop = extract_muzzle_region(
            frame.frame,
            bbox_x=bb.x,
            bbox_y=bb.y,
            bbox_w=bb.width,
            bbox_h=bb.height,
            normalized=True,
        )
        if muzzle_crop is None:
            logger.debug("Muzzle crop failed — skipping identification")
            return None

        id_service = IdentificationService(db)
        result = await id_service.identify_from_crop(muzzle_crop)

        return result.animal_id if result.is_identified else None

    # ================================================================ #
    # DB SAVE                                                           #
    # ================================================================ #

    async def _save_detection(
        self,
        db:           AsyncSession,
        detection:    YOLODetection,   # YOLODetection — .bounding_box
        animal_id:    Optional[int],
        inference_ms: float,
    ) -> tuple[Optional[Detection], Optional[str]]:
        """
        Detection + WeightMeasurement DB ga saqlash.

        Returns:
            (Detection ORM instance, animal tag_id yoki None)
        """
        now = datetime.utcnow()

        # YOLODetection.bounding_box → JSON dict sifatida saqlaymiz
        bb = detection.bounding_box
        bbox_dict = {
            "x": round(bb.x, 4),
            "y": round(bb.y, 4),
            "w": round(bb.width, 4),
            "h": round(bb.height, 4),
        }
        estimated_weight_kg = round(
            max(150.0, min(700.0,
                200.0 + (bb.width * bb.height * 1800)
            )), 1
        )

        # Detection ORM yozuvi
        det_record = Detection(
            animal_id=        animal_id,
            camera_id=        self.camera.camera_id,
            timestamp=        now,
            confidence=       round(detection.confidence, 4),
            class_id=         detection.class_id,
            class_name=       detection.class_name,
            bbox=             bbox_dict,
            estimated_weight= estimated_weight_kg,
            frame_number=     getattr(detection, "frame_number", None),
            inference_time_ms=round(inference_ms, 1),
        )
        db.add(det_record)

        # Animal + WeightMeasurement
        animal_tag_id: Optional[str] = None
        if animal_id:
            result = await db.execute(select(Animal).where(Animal.id == animal_id))
            animal = result.scalar_one_or_none()

            if animal:
                animal.mark_detected(now)
                animal_tag_id = animal.tag_id

                if detection.confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
                    db.add(WeightMeasurement(
                        animal_id=          animal_id,
                        timestamp=          now,
                        estimated_weight_kg=estimated_weight_kg,
                        confidence_score=   round(detection.confidence, 4),
                        camera_id=          self.camera.camera_id,
                        raw_ai_data={
                            "bbox":         bbox_dict,
                            "class_name":   detection.class_name,
                            "class_id":     detection.class_id,
                            "inference_ms": round(inference_ms, 1),
                            "source":       "yolo_pipeline",
                        },
                    ))
                    logger.debug(
                        f"WeightMeasurement | animal={animal_tag_id} | "
                        f"weight={estimated_weight_kg}kg"
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
        Deteksiyadan keyin:
        1. Missing alertlarni yopish
        2. Bugungi ADI ni hisoblash (yoki yangilash)
        """
        # 1. Missing alertlarni yopish
        missing_types = [
            AlertType.ANIMAL_MISSING.value,
            AlertType.ANIMAL_MISSING_LONG.value,
        ]

        stmt = select(Alert).where(
            Alert.animal_id   == animal_id,
            Alert.alert_type.in_(missing_types),
            Alert.status.in_([AlertStatus.OPEN, AlertStatus.SEEN]),
        )
        result      = await db.execute(stmt)
        open_alerts = result.scalars().all()

        if open_alerts:
            for alert in open_alerts:
                alert.resolve(
                    resolved_by="pipeline",
                    note=f"Jonivor kamerada aniqlandi: {self.camera.camera_id}.",
                )
            await db.commit()
            self.stats.missing_resolved += len(open_alerts)
            logger.info(
                f"Missing alerts resolved | animal_id={animal_id} | "
                f"count={len(open_alerts)}"
            )

        # 2. Bugungi ADI ni hisoblash
        try:
            adi_service = ADIService(db)
            await adi_service.calculate_for_animal(
                animal_id=animal_id,
                force_recalculate=True,
            )
            logger.debug(f"ADI updated after detection | animal_id={animal_id}")
        except Exception as e:
            logger.warning(f"ADI calculation after detection failed: {e}")

    # ================================================================ #
    # WEBSOCKET BROADCAST                                                #
    # ================================================================ #

    async def _broadcast_detection(
        self,
        detection:     Detection,       # Detection ORM model — .bbox JSON dict
        animal_id:     Optional[int],
        animal_tag_id: Optional[str],
    ) -> None:
        """
        Real vaqt yangilanishni WebSocket orqali yuborish.

        detection = Detection ORM model → .bbox {"x","y","w","h"} dict
        """
        if not self.ws_manager:
            return

        # ORM Detection.bbox — JSON dict {"x": 0.5, "y": 0.6, "w": 0.3, "h": 0.4}
        bbox = detection.bbox or {}
        w    = bbox.get("w", 0.1)
        h    = bbox.get("h", 0.2)
        estimated_weight_kg = round(
            max(150.0, min(700.0,
                200.0 + (w * h * 1800)
            )), 1
        )

        payload = {
            "type":                "detection",
            "timestamp":           detection.timestamp.isoformat(),
            "camera_id":           detection.camera_id,
            "animal_id":           animal_id,
            "animal_tag_id":       animal_tag_id or "UNKNOWN",
            "class_name":          detection.class_name,
            "confidence":          round(detection.confidence, 3),
            "confidence_score":    round(detection.confidence, 3),
            "estimated_weight_kg": estimated_weight_kg,
            "bbox":                bbox,
            "identified":          animal_id is not None,
            "pipeline_stats": {
                "fps":    self.stats.fps,
                "frames": self.stats.processed_frames,
            },
        }

        await self.ws_manager.broadcast(payload)