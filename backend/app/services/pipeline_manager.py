"""
Taurus Vision — Multi-Camera Pipeline Manager (Sprint 9-10)

Bir vaqtda bir nechta kamera pipelinelarini boshqaradi.

ARXITEKTURA:
    PipelineManager (Singleton)
        ├── StreamOptimizer    — Adaptiv kadr skip, CPU pressure monitoring
        ├── LoadBalancer       — Pipelinelar soni va resurs cheklovi
        ├── HealthWatchdog     — Crashed pipeline larni avtomatik restart qilish
        └── PipelineEntry[]   — Har bir kamera uchun

STREAM OPTIMIZATION:
    StreamOptimizer har 10 soniyada CPU/Memory yukini o'lchaydi:
    - CPU < 60% → skip_frames = 2  (tez qayta ishlash)
    - CPU 60-80% → skip_frames = 4 (o'rtacha)
    - CPU > 80% → skip_frames = 8  (tejamkor)

LOAD BALANCING:
    max_pipelines = min(cpu_cores * 2, ram_total_mb / 400, 16)
    RAM cheklov: 400MB/pipeline (YOLO model + buffer uchun)

HEALTH WATCHDOG:
    Har 30 soniyada barcha pipelinelarni tekshiradi:
    - Task crashed? → Qayta ishga tushiradi (max 3 urinish)
    - FPS 0 > 60s? → Kamerani restart qiladi
"""

import asyncio
import logging
import time
import psutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from app.services.camera.simulated_camera import SimulatedCameraService
from app.services.camera.base import CameraServiceInterface
from app.services.ai.yolo_service import get_yolo_service

logger = logging.getLogger(__name__)

# ============================================================================
# KONSTANTALAR
# ============================================================================

_RAM_PER_PIPELINE_MB: int  = 400
_CPU_LOW:  float = 60.0
_CPU_HIGH: float = 80.0
_SKIP_LOW:  int = 2
_SKIP_MID:  int = 4
_SKIP_HIGH: int = 8
_WATCHDOG_INTERVAL:      float = 30.0
_MAX_RESTART_ATTEMPTS:   int   = 3
_ZERO_FPS_THRESHOLD:     float = 60.0


# ============================================================================
# STREAM OPTIMIZER
# ============================================================================

class StreamOptimizer:
    """CPU/RAM yukiga qarab kadr skip ni adaptiv boshqaradi."""

    _CHECK_INTERVAL: float = 10.0

    def __init__(self) -> None:
        self._current_skip: int        = _SKIP_LOW
        self._last_check:   float      = 0.0
        self._cpu_history:  list[float] = []

    def get_skip_frames(self) -> int:
        now = time.monotonic()
        if now - self._last_check < self._CHECK_INTERVAL:
            return self._current_skip

        self._last_check = now

        try:
            cpu          = psutil.cpu_percent(interval=None)
            ram          = psutil.virtual_memory()
            ram_used_pct = ram.percent

            self._cpu_history.append(cpu)
            if len(self._cpu_history) > 6:
                self._cpu_history.pop(0)

            avg_cpu  = sum(self._cpu_history) / len(self._cpu_history)
            pressure = max(avg_cpu, ram_used_pct)

            if pressure < _CPU_LOW:
                self._current_skip = _SKIP_LOW
            elif pressure < _CPU_HIGH:
                self._current_skip = _SKIP_MID
            else:
                self._current_skip = _SKIP_HIGH

            logger.debug(
                "StreamOptimizer update",
                extra={"extra_data": {
                    "avg_cpu":     round(avg_cpu, 1),
                    "ram_pct":     round(ram_used_pct, 1),
                    "skip_frames": self._current_skip,
                }},
            )

        except Exception as exc:
            logger.warning(f"StreamOptimizer CPU check failed: {exc}")

        return self._current_skip


# ============================================================================
# LOAD BALANCER
# ============================================================================

