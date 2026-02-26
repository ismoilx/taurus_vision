"""
Taurus Vision — USB Camera Service (Async Wrapper)

USBCamera (sinxron CameraInterface) ni CameraServiceInterface (asinxron)
ga moslaydi. RTSPCameraService bilan bir xil pattern.

USB KAMERA O'ZIGA XOSLIGI:
    - USB to'g'ri ulanmagan bo'lsa — darhol aniqlanadi
    - Linuxda /dev/video0, /dev/video1 ko'rinishida (yoki index 0, 1...)
    - OpenCV USBCamera uchun thread-safe emas → to_thread() zarur
    - auto_reconnect: Kamera chiqarib qo'yilsa qayta ulanadi

FOYDALANISH:
    service = USBCameraService(
        camera_id="CAM-USB-01",
        device_index=0,
        fps=15,
    )
    await service.initialize()
    async for frame in service.stream_frames(skip_frames=2):
        result = await yolo_service.detect(frame.frame)
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import AsyncGenerator, Optional

import numpy as np

from app.services.camera.base import (
    CameraFrame,
    CameraInfo,
    CameraServiceInterface,
)
from app.services.camera.usb_camera import USBCamera

logger = logging.getLogger(__name__)

_MAX_CONSECUTIVE_ERRORS: int = 5   # USB qurilma chiqarilganda tezroq qayta ulanish
_RECONNECT_DELAY:        float = 3.0  # sekund (USB tez aniqlanadi)


class USBCameraService(CameraServiceInterface):
    """
    Async USB kamera servisi.

    USBCamera (sync, OpenCV-based) ni asinxron interfeysi bilan o'raydi.
    DetectionPipeline dan foydalanish uchun mo'ljallangan.

    Args:
        camera_id:     Noyob kamera identifikatori
        device_index:  USB qurilma indeksi (0, 1, 2...)
        fps:           Kadr chiqarish tezligi
        width:         Kadr kengligi (piksel)
        height:        Kadr balandligi (piksel)
        auto_reconnect: Qurilma chiqarib qo'yilganda qayta ulanish
    """

    def __init__(
        self,
        camera_id: str,
        device_index: int = 0,
        fps: int = 15,
        width: int = 1280,
        height: int = 720,
        auto_reconnect: bool = True,
    ) -> None:
        self._camera_id     = camera_id
        self._device_index  = device_index
        self._fps           = fps
        self._width         = width
        self._height        = height
        self._auto_reconnect = auto_reconnect

        self._camera = USBCamera(
            camera_id      = camera_id,
            device_index   = device_index,
            fps            = fps,
            width          = width,
            height         = height,
            auto_reconnect = auto_reconnect,
        )

        self._is_active           = False
        self._frame_count         = 0
        self._consecutive_errors  = 0
        self._last_successful_frame: Optional[float] = None

        logger.info(
            "USBCameraService initialized",
            extra={"extra_data": {
                "camera_id":    camera_id,
                "device_index": device_index,
                "fps":          fps,
                "resolution":   f"{width}x{height}",
            }},
        )

    # =========================================================================
    # CameraServiceInterface — majburiy metodlar
    # =========================================================================

    async def initialize(self) -> None:
        """
        USB kamerani ishga tayyorlaydi.

        Raises:
            RuntimeError: Agar USB qurilma topilmasa yoki ochib bo'lmasa
        """
        logger.info(
            f"[{self._camera_id}] Initializing USB camera (device={self._device_index})..."
        )

        try:
            await asyncio.to_thread(self._camera.start)

            connected = await asyncio.to_thread(self._camera.is_opened)
            if not connected:
                raise RuntimeError(
                    f"[{self._camera_id}] USB qurilma ({self._device_index}) "
                    "topilmadi yoki ochib bo'lmadi."
                )

            actual_res = await asyncio.to_thread(self._camera.get_resolution)
            self._width  = actual_res[0]
            self._height = actual_res[1]

            self._is_active = True
            logger.info(
                f"[{self._camera_id}] USB camera connected",
                extra={"extra_data": {
                    "camera_id":    self._camera_id,
                    "device_index": self._device_index,
                    "resolution":   f"{self._width}x{self._height}",
                    "fps":          await asyncio.to_thread(self._camera.get_fps),
                }},
            )

        except Exception as exc:
            self._is_active = False
            logger.error(
                f"[{self._camera_id}] USB initialization failed: {exc}",
                exc_info=True,
            )
            raise

    async def start(self) -> None:
        """Kamerani ishga tushiradi (initialize qilinmagan bo'lsa)."""
        if not self._is_active:
            await self.initialize()

    async def get_frame(self) -> CameraFrame:
        """
        USB kameradan bitta kadr oladi.

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
                    f"[{self._camera_id}] USB frame olishda xato"
                )

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
            logger.error(f"[{self._camera_id}] Unexpected USB error: {exc}")
            raise RuntimeError(
                f"[{self._camera_id}] USB frame error: {exc}"
            ) from exc

    async def stream_frames(
        self,
        skip_frames: int = 1,
    ) -> AsyncGenerator[CameraFrame, None]:
        """
        Uzluksiz USB kadr oqimini beradi.

        Args:
            skip_frames: Har N-chi kadrni qayta ishlash

        Yields:
            CameraFrame obyektlari
        """
        if not self._is_active:
            raise RuntimeError(
                f"[{self._camera_id}] Camera not active. Call initialize() first."
            )

        frame_interval = 1.0 / self._fps
        local_count    = 0

        logger.info(
            f"[{self._camera_id}] USB stream started",
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

                    if local_count % skip_frames == 0:
                        yield frame

                except RuntimeError as exc:
                    logger.warning(f"[{self._camera_id}] USB frame error in stream: {exc}")
                    await asyncio.sleep(0.1)
                    continue

                elapsed    = time.monotonic() - loop_start
                sleep_time = max(0.0, frame_interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            logger.info(f"[{self._camera_id}] USB stream cancelled (normal shutdown)")
            raise
        except Exception as exc:
            logger.error(f"[{self._camera_id}] USB stream error: {exc}", exc_info=True)
            raise
        finally:
            logger.info(
                f"[{self._camera_id}] USB stream ended",
                extra={"extra_data": {"frames_yielded": local_count // max(skip_frames, 1)}},
            )

    async def stop(self) -> None:
        """USB kamerani to'xtatadi va resurslarni ozod qiladi."""
        logger.info(f"[{self._camera_id}] Stopping USB camera...")
        self._is_active = False

        try:
            await asyncio.to_thread(self._camera.stop)
        except Exception as exc:
            logger.error(f"[{self._camera_id}] USB stop error: {exc}")

        logger.info(f"[{self._camera_id}] USB camera stopped")

    def get_info(self) -> CameraInfo:
        """Kamera metadata va konfiguratsiyasini qaytaradi."""
        return CameraInfo(
            camera_id  = self._camera_id,
            name       = f"USB Camera {self._camera_id} (device={self._device_index})",
            type       = "usb",
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
        """USB kamera ishlash statistikasini qaytaradi."""
        base_stats = self._camera.get_stats()
        base_stats.update({
            "service_type":        "usb_service",
            "is_active":           self._is_active,
            "service_frame_count": self._frame_count,
            "consecutive_errors":  self._consecutive_errors,
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
        USB kamerani qayta ulashga urinadi.

        USB qurilmalar odatda qisqa vaqt ichida qayta aniqlanadi.
        """
        if not self._auto_reconnect:
            logger.warning(
                f"[{self._camera_id}] auto_reconnect=False, reconnect o'tkazib yuborildi"
            )
            return

        logger.info(
            f"[{self._camera_id}] USB reconnect: {_RECONNECT_DELAY}s kutilmoqda..."
        )
        await asyncio.sleep(_RECONNECT_DELAY)

        try:
            await asyncio.to_thread(self._camera.stop)
            await asyncio.sleep(0.5)  # Qurilma reset uchun
            await asyncio.to_thread(self._camera.start)

            connected = await asyncio.to_thread(self._camera.is_opened)
            if connected:
                self._consecutive_errors = 0
                logger.info(f"[{self._camera_id}] USB reconnect muvaffaqiyatli")
            else:
                logger.error(
                    f"[{self._camera_id}] USB reconnect muvaffaqiyatsiz. "
                    "Pipeline to'xtatiladi."
                )
                self._is_active = False

        except Exception as exc:
            logger.error(
                f"[{self._camera_id}] USB reconnect xatosi: {exc}"
            )
            self._is_active = False
