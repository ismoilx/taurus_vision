"""
Taurus Vision — RTSP Camera Service (Async Wrapper)

RTSPCamera (sinxron CameraInterface) ni CameraServiceInterface (asinxron)
ga moslaydi. DetectionPipeline shu interfeys orqali ishlaydi.

PATTERN:
    RTSPCamera (OpenCV sync) — asyncio.to_thread() → RTSPCameraService (async)

RECONNECT STRATEGY:
    Ulanish uzilganda eksponensial backoff bilan qayta urinadi:
    1s → 2s → 4s → 8s → max 30s

THREAD SAFETY:
    OpenCV VideoCapture thread-safe emas — shuning uchun barcha
    sync operatsiyalar bitta ThreadPoolExecutor orqali bajariladi.
"""

import asyncio
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

import numpy as np

from app.services.camera.base import (
    CameraFrame,
    CameraInfo,
    CameraServiceInterface,
)
from app.services.camera.rtsp_camera import RTSPCamera

logger = logging.getLogger(__name__)

# Reconnect sozlamalari
_RECONNECT_BASE_DELAY: float = 1.0   # sekund
_RECONNECT_MAX_DELAY:  float = 30.0  # sekund
_RECONNECT_FACTOR:     float = 2.0   # eksponensial
_MAX_CONSECUTIVE_ERRORS: int = 10    # shu sondagi xatodan keyin reconnect