class LoadBalancer:
    """Bir vaqtda ishlaydigan pipelinelar sonini cheklaydi."""

    def __init__(self) -> None:
        self._max_pipelines = self._compute_max_pipelines()
        logger.info(
            "LoadBalancer initialized",
            extra={"extra_data": {"max_pipelines": self._max_pipelines}},
        )

    @property
    def max_pipelines(self) -> int:
        return self._max_pipelines

    def can_start(self, current_count: int) -> tuple[bool, str]:
        if current_count >= self._max_pipelines:
            return False, (
                f"Maksimal pipeline soni ({self._max_pipelines}) ga yetildi. "
                f"Avval mavjud pipelinelardan birini to'xtating."
            )

        ram              = psutil.virtual_memory()
        available_mb     = ram.available / (1024 * 1024)

        if available_mb < _RAM_PER_PIPELINE_MB:
            return False, (
                f"Yetarli RAM yo'q. Mavjud: {available_mb:.0f}MB, "
                f"Kerak: {_RAM_PER_PIPELINE_MB}MB."
            )

        return True, ""

    @staticmethod
    def _compute_max_pipelines() -> int:
        cpu_cores  = psutil.cpu_count(logical=True) or 2
        cpu_based  = cpu_cores * 2
        ram        = psutil.virtual_memory()
        ram_mb     = ram.total / (1024 * 1024)
        ram_based  = max(1, int(ram_mb / _RAM_PER_PIPELINE_MB))
        return min(cpu_based, ram_based, 16)


# ============================================================================
# PIPELINE ENTRY
# ============================================================================

@dataclass
class PipelineEntry:
    camera_id:      str
    camera_type:    str
    camera_config:  dict
    camera_service: CameraServiceInterface
    pipeline:       "Any"  # DetectionPipeline — lazy import
    task:           Optional[asyncio.Task] = None
    started_at:     datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    restart_count:  int = 0
    last_error:     Optional[str] = None
    last_fps_check: float = field(default_factory=time.monotonic)


# ============================================================================
# PIPELINE MANAGER
# ============================================================================

