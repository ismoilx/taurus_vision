"""
Taurus Vision — Automated Detection Pipeline

PIPELINE FLOW (YANGILANGAN — Ikki bosqichli identifikatsiya):
    Camera Frame
        ↓
    YOLO26 Detection     → sigir/qo'y bbox lar (class 19/20)
        ↓
    FrameCollector       (Sprint 15-16) — training uchun kadrlar
        ↓
    Sigir cropini kesish  frame[y1:y2, x1:x2]
        ↓
    MuzzleDetector       (best.pt) — sigir crop ichida muzzle topadi
        ↓
    Muzzle cropini kesish crop_muzzle_from_animal()
        ↓
    MobileNetV2 embedding → cosine similarity → animal_id
        ↓
    Detection Log (DB)
        ↓
    ADI Trigger + Alert Check
        ↓
    WebSocket Broadcast

MUHIM FARQ (eski vs yangi):
    ESKI: extract_muzzle_region() heuristik — bbox pastki 45% ni oladi
    YANGI: MuzzleDetector (best.pt) — sigir cropida haqiqiy muzzleni topadi

    Bu o'zgarish identifikatsiya aniqligini sezilarli oshiradi chunki:
    1. Haqiqiy muzzle joylashuvi aniqlanadi (heuristik emas)
    2. Yonlamasiga turgan sigirlarda ham ishlaydi
    3. Qisman ko'rinadigan muzzle lar ham aniqlanadi

MUZZLE STRICT MODE:
    settings.MUZZLE_STRICT_MODE = True (default):
        Muzzle topilmasa → identifikatsiya o'tkazib yuboriladi.
        Natija: identification_service.identify_from_crop() chaqirilmaydi.
    settings.MUZZLE_STRICT_MODE = False:
        Muzzle topilmasa → eski heuristik (bbox pastki 45%) ishlatiladi.
        Bu legacy/fallback rejim.
"""

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.camera.base import CameraServiceInterface
from app.services.ai.yolo_service import YoloService
from app.services.ai.base import Detection as YOLODetection
from app.services.ai.frame_collector import get_frame_collector   # Sprint 15-16
from app.services.ai.muzzle_detector import (                     # YANGI
    get_muzzle_detector,
    crop_muzzle_from_animal,
)
from app.services.identification_service import IdentificationService
from app.services.alert_service import AlertService
from app.services.adi_service import ADIService
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.api.v1.websocket import ConnectionManager
from app.services.ai.cattle_tracker import CattleTracker
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
        self.frames_collected:   int   = 0   # Sprint 15-16: yig'ilgan kadrlar

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
            "uptime_seconds":   round(self.uptime_seconds, 1),
            "total_frames":     self.total_frames,
            "processed_frames": self.processed_frames,
            "yolo_detections":  self.yolo_detections,
            "identified":       self.identified,
            "unidentified":     self.unidentified,
            "db_writes":        self.db_writes,
            "alert_checks":     self.alert_checks,
            "missing_resolved": self.missing_resolved,
            "errors":           self.errors,
            "fps":              self.fps,
            "avg_inference_ms": self.avg_inference_ms,
            "frames_collected": self.frames_collected,   # Sprint 15-16
        }


# ------------------------------------------------------------------ #
# Detection Pipeline                                                   #
# ------------------------------------------------------------------ #

