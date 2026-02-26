"""
Taurus Vision — Multi-Camera Pipeline Manager

Bir vaqtda bir nechta kamera pipelinelarini boshqaradi.

ARXITEKTURA:
    - Har bir kamera uchun alohida DetectionPipeline instance
    - asyncio.Task orqali parallel ishlash
    - Thread-safe dict orqali pipelinelar saqlanadi
    - Singleton pattern — butun dastur bo'ylab bitta instance

PIPELINE LIFECYCLE:
    start_camera(camera_id) → kamera DB dan olinadi
                            → SimulatedCamera/RTSP yaratiladi
                            → DetectionPipeline ishga tushiriladi
                            → Task saqlanadi

    stop_camera(camera_id)  → Task bekor qilinadi
                            → Pipeline to'xtatiladi
                            → Dict dan o'chiriladi

    stop_all()              → Barcha pipelinelar to'xtatiladi

STATUS:
    get_status(camera_id) → {running, stats, camera_id}
    get_all_status()      → {camera_id: status, ...}
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from app.services.detection_pipeline import DetectionPipeline
from app.services.camera.simulated_camera import SimulatedCameraService
from app.services.camera.camera_factory import CameraFactory
from app.services.ai.yolo_service import get_yolo_service
from app.api.v1.websocket import get_ws_manager

logger = logging.getLogger(__name__)


@dataclass
class PipelineEntry:
    """
    Bitta kamera pipelini uchun ma'lumotlar.
    
    Fields:
        camera_id: Kamera identifikatori
        pipeline:  DetectionPipeline instance
        task:      asyncio.Task (pipeline._run_loop())
        started_at: Ishga tushirilgan vaqt
    """
    camera_id:  str
    pipeline:   DetectionPipeline
    task:       Optional[asyncio.Task]  = None
    started_at: datetime               = field(default_factory=lambda: datetime.now(timezone.utc))


class PipelineManager:
    """
    Barcha kamera pipelinelarini markaziy boshqarish.

    FOYDALANISH:
        manager = get_pipeline_manager()

        # Kamera ishga tushirish
        await manager.start_camera("CAM-TEST-KAMERA", camera_config)

        # Holat tekshirish
        status = manager.get_status("CAM-TEST-KAMERA")

        # To'xtatish
        await manager.stop_camera("CAM-TEST-KAMERA")
    """

    _instance: Optional["PipelineManager"] = None

    def __new__(cls) -> "PipelineManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            # camera_id → PipelineEntry
            self._pipelines: dict[str, PipelineEntry] = {}
            self._initialized = True
            logger.info("PipelineManager initialized")

    # ================================================================ #
    # START                                                              #
    # ================================================================ #

    async def start_camera(
        self,
        camera_id:    str,
        camera_type:  str  = "simulated",
        source:       Optional[str] = None,
        device_index: Optional[int] = None,
        fps:          int  = 10,
        skip_frames:  int  = 3,
    ) -> bool:
        """
        Kamera uchun detection pipeline ishga tushiradi.

        Agar kamera allaqachon ishlayotgan bo'lsa — False qaytaradi.

        Args:
            camera_id:    DB dagi kamera identifikatori
            camera_type:  'simulated' | 'usb' | 'rtsp'
            source:       RTSP URL
            device_index: USB device indeksi
            fps:          Kamera FPS
            skip_frames:  Har N-chi kadrni qayta ishlash

        Returns:
            True — muvaffaqiyatli ishga tushirildi
            False — allaqachon ishlayapti yoki xatolik
        """
        if self.is_running(camera_id):
            logger.warning(f"Pipeline {camera_id} allaqachon ishlayapti")
            return False

        try:
            # 1. Kamera servisini yaratish
            camera_service = self._create_camera_service(
                camera_id    = camera_id,
                camera_type  = camera_type,
                source       = source,
                device_index = device_index,
                fps          = fps,
            )

            # 2. WebSocket manager
            try:
                ws_manager = get_ws_manager()
            except RuntimeError:
                ws_manager = None
                logger.warning(f"[{camera_id}] WebSocket manager yo'q")

            # 3. Pipeline yaratish
            yolo = get_yolo_service()
            pipeline = DetectionPipeline(
                camera_service = camera_service,
                yolo_service   = yolo,
                ws_manager     = ws_manager,
            )

            # skip_frames ni MIN_FRAME_INTERVAL ga aylantirish
            if skip_frames > 0 and fps > 0:
                pipeline.MIN_FRAME_INTERVAL = skip_frames / fps

            # 4. Pipeline ni ishga tushirish (task sifatida)
            await camera_service.initialize()
            pipeline._running = True
            pipeline.stats.reset()
            pipeline.stats.started_at = datetime.now(timezone.utc)
            await camera_service.start()

            task = asyncio.create_task(
                pipeline._run_loop(),
                name=f"pipeline-{camera_id}",
            )

            self._pipelines[camera_id] = PipelineEntry(
                camera_id = camera_id,
                pipeline  = pipeline,
                task      = task,
            )

            logger.info(
                f"Pipeline ishga tushirildi",
                extra={"extra_data": {
                    "camera_id":   camera_id,
                    "camera_type": camera_type,
                    "fps":         fps,
                    "skip_frames": skip_frames,
                }},
            )
            return True

        except Exception as exc:
            logger.error(
                f"Pipeline ishga tushirishda xato",
                extra={"extra_data": {
                    "camera_id": camera_id,
                    "error":     str(exc),
                }},
                exc_info=True,
            )
            # Agar yartim ishga tushgan bo'lsa — tozalaymiz
            if camera_id in self._pipelines:
                del self._pipelines[camera_id]
            return False

    # ================================================================ #
    # STOP                                                               #
    # ================================================================ #

    async def stop_camera(self, camera_id: str) -> bool:
        """
        Bitta kamera pipelineni to'xtatadi.

        Args:
            camera_id: To'xtatilishi kerak bo'lgan kamera

        Returns:
            True — muvaffaqiyatli to'xtatildi
            False — kamera topilmadi yoki xatolik
        """
        entry = self._pipelines.get(camera_id)
        if entry is None:
            logger.warning(f"Pipeline {camera_id} topilmadi")
            return False

        try:
            # Task ni bekor qilish
            if entry.task and not entry.task.done():
                entry.task.cancel()
                try:
                    await asyncio.wait_for(entry.task, timeout=5.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # Pipeline va kamerani to'xtatish
            entry.pipeline._running = False
            await entry.pipeline.camera.stop()

            del self._pipelines[camera_id]

            logger.info(
                "Pipeline to'xtatildi",
                extra={"extra_data": {"camera_id": camera_id}},
            )
            return True

        except Exception as exc:
            logger.error(
                "Pipeline to'xtatishda xato",
                extra={"extra_data": {
                    "camera_id": camera_id,
                    "error":     str(exc),
                }},
            )
            # Har holda dict dan o'chiramiz
            self._pipelines.pop(camera_id, None)
            return False

    async def stop_all(self) -> int:
        """
        Barcha pipelinelarni to'xtatadi.

        Returns:
            To'xtatilgan pipelinelar soni
        """
        camera_ids = list(self._pipelines.keys())
        stopped = 0

        for camera_id in camera_ids:
            if await self.stop_camera(camera_id):
                stopped += 1

        logger.info(
            "Barcha pipelinelar to'xtatildi",
            extra={"extra_data": {
                "total":   len(camera_ids),
                "stopped": stopped,
            }},
        )
        return stopped

    # ================================================================ #
    # STATUS                                                             #
    # ================================================================ #

    def is_running(self, camera_id: str) -> bool:
        """Kamera pipelini ishlayaptimi?"""
        entry = self._pipelines.get(camera_id)
        if entry is None:
            return False
        # Task tugagan bo'lsa — pipeline to'xtagan
        if entry.task and entry.task.done():
            self._pipelines.pop(camera_id, None)
            return False
        return entry.pipeline.is_running

    def get_status(self, camera_id: str) -> dict:
        """
        Bitta kamera pipeline holati.

        Returns:
            {
                "camera_id": "CAM-...",
                "running": True/False,
                "stats": {...} | None,
                "started_at": "ISO string" | None,
            }
        """
        entry = self._pipelines.get(camera_id)

        if entry is None or not self.is_running(camera_id):
            return {
                "camera_id":  camera_id,
                "running":    False,
                "stats":      None,
                "started_at": None,
            }

        return {
            "camera_id":  camera_id,
            "running":    True,
            "stats":      entry.pipeline.get_stats(),
            "started_at": entry.started_at.isoformat(),
        }

    def get_all_status(self) -> dict[str, dict]:
        """
        Barcha pipelinelar holati.

        Returns:
            Dict[camera_id, status_dict]
        """
        # Tugagan tasklarni tozalash
        dead = [
            cid for cid, e in self._pipelines.items()
            if e.task and e.task.done()
        ]
        for cid in dead:
            self._pipelines.pop(cid, None)

        return {
            cid: self.get_status(cid)
            for cid in self._pipelines
        }

    def list_running(self) -> list[str]:
        """Hozir ishlayotgan kameralar ro'yxati."""
        return [
            cid for cid in list(self._pipelines.keys())
            if self.is_running(cid)
        ]

    def total_running(self) -> int:
        """Ishlayotgan pipelinelar soni."""
        return len(self.list_running())

    # ================================================================ #
    # INTERNAL                                                           #
    # ================================================================ #

    def _create_camera_service(
        self,
        camera_id:    str,
        camera_type:  str,
        source:       Optional[str],
        device_index: Optional[int],
        fps:          int,
    ) -> SimulatedCameraService:
        """
        Kamera turi bo'yicha camera service yaratadi.

        Hozir: simulated va rtsp (rtsp → simulated fallback)
        Kelajak: real RTSP, USB kameralar
        """
        if camera_type == "simulated":
            return SimulatedCameraService(
                camera_id  = camera_id,
                fps        = fps,
                resolution = (1280, 720),
                mode       = "random",
            )

        elif camera_type == "rtsp" and source:
            # RTSP mavjud bo'lsa CameraFactory ishlatamiz
            config = {
                "camera_id": camera_id,
                "type":      "rtsp",
                "url":       source,
                "fps":       fps,
            }
            # CameraFactory RTSP qo'llab-quvvatlamasa — simulated fallback
            try:
                cam = CameraFactory.create_camera(config)
                if cam is not None:
                    # CameraFactory CameraInterface qaytaradi
                    # Uni SimulatedCameraService ga o'rash kerak bo'ladi
                    # Hozircha simulated bilan almashtirish:
                    logger.warning(
                        f"RTSP kamera hozircha simulated bilan almashtirilyapti: {camera_id}"
                    )
            except Exception:
                pass

            return SimulatedCameraService(
                camera_id  = camera_id,
                fps        = fps,
                resolution = (1280, 720),
                mode       = "random",
            )

        elif camera_type == "usb":
            # USB hozircha simulated sifatida ishlaydi
            logger.warning(f"USB kamera simulated bilan almashtirilyapti: {camera_id}")
            return SimulatedCameraService(
                camera_id  = camera_id,
                fps        = fps,
                resolution = (1280, 720),
                mode       = "random",
            )

        else:
            # Default — simulated
            return SimulatedCameraService(
                camera_id  = camera_id,
                fps        = fps,
                resolution = (1280, 720),
                mode       = "random",
            )


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================

_pipeline_manager: Optional[PipelineManager] = None


def get_pipeline_manager() -> PipelineManager:
    """
    Global PipelineManager instance ni qaytaradi.

    Singleton — dastur bo'ylab bitta instance.
    """
    global _pipeline_manager
    if _pipeline_manager is None:
        _pipeline_manager = PipelineManager()
    return _pipeline_manager