class PipelineManager:
    """
    Barcha kamera pipelinelarini markaziy boshqarish.

    Singleton pattern — dastur bo'ylab bitta instance.
    """

    _instance: Optional["PipelineManager"] = None

    def __new__(cls) -> "PipelineManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not hasattr(self, "_initialized"):
            self._pipelines:     dict[str, PipelineEntry] = {}
            self._optimizer:     StreamOptimizer           = StreamOptimizer()
            self._balancer:      LoadBalancer              = LoadBalancer()
            self._watchdog_task: Optional[asyncio.Task]   = None
            # Har kamera uchun oxirgi detection — MJPEG stream bbox overlay uchun
            self._latest_detections: dict[str, dict] = {}
            # Har kamera uchun oxirgi frame — MJPEG stream uchun (race condition yo'q)
            self._latest_frames: dict[str, "np.ndarray"] = {}
            self._initialized    = True
            logger.info(
                "PipelineManager initialized",
                extra={"extra_data": {
                    "max_pipelines": self._balancer.max_pipelines,
                }},
            )

    # ================================================================
    # START
    # ================================================================

    async def start_camera(
        self,
        camera_id:    str,
        camera_type:  str   = "simulated",
        source:       Optional[str] = None,
        device_index: Optional[int] = None,
        fps:          int   = 10,
        skip_frames:  Optional[int] = None,
    ) -> tuple[bool, str]:
        """
        Kamera uchun detection pipeline ishga tushiradi.

        CAMERA TYPE:
            'simulated' → SimulatedCameraService (development/test)
            'rtsp'      → RTSPCameraService      (real IP kamera)
            'usb'       → USBCameraService        (USB/webcam)

        Returns:
            (True, "")       — muvaffaqiyatli
            (False, sabab)   — muvaffaqiyatsiz
        """
        if self.is_running(camera_id):
            return False, f"Pipeline '{camera_id}' allaqachon ishlayapti."

        can_start, reason = self._balancer.can_start(len(self._pipelines))
        if not can_start:
            logger.warning(f"LoadBalancer: {reason}")
            return False, reason

        try:
            camera_service = await self._create_camera_service(
                camera_id    = camera_id,
                camera_type  = camera_type,
                source       = source,
                device_index = device_index,
                fps          = fps,
            )

            try:
                from app.api.v1.websocket import get_ws_manager  # noqa: PLC0415
                ws_manager = get_ws_manager()
            except RuntimeError:
                ws_manager = None
                logger.warning(f"[{camera_id}] WebSocket manager yo'q")

            yolo     = get_yolo_service()
            from app.services.detection_pipeline import DetectionPipeline  # noqa: PLC0415
            pipeline = DetectionPipeline(
                camera_service = camera_service,
                yolo_service   = yolo,
                ws_manager     = ws_manager,
                frame_cache_cb = self.update_latest_frame,
            )

            effective_skip = skip_frames if skip_frames is not None \
                             else self._optimizer.get_skip_frames()

            if effective_skip > 0 and fps > 0:
                pipeline.MIN_FRAME_INTERVAL = effective_skip / fps

            await camera_service.initialize()
            await camera_service.start()

            pipeline._running = True
            pipeline.stats.reset()
            pipeline.stats.started_at = datetime.now(timezone.utc)

            task = asyncio.create_task(
                pipeline._run_loop(),
                name=f"pipeline-{camera_id}",
            )

            self._pipelines[camera_id] = PipelineEntry(
                camera_id      = camera_id,
                camera_type    = camera_type,
                camera_config  = {
                    "camera_type":  camera_type,
                    "source":       source,
                    "device_index": device_index,
                    "fps":          fps,
                    "skip_frames":  effective_skip,
                },
                camera_service = camera_service,
                pipeline       = pipeline,
                task           = task,
            )

            await self._ensure_watchdog_running()

            logger.info(
                "Pipeline ishga tushirildi",
                extra={"extra_data": {
                    "camera_id":    camera_id,
                    "camera_type":  camera_type,
                    "fps":          fps,
                    "skip_frames":  effective_skip,
                    "total_active": len(self._pipelines),
                }},
            )
            return True, ""

        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "Pipeline ishga tushirishda xato",
                extra={"extra_data": {"camera_id": camera_id, "error": error_msg}},
                exc_info=True,
            )
            self._pipelines.pop(camera_id, None)
            return False, f"Pipeline xatosi: {error_msg}"

    # ================================================================
    # STOP
    # ================================================================

    async def stop_camera(self, camera_id: str) -> tuple[bool, str]:
        """
        Bitta kamera pipelineni to'xtatadi.

        OpenCV VideoCapture.release() ba'zan minutlab bloklanishi mumkin.
        Shuning uchun camera_service.stop() ni 3 soniya timeout bilan o'raymiz.
        Timeout bo'lsa ham entry o'chiriladi — stream to'xtaydi.
        """
        entry = self._pipelines.get(camera_id)
        if entry is None:
            return False, f"Pipeline '{camera_id}' topilmadi."

        try:
            # 1. Asyncio taskni bekor qilamiz
            if entry.task and not entry.task.done():
                entry.task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(entry.task), timeout=2.0)
                except (asyncio.CancelledError, asyncio.TimeoutError):
                    pass

            # 2. Pipeline flagini o'chiramiz
            entry.pipeline._running = False

            # 3. camera_service.stop() — OpenCV release() bloklanmasin uchun timeout
            try:
                await asyncio.wait_for(entry.camera_service.stop(), timeout=3.0)
            except asyncio.TimeoutError:
                logger.warning(
                    f"[{camera_id}] camera_service.stop() 3s da tugamadi "
                    "(OpenCV release bloklanishi). Force stop."
                )
            except Exception as exc:
                logger.warning(f"[{camera_id}] camera_service.stop() xatosi: {exc}")

            # 4. Cache lardan o'chirish
            self._pipelines.pop(camera_id, None)
            self._latest_detections.pop(camera_id, None)
            self._latest_frames.pop(camera_id, None)

            logger.info(
                "Pipeline to'xtatildi",
                extra={"extra_data": {
                    "camera_id":    camera_id,
                    "total_active": len(self._pipelines),
                }},
            )

            if not self._pipelines and self._watchdog_task:
                self._watchdog_task.cancel()
                self._watchdog_task = None

            return True, ""

        except Exception as exc:
            error_msg = str(exc)
            logger.error(
                "Pipeline to'xtatishda xato",
                extra={"extra_data": {"camera_id": camera_id, "error": error_msg}},
            )
            self._pipelines.pop(camera_id, None)
            self._latest_detections.pop(camera_id, None)
            self._latest_frames.pop(camera_id, None)
            return False, f"Stop xatosi: {error_msg}"

    async def stop_all(self) -> int:
        """Barcha pipelinelarni to'xtatadi."""
        camera_ids = list(self._pipelines.keys())
        stopped    = 0

        for camera_id in camera_ids:
            ok, _ = await self.stop_camera(camera_id)
            if ok:
                stopped += 1

        logger.info(
            "Barcha pipelinelar to'xtatildi",
            extra={"extra_data": {"total": len(camera_ids), "stopped": stopped}},
        )
        return stopped

    # ================================================================
    # LIVE DETECTION TRACKING — MJPEG bbox overlay uchun
    # ================================================================

    def update_latest_detection(
        self,
        camera_id:  str,
        bbox:       dict,
        animal_tag: Optional[str],
        confidence: float,
        class_name: str = "animal",
    ) -> None:
        self._latest_detections[camera_id] = {
            "bbox":       bbox,
            "animal_tag": animal_tag,
            "confidence": confidence,
            "class_name": class_name,
            "ts":         time.monotonic(),
        }

    def get_latest_detection(self, camera_id: str) -> Optional[dict]:
        det = self._latest_detections.get(camera_id)
        if det is None:
            return None
        age = time.monotonic() - det["ts"]
        if age > 2.0:
            return None
        return det

    # ── Frame cache — MJPEG stream uchun ────────────────────────────

    def update_latest_frame(self, camera_id: str, frame: "np.ndarray") -> None:
        """
        DetectionPipeline har frame olganda shu metodini chaqiradi.
        MJPEG stream bevosita camera.get_frame() chaqirmay, shu cache dan oladi.
        Natija: OpenCV VideoCapture da race condition bo'lmaydi.
        """
        self._latest_frames[camera_id] = frame

    def get_latest_frame(self, camera_id: str) -> Optional["np.ndarray"]:
        """MJPEG stream uchun eng so'nggi kamera kadrini qaytaradi."""
        return self._latest_frames.get(camera_id)

    def get_camera_service(self, camera_id: str) -> Optional[CameraServiceInterface]:
        """Pipeline ichidagi kamera servisini qaytaradi (MJPEG uchun)."""
        entry = self._pipelines.get(camera_id)
        return entry.camera_service if entry else None

    # ================================================================
    # STATUS
    # ================================================================

    def is_running(self, camera_id: str) -> bool:
        entry = self._pipelines.get(camera_id)
        if entry is None:
            return False
        if entry.task and entry.task.done():
            self._pipelines.pop(camera_id, None)
            return False
        return entry.pipeline.is_running

    def get_status(self, camera_id: str) -> dict:
        entry = self._pipelines.get(camera_id)

        if entry is None or not self.is_running(camera_id):
            return {
                "camera_id":     camera_id,
                "running":       False,
                "stats":         None,
                "started_at":    None,
                "restart_count": 0,
                "last_error":    None,
            }

        return {
            "camera_id":     camera_id,
            "running":       True,
            "stats":         entry.pipeline.get_stats(),
            "started_at":    entry.started_at.isoformat(),
            "restart_count": entry.restart_count,
            "last_error":    entry.last_error,
        }

    def get_all_status(self) -> dict[str, dict]:
        dead = [
            cid for cid, e in self._pipelines.items()
            if e.task and e.task.done()
        ]
        for cid in dead:
            self._pipelines.pop(cid, None)

        return {cid: self.get_status(cid) for cid in list(self._pipelines.keys())}

    def list_running(self) -> list[str]:
        return [cid for cid in list(self._pipelines.keys()) if self.is_running(cid)]

    def total_running(self) -> int:
        return len(self.list_running())

    def get_system_metrics(self) -> dict:
        """Tizim resurslari va load balancing holati."""
        try:
            cpu              = psutil.cpu_percent(interval=None)
            ram              = psutil.virtual_memory()
            ram_available_mb = ram.available / (1024 * 1024)
        except Exception:
            cpu, ram_available_mb = 0.0, 0.0
            ram = type("R", (), {"percent": 0})()

        active     = self.total_running()
        can_start, _ = self._balancer.can_start(active)

        return {
            "cpu_percent":         round(cpu, 1),
            "ram_percent":         round(getattr(ram, "percent", 0), 1),
            "ram_available_mb":    round(ram_available_mb, 0),
            "active_pipelines":    active,
            "max_pipelines":       self._balancer.max_pipelines,
            "current_skip_frames": self._optimizer.get_skip_frames(),
            "can_start_new":       can_start,
        }

    # ================================================================
    # HEALTH WATCHDOG
    # ================================================================

    async def _ensure_watchdog_running(self) -> None:
        if self._watchdog_task is None or self._watchdog_task.done():
            self._watchdog_task = asyncio.create_task(
                self._watchdog_loop(),
                name="pipeline-watchdog",
            )
            logger.info("Pipeline health watchdog started")

    async def _watchdog_loop(self) -> None:
        logger.info("Watchdog loop started")
        try:
            while True:
                await asyncio.sleep(_WATCHDOG_INTERVAL)

                if not self._pipelines:
                    logger.info("No active pipelines — watchdog exiting")
                    break

                for camera_id in list(self._pipelines.keys()):
                    await self._check_pipeline_health(camera_id)

        except asyncio.CancelledError:
            logger.info("Watchdog loop cancelled (normal)")
        except Exception as exc:
            logger.error(f"Watchdog loop error: {exc}", exc_info=True)

    async def _check_pipeline_health(self, camera_id: str) -> None:
        entry = self._pipelines.get(camera_id)
        if entry is None:
            return

        # ── Task crashed? ─────────────────────────────────────────────
        if entry.task and entry.task.done():
            exc = entry.task.exception() if not entry.task.cancelled() else None
            if exc:
                entry.last_error = str(exc)

            logger.warning(
                f"[{camera_id}] Pipeline task ended unexpectedly. "
                f"Restart #{entry.restart_count + 1}..."
            )

            if entry.restart_count < _MAX_RESTART_ATTEMPTS:
                await self._restart_pipeline(camera_id)
            else:
                logger.error(
                    f"[{camera_id}] Max restarts ({_MAX_RESTART_ATTEMPTS}) reached. "
                    "Pipeline removed."
                )
                self._pipelines.pop(camera_id, None)
            return

        # ── FPS = 0 uzun vaqt? ────────────────────────────────────────
        try:
            stats = entry.pipeline.get_stats()
            fps   = stats.get("fps", -1)

            if fps == 0.0:
                now = time.monotonic()
                if now - entry.last_fps_check > _ZERO_FPS_THRESHOLD:
                    logger.warning(
                        f"[{camera_id}] FPS = 0 for {_ZERO_FPS_THRESHOLD}s. Restarting..."
                    )
                    entry.last_error = "FPS = 0 timeout"
                    await self._restart_pipeline(camera_id)
            else:
                entry.last_fps_check = time.monotonic()

        except Exception as exc:
            logger.warning(f"[{camera_id}] Stats check error: {exc}")

    async def _restart_pipeline(self, camera_id: str) -> None:
        entry = self._pipelines.get(camera_id)
        if entry is None:
            return

        restart_count = entry.restart_count + 1
        config        = entry.camera_config.copy()

        logger.info(f"[{camera_id}] Restarting (attempt #{restart_count})...")

        await self.stop_camera(camera_id)
        await asyncio.sleep(2.0)

        ok, reason = await self.start_camera(
            camera_id    = camera_id,
            camera_type  = config.get("camera_type", "simulated"),
            source       = config.get("source"),
            device_index = config.get("device_index"),
            fps          = config.get("fps", 10),
            skip_frames  = config.get("skip_frames"),
        )

        if ok:
            new_entry = self._pipelines.get(camera_id)
            if new_entry:
                new_entry.restart_count = restart_count
            logger.info(f"[{camera_id}] Restart #{restart_count} successful")
        else:
            logger.error(f"[{camera_id}] Restart #{restart_count} failed: {reason}")

    # ================================================================
    # KAMERA SERVISI YARATISH
    # ================================================================

    async def _create_camera_service(
        self,
        camera_id:    str,
        camera_type:  str,
        source:       Optional[str],
        device_index: Optional[int],
        fps:          int,
    ) -> CameraServiceInterface:
        """
        Kamera turiga mos async servis yaratadi.

        MUHIM: Endi RTSP va USB uchun REAL implementatsiya ishlatiladi.
        SimulatedCameraService ga fallback YO'Q.
        """
        if camera_type == "simulated":
            return SimulatedCameraService(
                camera_id  = camera_id,
                fps        = fps,
                resolution = (1280, 720),
                mode       = "random",
            )

        elif camera_type == "rtsp":
            if not source:
                raise ValueError(
                    f"[{camera_id}] RTSP kamera uchun 'source' (URL) talab qilinadi."
                )
            from app.services.camera.rtsp_camera_service import RTSPCameraService
            return RTSPCameraService(
                camera_id          = camera_id,
                rtsp_url           = source,
                fps                = fps,
                width              = 1920,
                height             = 1080,
                reconnect_interval = 5,
                connection_timeout = 10,
                buffer_size        = 1,
                auto_reconnect     = True,
            )

        elif camera_type == "usb":
            if device_index is None:
                raise ValueError(
                    f"[{camera_id}] USB kamera uchun 'device_index' talab qilinadi."
                )
            from app.services.camera.usb_camera_service import USBCameraService
            return USBCameraService(
                camera_id      = camera_id,
                device_index   = device_index,
                fps            = fps,
                width          = 1280,
                height         = 720,
                auto_reconnect = True,
            )

        else:
            raise ValueError(
                f"[{camera_id}] Noma'lum kamera turi: '{camera_type}'. "
                "Qabul qilinadigan qiymatlar: 'simulated', 'rtsp', 'usb'."
            )


# ============================================================================
# GLOBAL INSTANCE
# ============================================================================

_pipeline_manager: Optional[PipelineManager] = None


def get_pipeline_manager() -> PipelineManager:
    """Global PipelineManager instance ni qaytaradi (Singleton)."""
    global _pipeline_manager
    if _pipeline_manager is None:
        _pipeline_manager = PipelineManager()
    return _pipeline_manager