class DetectionPipeline:
    """
    Asosiy detection pipeline.

    Camera → YOLO → FrameCollect → Identify → DB → Alert Check → WebSocket

    RESILIENCE:
        - Bitta frame xatosi pipeline ni to'xtatmaydi
        - Har bir bosqich mustaqil try/except bilan o'ralgan
        - Xatolar logga yoziladi va statistikaga qo'shiladi

    SPRINT 15-16 QO'SHIMCHA:
        FrameCollector integratsiyasi — har N YOLO detectiondan bir kadrni
        training dataset uchun saqlaydi. ThreadPoolExecutor orqali
        event loop bloklanmaydi.
    """

    MIN_FRAME_INTERVAL = 0.5

    def __init__(
        self,
        camera_service:  CameraServiceInterface,
        yolo_service:    YoloService,
        ws_manager:      Optional["ConnectionManager"] = None,
        frame_cache_cb = None,
    ) -> None:
        self.camera          = camera_service
        self.yolo            = yolo_service
        self.ws_manager      = ws_manager
        self._frame_cache_cb = frame_cache_cb

        self._running = False
        self._task:   Optional[asyncio.Task] = None
        self.stats    = PipelineStats()

        # ── Multi-Object Tracker ─────────────────────────────────────
        # Har kamera uchun alohida tracker instansi.
        # Kalman filter + Hungarian algorithm + dual identification.
        self._tracker = CattleTracker()

        # Sprint 15-16: disk I/O uchun alohida thread pool
        self._io_executor = ThreadPoolExecutor(
            max_workers        = 1,
            thread_name_prefix = "frame_collector",
        )

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

        # Sprint 15-16: I/O thread pool ni to'xtatish
        self._io_executor.shutdown(wait=False)

        await self.camera.stop()
        self._tracker.reset()
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
                now     = time.monotonic()
                elapsed = now - last_frame_time
                if elapsed < self.MIN_FRAME_INTERVAL:
                    await asyncio.sleep(self.MIN_FRAME_INTERVAL - elapsed)

                frame = await self.camera.get_frame()
                self.stats.total_frames += 1

                if frame is None:
                    await asyncio.sleep(0.1)
                    continue

                # MJPEG stream uchun oxirgi frameni cache ga saqlash
                if self._frame_cache_cb is not None:
                    try:
                        self._frame_cache_cb(self.camera.camera_id, frame.frame)
                    except Exception:
                        pass

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
            detections       = inference_result.detections
        except Exception as e:
            logger.error(f"YOLO inference failed: {e}")
            self.stats.errors += 1
            return

        inference_ms                  = (time.monotonic() - t0) * 1000
        self.stats.total_inference_ms += inference_ms
        self.stats.yolo_detections    += len(detections)

        if not detections:
            return

        # ── Sprint 15-16: Training kadrlarini yig'ish ─────────────────────
        await self._collect_training_frame(frame.frame, detections)

        # ── TRACKER: Kalman + Hungarian + Dual Identification ─────────────
        # Har kadrda detectionlarni trackerlarga ulash.
        # Tracker ichida: predict → associate → update → identification urinish
        async with AsyncSessionLocal() as db:
            active_tracks = await self._tracker.update(
                detections=detections,
                frame=frame.frame,
                db=db,
            )

            # Har bir aktiv track uchun DB yozuv va WebSocket broadcast
            for track in active_tracks:
                # Faqat tasdiqlangan tracklar uchun DB ga yozamiz
                # (TENTATIVE tracklar hali tasdiqlanmagan — DB ni to'ldirmaymiz)
                if track.state.value in ("unidentified", "identified"):
                    try:
                        saved_det, _ = await self._save_detection_from_track(
                            db=db,
                            track=track,
                            inference_ms=inference_ms,
                        )
                        self.stats.db_writes += 1

                        if track.animal_id:
                            self.stats.identified   += 1
                            await self._handle_adi_integration(db, track.animal_id)
                            self.stats.alert_checks += 1
                        else:
                            self.stats.unidentified += 1

                    except Exception as e:
                        logger.error(f"Track save failed T#{track.track_id}: {e}")
                        self.stats.errors += 1

            # WebSocket broadcast — barcha aktiv tracklar (TENTATIVE ham)
            if self.ws_manager and active_tracks:
                try:
                    await self._broadcast_tracks(active_tracks)
                except Exception as e:
                    logger.warning(f"WebSocket broadcast failed: {e}")

            # Pipeline manager overlay yangilash (MJPEG stream uchun)
            if active_tracks:
                try:
                    from app.services.pipeline_manager import get_pipeline_manager
                    pm = get_pipeline_manager()
                    for track in active_tracks:
                        bbox = track.kalman.bbox
                        pm.update_latest_detection(
                            camera_id  = self.camera.camera_id,
                            bbox       = {
                                "x": float(bbox[0]),
                                "y": float(bbox[1]),
                                "w": float(bbox[2]),
                                "h": float(bbox[3]),
                            },
                            animal_tag = track.tag_id or f"T#{track.track_id}",
                            confidence = track.detection_confidence,
                            class_name = "cow",
                        )
                except Exception:
                    pass

        # Tracker stats ni pipeline stats ga qo'shish
        tracker_stats = self._tracker.get_stats()
        self.stats.identified   = tracker_stats["total_identifications"]

    async def _collect_training_frame(
        self,
        frame:      "np.ndarray",
        detections: list[YOLODetection],
    ) -> None:
        """
        Sprint 15-16: FrameCollector ga kadr yuborish.

        Non-blocking — ThreadPoolExecutor orqali bajariladi.
        Collector None bo'lsa — hech narsa qilinmaydi.
        """
        collector = get_frame_collector()
        if collector is None:
            return

        try:
            loop = asyncio.get_event_loop()
            saved = await loop.run_in_executor(
                self._io_executor,
                collector.maybe_save,
                frame,
                self.camera.camera_id,
                detections,
            )
            if saved:
                self.stats.frames_collected += 1
        except Exception as exc:
            # Kadr yig'ish xatosi pipeline ni to'xtatmasin
            logger.debug(f"[pipeline] Frame collection warning: {exc}")

    async def _process_single_detection(
        self,
        db:           AsyncSession,
        detection:    YOLODetection,
        frame,
        inference_ms: float,
    ) -> None:
        """Bitta YOLO detection ni qayta ishlash."""

        # STEP 1: Identifikatsiya
        t_identify = time.monotonic()
        animal_id: Optional[int] = None

        try:
            animal_id = await self._identify_animal(db, detection, frame)
            self.stats.total_identify_ms += (time.monotonic() - t_identify) * 1000

            if animal_id:
                self.stats.identified   += 1
            else:
                self.stats.unidentified += 1

        except Exception as e:
            logger.warning(f"Identification failed: {e}")
            self.stats.errors += 1

        # STEP 2: DB ga saqlash
        try:
            saved_detection, animal_tag_id = await self._save_detection(
                db           = db,
                detection    = detection,
                animal_id    = animal_id,
                inference_ms = inference_ms,
            )
            self.stats.db_writes += 1
        except Exception as e:
            logger.error(f"Detection save failed: {e}", exc_info=True)
            self.stats.errors += 1
            return

        # STEP 3: ADI / Alert tekshiruvi
        if animal_id:
            try:
                await self._handle_adi_integration(db, animal_id)
                self.stats.alert_checks += 1
            except Exception as e:
                logger.warning(f"ADI integration failed for animal {animal_id}: {e}")

        # STEP 4: WebSocket broadcast
        if self.ws_manager and saved_detection:
            try:
                await self._broadcast_detection(
                    detection     = saved_detection,
                    animal_id     = animal_id,
                    animal_tag_id = animal_tag_id,
                )
            except Exception as e:
                logger.warning(f"WebSocket broadcast failed: {e}")

        # STEP 5: MJPEG overlay uchun pipeline_manager ni yangilash
        if saved_detection and saved_detection.bbox:
            try:
                from app.services.pipeline_manager import get_pipeline_manager
                pm = get_pipeline_manager()
                pm.update_latest_detection(
                    camera_id  = self.camera.camera_id,
                    bbox       = saved_detection.bbox,
                    animal_tag = animal_tag_id,
                    confidence = saved_detection.confidence,
                    class_name = saved_detection.class_name or "animal",
                )
            except Exception:
                pass

    async def _save_detection_from_track(
        self,
        db,
        track,           # CattleTrack
        inference_ms: float,
    ) -> tuple:
        """
        CattleTrack dan Detection DB yozuvi yaratish.

        _save_detection dan farqi: track_id ham saqlanadi,
        bbox Kalman filtered pozitsiyadan olinadi.
        """
        from app.services.ai.cattle_tracker import CattleTrack
        import json

        now  = datetime.utcnow()
        bbox = track.kalman.bbox   # [cx, cy, w, h] normalized

        bbox_dict = {
            "x": round(float(bbox[0]), 4),
            "y": round(float(bbox[1]), 4),
            "w": round(float(bbox[2]), 4),
            "h": round(float(bbox[3]), 4),
        }

        estimated_weight_kg = round(
            max(150.0, min(700.0, 200.0 + (bbox[2] * bbox[3] * 1800))), 1
        )

        det_record = Detection(
            animal_id         = track.animal_id,
            camera_id         = self.camera.camera_id,
            timestamp         = now,
            confidence        = round(track.detection_confidence, 4),
            class_id          = 19,   # COCO: cow
            class_name        = "cow",
            bbox              = bbox_dict,
            estimated_weight  = estimated_weight_kg,
            inference_time_ms = round(inference_ms, 1),
        )
        db.add(det_record)

        if track.animal_id:
            result = await db.execute(
                select(Animal).where(Animal.id == track.animal_id)
            )
            animal = result.scalar_one_or_none()
            if animal:
                animal.mark_detected(now)

                if track.detection_confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
                    db.add(WeightMeasurement(
                        animal_id           = track.animal_id,
                        timestamp           = now,
                        estimated_weight_kg = estimated_weight_kg,
                        confidence_score    = round(track.detection_confidence, 4),
                        camera_id           = self.camera.camera_id,
                        raw_ai_data         = {
                            "track_id":     track.track_id,
                            "id_score":     round(track.id_score, 4),
                            "bbox":         bbox_dict,
                            "source":       "cattle_tracker",
                        },
                    ))

        await db.commit()
        await db.refresh(det_record)
        return det_record, track.tag_id

    async def _broadcast_tracks(self, active_tracks: list) -> None:
        """
        Barcha aktiv tracklar uchun WebSocket broadcast.

        Har track:
          - track_id (vaqtincha ID)
          - state: tentative | unidentified | identified
          - bbox_color: orange | red | green
          - animal_id, tag_id (faqat IDENTIFIED da)
        """
        import json

        message = json.dumps({
            "type":   "tracked_detections",
            "camera": self.camera.camera_id,
            "tracks": [t.to_websocket_dict() for t in active_tracks],
            "stats":  self._tracker.get_stats(),
        })
        await self.ws_manager.broadcast(message)

    # ================================================================ #
    # IDENTIFICATION (eski — tracker ishlatiladi, bu legacy)            #
    # ================================================================ #

    async def _identify_animal(
        self,
        db:        AsyncSession,
        detection: YOLODetection,
        frame,
    ) -> Optional[int]:
        """
        Ikki bosqichli identifikatsiya:
            1. Sigir cropini kesish (YOLO26 bbox dan)
            2. MuzzleDetector (best.pt) → muzzle bbox topish
            3. Muzzle cropini kesish
            4. MobileNetV2 → embedding → cosine similarity → animal_id

        STRICT MODE (settings.MUZZLE_STRICT_MODE = True):
            Muzzle topilmasa → None qaytaradi (identifikatsiya o'tkazib yuboriladi).
        LEGACY MODE (settings.MUZZLE_STRICT_MODE = False):
            Muzzle topilmasa → eski heuristik (bbox pastki 45%) ishlatiladi.

        Args:
            detection: YOLODetection — .bounding_box.x/y/width/height (normalized)
                       .extra_data['absolute_box'] — pixel koordinatalar
            frame:     CameraFrame — .frame (BGR numpy array)

        Returns:
            animal_id (int) yoki None.
        """
        bb     = detection.bounding_box
        img    = frame.frame
        img_h, img_w = img.shape[:2]

        # --- STEP 1: Sigir cropini kesish ---
        # YOLODetection.bounding_box: center_x, center_y, width, height (normalized)
        abs_cx = bb.x * img_w
        abs_cy = bb.y * img_h
        abs_w  = bb.width  * img_w
        abs_h  = bb.height * img_h

        animal_x1 = max(0, int(abs_cx - abs_w / 2))
        animal_y1 = max(0, int(abs_cy - abs_h / 2))
        animal_x2 = min(img_w, int(abs_cx + abs_w / 2))
        animal_y2 = min(img_h, int(abs_cy + abs_h / 2))

        if (animal_x2 - animal_x1) < 32 or (animal_y2 - animal_y1) < 32:
            logger.debug("Sigir crop juda kichik — identifikatsiya o'tkazib yuborildi")
            return None

        animal_crop = img[animal_y1:animal_y2, animal_x1:animal_x2]

        if animal_crop.size == 0:
            logger.debug("Bo'sh sigir crop — identifikatsiya o'tkazib yuborildi")
            return None

        # --- STEP 2: MuzzleDetector bilan muzzleni aniqlash ---
        muzzle_crop: Optional[np.ndarray] = None

        try:
            muzzle_detector = get_muzzle_detector()
            muzzle_det = await muzzle_detector.detect_muzzle(animal_crop)

            if muzzle_det is not None:
                # --- STEP 3: Muzzle cropini kesish ---
                muzzle_crop = crop_muzzle_from_animal(animal_crop, muzzle_det)
                if muzzle_crop is None:
                    logger.debug("crop_muzzle_from_animal None qaytardi")

        except RuntimeError as exc:
            # MuzzleDetector yuklanmagan (startup xatosi)
            logger.warning(f"MuzzleDetector unavailable: {exc}")
        except Exception as exc:
            logger.warning(f"MuzzleDetector xatosi: {exc}")

        # --- STRICT MODE: muzzle topilmasa ---
        if muzzle_crop is None:
            if settings.MUZZLE_STRICT_MODE:
                logger.debug(
                    "Muzzle topilmadi — strict mode, identifikatsiya o'tkazib yuborildi"
                )
                return None
            else:
                # Legacy fallback: eski heuristik extract_muzzle_region()
                logger.debug(
                    "Muzzle topilmadi — legacy fallback (heuristik) ishlatilmoqda"
                )
                muzzle_crop = extract_muzzle_region(
                    img,
                    bbox_x     = bb.x,
                    bbox_y     = bb.y,
                    bbox_w     = bb.width,
                    bbox_h     = bb.height,
                    normalized = True,
                )
                if muzzle_crop is None:
                    return None

        # --- STEP 4: MobileNetV2 → embedding → identifikatsiya ---
        id_service = IdentificationService(db)
        result     = await id_service.identify_from_crop(muzzle_crop)
        return result.animal_id if result.is_identified else None

    # ================================================================ #
    # DB SAVE                                                            #
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

        Returns:
            (Detection ORM instance, animal tag_id yoki None)
        """
        now = datetime.utcnow()

        bb        = detection.bounding_box
        bbox_dict = {
            "x": round(bb.x,      4),
            "y": round(bb.y,      4),
            "w": round(bb.width,  4),
            "h": round(bb.height, 4),
        }
        estimated_weight_kg = round(
            max(150.0, min(700.0,
                200.0 + (bb.width * bb.height * 1800)
            )), 1
        )

        det_record = Detection(
            animal_id         = animal_id,
            camera_id         = self.camera.camera_id,
            timestamp         = now,
            confidence        = round(detection.confidence, 4),
            class_id          = detection.class_id,
            class_name        = detection.class_name,
            bbox              = bbox_dict,
            estimated_weight  = estimated_weight_kg,
            frame_number      = getattr(detection, "frame_number", None),
            inference_time_ms = round(inference_ms, 1),
        )
        db.add(det_record)

        animal_tag_id: Optional[str] = None
        if animal_id:
            result = await db.execute(select(Animal).where(Animal.id == animal_id))
            animal = result.scalar_one_or_none()

            if animal:
                animal.mark_detected(now)
                animal_tag_id = animal.tag_id

                if detection.confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
                    db.add(WeightMeasurement(
                        animal_id           = animal_id,
                        timestamp           = now,
                        estimated_weight_kg = estimated_weight_kg,
                        confidence_score    = round(detection.confidence, 4),
                        camera_id           = self.camera.camera_id,
                        raw_ai_data         = {
                            "bbox":         bbox_dict,
                            "class_name":   detection.class_name,
                            "class_id":     detection.class_id,
                            "inference_ms": round(inference_ms, 1),
                            "source":       "yolo_pipeline",
                        },
                    ))

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
        missing_types = [
            AlertType.ANIMAL_MISSING.value,
            AlertType.ANIMAL_MISSING_LONG.value,
        ]

        open_missing = await db.execute(
            select(Alert).where(
                Alert.animal_id  == animal_id,
                Alert.alert_type.in_(missing_types),
                Alert.status.in_(["open", "seen"]),
            )
        )
        for alert in open_missing.scalars().all():
            alert.status      = AlertStatus.RESOLVED
            alert.resolved_at = datetime.utcnow()
            alert.resolved_by = "system_detection"
            alert.resolution_note = "Jonivor kamerada yana ko'rindi"
            self.stats.missing_resolved += 1

        await db.commit()

    # ================================================================ #
    # WEBSOCKET BROADCAST                                                #
    # ================================================================ #

    async def _broadcast_detection(
        self,
        detection:     Detection,
        animal_id:     Optional[int],
        animal_tag_id: Optional[str],
    ) -> None:
        """Detection ma'lumotlarini WebSocket orqali broadcast qilish."""
        import json

        message = json.dumps({
            "type":       "detection",
            "data": {
                "detection_id": detection.id,
                "camera_id":    detection.camera_id,
                "animal_id":    animal_id,
                "animal_tag":   animal_tag_id,
                "confidence":   detection.confidence,
                "class_name":   detection.class_name,
                "bbox":         detection.bbox,
                "timestamp":    detection.timestamp.isoformat(),
            },
        })
        await self.ws_manager.broadcast(message)