class RTSPCameraService(CameraServiceInterface):
    """
    Async RTSP kamera servisi.

    RTSPCamera (sync, OpenCV-based) ni asinxron interfeysi bilan o'raydi.
    DetectionPipeline dan foydalanish uchun mo'ljallangan.

    FOYDALANISH:
        service = RTSPCameraService(
            camera_id="CAM-BARN-01",
            rtsp_url="rtsp://192.168.1.100:554/stream1",
            fps=10,
        )
        await service.initialize()
        await service.start()

        async for frame in service.stream_frames(skip_frames=3):
            detections = await yolo_service.detect(frame.frame)

        await service.stop()

    Args:
        camera_id:          Noyob kamera identifikatori
        rtsp_url:           RTSP stream URL (rtsp://user:pass@host:port/path)
        fps:                Kadr chiqarish tezligi
        width:              Kadr kengligi (piksel)
        height:             Kadr balandligi (piksel)
        reconnect_interval: Qayta ulanish oralig'i (sekund)
        connection_timeout: Ulanish kutish vaqti (sekund)
        buffer_size:        OpenCV buffer hajmi (1 = eng yangi kadr)
        auto_reconnect:     Ulanish uzilganda avtomatik qayta ulanish
    """

    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        fps: int = 10,
        width: int = 1920,
        height: int = 1080,
        reconnect_interval: int = 5,
        connection_timeout: int = 10,
        buffer_size: int = 1,
        auto_reconnect: bool = True,
    ) -> None:
        self._camera_id   = camera_id
        self._rtsp_url    = rtsp_url
        self._fps         = fps
        self._width       = width
        self._height      = height
        self._auto_reconnect = auto_reconnect

        # Ichki RTSPCamera
        self._camera = RTSPCamera(
            camera_id           = camera_id,
            rtsp_url            = rtsp_url,
            fps                 = fps,
            width               = width,
            height              = height,
            reconnect_interval  = reconnect_interval,
            connection_timeout  = connection_timeout,
            buffer_size         = buffer_size,
        )

        self._is_active        = False
        self._frame_count      = 0
        self._consecutive_errors = 0
        self._last_successful_frame: Optional[float] = None  # UNIX timestamp

        logger.info(
            "RTSPCameraService initialized",
            extra={"extra_data": {
                "camera_id": camera_id,
                "url":       self._mask_url(rtsp_url),
                "fps":       fps,
            }},
        )

    # =========================================================================
    # CameraServiceInterface — majburiy metodlar
    # =========================================================================

    async def initialize(self) -> None:
        """
        RTSP kamerani ishga tayyorlaydi.

        OpenCV VideoCapture ni thread executor orqali ochadi.
        Raises:
            RuntimeError: Agar ulanish muvaffaqiyatsiz bo'lsa
        """
        logger.info(f"[{self._camera_id}] Initializing RTSP connection...")

        try:
            # Sync operatsiyani async thread da bajarish
            await asyncio.to_thread(self._camera.start)

            # Ulanishni tekshirish
            connected = await asyncio.to_thread(self._camera.is_opened)
            if not connected:
                raise RuntimeError(
                    f"[{self._camera_id}] RTSP stream ga ulanib bo'lmadi: "
                    f"{self._mask_url(self._rtsp_url)}"
                )

            self._is_active = True
            logger.info(
                f"[{self._camera_id}] RTSP connection established",
                extra={"extra_data": {
                    "camera_id": self._camera_id,
                    "url":       self._mask_url(self._rtsp_url),
                }},
            )

        except Exception as exc:
            self._is_active = False
            logger.error(
                f"[{self._camera_id}] RTSP initialization failed: {exc}",
                exc_info=True,
            )
            raise

    async def start(self) -> None:
        """Kamerani ishga tushiradi (initialize qilinmagan bo'lsa)."""
        if not self._is_active:
            await self.initialize()

    async def get_frame(self) -> CameraFrame:
        """
        Kameradan bitta kadr oladi.

        Returns:
            CameraFrame — kadr va metadata bilan

        Raises:
            RuntimeError: Kamera aktiv emas yoki kadr olishda xato
        """
        if not self._is_active:
            raise RuntimeError(
                f"[{self._camera_id}] Camera is not active. "
                "Call initialize() first."
            )

        try:
            # Sync get_frame ni thread da bajar
            frame_data: Optional[np.ndarray] = await asyncio.to_thread(
                self._camera.get_frame
            )

            if frame_data is None:
                self._consecutive_errors += 1
                if self._consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
                    logger.warning(
                        f"[{self._camera_id}] {_MAX_CONSECUTIVE_ERRORS} "
                        "ketma-ket xato — qayta ulanish..."
                    )
                    await self._reconnect()
                raise RuntimeError(
                    f"[{self._camera_id}] Frame olishda xato yuz berdi"
                )

            # Muvaffaqiyatli kadr
            self._consecutive_errors  = 0
            self._frame_count        += 1
            self._last_successful_frame = time.monotonic()

            return CameraFrame(
                frame        = frame_data,
                timestamp    = datetime.utcnow(),
                camera_id    = self._camera_id,
                frame_number = self._frame_count,
                resolution   = (self._width, self._height),
            )

        except RuntimeError:
            raise
        except Exception as exc:
            self._consecutive_errors += 1
            logger.error(f"[{self._camera_id}] Unexpected error: {exc}")
            raise RuntimeError(f"[{self._camera_id}] Frame error: {exc}") from exc

    async def stream_frames(
        self,
        skip_frames: int = 1,
    ) -> AsyncGenerator[CameraFrame, None]:
        """
        Uzluksiz kadr oqimini beradi.

        Args:
            skip_frames: Har N-chi kadrni qayta ishlash (1 = barchasi)

        Yields:
            CameraFrame obyektlari

        Notes:
            FPS throttling: kadrlar orasidagi vaqt = 1 / fps
            stream_frames to'xtatilganda CancelledError ni to'g'ri ushlaydi
        """
        if not self._is_active:
            raise RuntimeError(
                f"[{self._camera_id}] Camera not active. Call initialize() first."
            )

        frame_interval = 1.0 / self._fps  # sekund
        local_count    = 0

        logger.info(
            f"[{self._camera_id}] Stream started",
            extra={"extra_data": {
                "fps":         self._fps,
                "skip_frames": skip_frames,
            }},
        )

        try:
            while self._is_active:
                loop_start = time.monotonic()

                try:
                    frame = await self.get_frame()
                    local_count += 1

                    # skip_frames filtri
                    if local_count % skip_frames == 0:
                        yield frame

                except RuntimeError as exc:
                    # Biroz kutib davom etamiz (kamera vaqtinchalik muammo)
                    logger.warning(f"[{self._camera_id}] Frame error in stream: {exc}")
                    await asyncio.sleep(0.1)
                    continue

                # FPS throttling: qolgan vaqtni uxlatamiz
                elapsed = time.monotonic() - loop_start
                sleep_time = max(0.0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"[{self._camera_id}] Stream cancelled (normal shutdown)")
            raise
        except Exception as exc:
            logger.error(
                f"[{self._camera_id}] Stream error: {exc}",
                exc_info=True,
            )
            raise
        finally:
            logger.info(
                f"[{self._camera_id}] Stream ended",
                extra={"extra_data": {
                    "total_frames_yielded": local_count // max(skip_frames, 1),
                }},
            )

    async def stop(self) -> None:
        """Kamerani to'xtatadi va resurslarni ozod qiladi."""
        logger.info(f"[{self._camera_id}] Stopping RTSP camera...")
        self._is_active = False

        try:
            await asyncio.to_thread(self._camera.stop)
        except Exception as exc:
            logger.error(f"[{self._camera_id}] Stop error: {exc}")

        logger.info(f"[{self._camera_id}] RTSP camera stopped")

    def get_info(self) -> CameraInfo:
        """Kamera metadata va konfiguratsiyasini qaytaradi."""
        return CameraInfo(
            camera_id  = self._camera_id,
            name       = f"RTSP Camera {self._camera_id}",
            type       = "rtsp",
            resolution = (self._width, self._height),
            fps        = self._fps,
            is_active  = self._is_active,
            location   = None,
        )

    @property
    def is_active(self) -> bool:
        """Kamera aktiv ekanligini tekshiradi."""
        return self._is_active

    @property
    def camera_id(self) -> str:
        """Kamera identifikatorini qaytaradi."""
        return self._camera_id

    # =========================================================================
    # QO'SHIMCHA METODLAR
    # =========================================================================

    def get_stats(self) -> dict:
        """Kamera ishlash statistikasini qaytaradi."""
        base_stats = self._camera.get_stats()
        base_stats.update({
            "service_type":       "rtsp_service",
            "is_active":          self._is_active,
            "service_frame_count": self._frame_count,
            "consecutive_errors": self._consecutive_errors,
            "last_successful_frame_ago": (
                round(time.monotonic() - self._last_successful_frame, 2)
                if self._last_successful_frame else None
            ),
        })
        return base_stats

    # =========================================================================
    # ICHKI METODLAR
    # =========================================================================

    async def _reconnect(self) -> None:
        """
        Eksponensial backoff bilan qayta ulanish.

        auto_reconnect=True bo'lmasa — qayta ulanmaydi.
        """
        if not self._auto_reconnect:
            logger.warning(
                f"[{self._camera_id}] auto_reconnect=False, reconnect o'tkazib yuborildi"
            )
            return

        delay = _RECONNECT_BASE_DELAY

        for attempt in range(1, 6):  # Max 5 urinish
            logger.info(
                f"[{self._camera_id}] Reconnect urinish #{attempt} "
                f"({delay:.1f}s kutilmoqda)..."
            )
            await asyncio.sleep(delay)

            try:
                await asyncio.to_thread(self._camera.stop)
                await asyncio.to_thread(self._camera.start)
                connected = await asyncio.to_thread(self._camera.is_opened)

                if connected:
                    self._consecutive_errors = 0
                    logger.info(
                        f"[{self._camera_id}] Reconnect muvaffaqiyatli "
                        f"(urinish #{attempt})"
                    )
                    return

            except Exception as exc:
                logger.warning(
                    f"[{self._camera_id}] Reconnect #{attempt} muvaffaqiyatsiz: {exc}"
                )

            delay = min(delay * _RECONNECT_FACTOR, _RECONNECT_MAX_DELAY)

        logger.error(
            f"[{self._camera_id}] Barcha reconnect urinishlari muvaffaqiyatsiz. "
            "Pipeline to'xtatiladi."
        )
        self._is_active = False

    @staticmethod
    def _mask_url(url: str) -> str:
        """Log uchun RTSP URL dagi parolni yashiradi."""
        import re
        return re.sub(r"://([^:]+):([^@]+)@", r"://***:***@", url)
