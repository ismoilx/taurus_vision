"""
Taurus Vision — Colab GPU Pipeline

MAQSAD:
    Kameradan kadrlarni olib, Colab GPU ga JPEG formatda yuboradi.
    Colab YOLO + Tracker bajaradi va natijani /api/v1/colab/push-tracks
    endpointiga qaytaradi.

JARAYON:
    Kamera (RTSP/USB/Simulated)
         ↓  get_frame()
    ColabPipeline (backend)
         ↓  POST /frame  (JPEG bytes)
    Colab Flask Server (GPU)
         ↓  YOLO → MuzzleDetector → Embedding → Tracker
    Backend /api/v1/colab/push-tracks
         ↓
    DB + WebSocket
"""

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.services.camera.base import CameraServiceInterface

logger = logging.getLogger(__name__)


class ColabPipelineStats:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.started_at:      Optional[datetime] = None
        self.total_frames:    int   = 0
        self.sent_frames:     int   = 0
        self.skipped_frames:  int   = 0
        self.errors:          int   = 0
        self.avg_latency_ms:  float = 0.0
        self._latency_buf:    list  = []

    def add_latency(self, ms: float) -> None:
        self._latency_buf.append(ms)
        if len(self._latency_buf) > 30:
            self._latency_buf.pop(0)
        self.avg_latency_ms = round(sum(self._latency_buf) / len(self._latency_buf), 1)

    @property
    def fps(self) -> float:
        if not self.started_at:
            return 0.0
        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return round(self.sent_frames / max(uptime, 1), 2)

    def to_dict(self) -> dict:
        return {
            "mode":           "colab_gpu",
            "total_frames":   self.total_frames,
            "sent_frames":    self.sent_frames,
            "skipped_frames": self.skipped_frames,
            "errors":         self.errors,
            "fps":            self.fps,
            "avg_latency_ms": self.avg_latency_ms,
        }


class ColabPipeline:
    """
    Kamera kadrlarini Colab GPU ga yuboruvchi pipeline.
    Target: 15 FPS.
    """

    def __init__(
        self,
        camera_service: CameraServiceInterface,
        colab_url:      str,
        colab_secret:   Optional[str] = None,
        target_fps:     int  = 15,
        jpeg_quality:   int  = 70,
        frame_scale:    int  = 1,
    ) -> None:
        self.camera       = camera_service
        self.colab_url    = colab_url.rstrip("/")
        self.frame_url    = f"{self.colab_url}/frame"
        self.target_fps   = target_fps
        self.jpeg_quality = jpeg_quality
        self.frame_scale  = frame_scale

        # 15 FPS → har 0.067 soniyada bir kadr
        self.MIN_FRAME_INTERVAL = 1.0 / target_fps

        self._headers = {"Content-Type": "application/octet-stream"}
        if colab_secret:
            self._headers["X-Colab-Key"] = colab_secret

        self._running = False
        self._task:   Optional[asyncio.Task] = None
        self.stats    = ColabPipelineStats()
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"ColabPipeline initialized | "
            f"camera={camera_service.camera_id} | "
            f"target_fps={target_fps} | "
            f"colab_url={self.colab_url}"
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return

        self._running = True
        self.stats.reset()
        self.stats.started_at = datetime.now(timezone.utc)

        # httpx client — keep-alive bilan tezroq
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=3.0, write=3.0, pool=5.0),
            limits=httpx.Limits(max_connections=2, max_keepalive_connections=2),
        )

        await self.camera.start()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"ColabPipeline started | camera={self.camera.camera_id} | fps={self.target_fps}")

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

        await self.camera.stop()

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info(f"ColabPipeline stopped | stats={self.stats.to_dict()}")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        base = self.stats.to_dict()
        base["status"]    = "running" if self._running else "stopped"
        base["camera_id"] = self.camera.camera_id
        base["colab_url"] = self.colab_url
        return base

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        last_frame_time = 0.0

        while self._running:
            try:
                # FPS nazorati
                now     = time.monotonic()
                elapsed = now - last_frame_time
                if elapsed < self.MIN_FRAME_INTERVAL:
                    await asyncio.sleep(self.MIN_FRAME_INTERVAL - elapsed)

                frame = await self.camera.get_frame()
                self.stats.total_frames += 1

                if frame is None:
                    await asyncio.sleep(0.01)
                    continue

                last_frame_time = time.monotonic()

                # Non-blocking yuborish — Colab sekin bo'lsa ham loop to'xtamasin
                asyncio.create_task(self._send_frame(frame.frame))

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"ColabPipeline loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _send_frame(self, frame_bgr) -> None:
        """Kadrni JPEG ga aylantirib Colabga yuborish."""
        import cv2

        try:
            # Kichraytirish (tarmoq tejash)
            if self.frame_scale > 1:
                h, w = frame_bgr.shape[:2]
                frame_bgr = cv2.resize(
                    frame_bgr,
                    (w // self.frame_scale, h // self.frame_scale)
                )

            # JPEG encode
            ok, buf = cv2.imencode(
                ".jpg", frame_bgr,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if not ok:
                self.stats.errors += 1
                return

            # Colabga yuborish
            t0 = time.monotonic()
            resp = await self._client.post(
                self.frame_url,
                content=buf.tobytes(),
                headers=self._headers,
            )
            latency_ms = (time.monotonic() - t0) * 1000

            if resp.status_code == 200:
                self.stats.sent_frames += 1
                self.stats.add_latency(latency_ms)
                d = resp.json()
                logger.debug(
                    f"[colab] fno={d.get('fno')} fps={d.get('fps')} "
                    f"tracks={d.get('tracks')} lat={latency_ms:.0f}ms"
                )
            else:
                self.stats.errors += 1
                logger.warning(f"[colab] frame rejected: {resp.status_code}")

        except httpx.TimeoutException:
            self.stats.skipped_frames += 1
        except httpx.ConnectError:
            self.stats.errors += 1
            logger.warning("[colab] Colab bilan aloqa uzildi...")
            await asyncio.sleep(2.0)
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"[colab] send_frame xato: {e}")


import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

from app.services.camera.base import CameraServiceInterface
from app.config import settings

logger = logging.getLogger(__name__)


class ColabPipelineStats:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.started_at:      Optional[datetime] = None
        self.total_frames:    int   = 0
        self.sent_frames:     int   = 0
        self.skipped_frames:  int   = 0
        self.errors:          int   = 0
        self.avg_latency_ms:  float = 0.0
        self._latency_sum:    float = 0.0
        self._latency_count:  int   = 0

    def add_latency(self, ms: float) -> None:
        self._latency_sum   += ms
        self._latency_count += 1
        self.avg_latency_ms  = round(self._latency_sum / self._latency_count, 1)

    @property
    def fps(self) -> float:
        if not self.started_at:
            return 0.0
        uptime = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return round(self.sent_frames / max(uptime, 1), 2)

    def to_dict(self) -> dict:
        return {
            "mode":            "colab_gpu",
            "total_frames":    self.total_frames,
            "sent_frames":     self.sent_frames,
            "skipped_frames":  self.skipped_frames,
            "errors":          self.errors,
            "fps":             self.fps,
            "avg_latency_ms":  self.avg_latency_ms,
        }


class ColabPipeline:
    """
    Kamera kadrlarini Colab GPU ga yuboruvchi pipeline.

    DetectionPipeline bilan bir xil interfeys —
    PipelineManager ikkalasini bir xil boshqaradi.
    """

    MIN_FRAME_INTERVAL = 0.1   # max 10 FPS Colabga

    def __init__(
        self,
        camera_service: CameraServiceInterface,
        colab_url:      str,
        colab_secret:   Optional[str] = None,
        jpeg_quality:   int = 70,
        frame_scale:    int = 1,
    ) -> None:
        self.camera        = camera_service
        self.colab_url     = colab_url.rstrip("/")
        self.frame_url     = f"{self.colab_url}/frame"
        self.jpeg_quality  = jpeg_quality
        self.frame_scale   = frame_scale

        self._headers = {"Content-Type": "application/octet-stream"}
        if colab_secret:
            self._headers["X-Colab-Key"] = colab_secret

        self._running = False
        self._task:   Optional[asyncio.Task] = None
        self.stats    = ColabPipelineStats()

        # httpx async client — connection reuse uchun
        self._client: Optional[httpx.AsyncClient] = None

        logger.info(
            f"ColabPipeline initialized | "
            f"camera={camera_service.camera_id} | "
            f"colab_url={self.colab_url}"
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            logger.warning("ColabPipeline already running")
            return

        self._running = True
        self.stats.reset()
        self.stats.started_at = datetime.now(timezone.utc)

        self._client = httpx.AsyncClient(timeout=5.0)

        await self.camera.start()
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"ColabPipeline started | camera={self.camera.camera_id}")

    async def stop(self) -> None:
        if not self._running:
            return

        logger.info("ColabPipeline stopping...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self.camera.stop()

        if self._client:
            await self._client.aclose()
            self._client = None

        logger.info(f"ColabPipeline stopped | stats={self.stats.to_dict()}")

    @property
    def is_running(self) -> bool:
        return self._running

    def get_stats(self) -> dict:
        base = self.stats.to_dict()
        base["status"]    = "running" if self._running else "stopped"
        base["camera_id"] = self.camera.camera_id
        base["colab_url"] = self.colab_url
        return base

    # ── Main Loop ─────────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
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

                last_frame_time = time.monotonic()
                await self._send_frame(frame.frame)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.stats.errors += 1
                logger.error(f"ColabPipeline loop error: {e}", exc_info=True)
                await asyncio.sleep(1.0)

    async def _send_frame(self, frame_bgr) -> None:
        """Kadrni JPEG ga aylantirib Colabga yuborish."""
        import cv2
        import numpy as np

        try:
            # Kichraytirish (tarmoq tejash uchun)
            if self.frame_scale > 1:
                h, w = frame_bgr.shape[:2]
                frame_bgr = cv2.resize(frame_bgr, (w // self.frame_scale, h // self.frame_scale))

            # JPEG encode
            ok, buf = cv2.imencode(
                ".jpg", frame_bgr,
                [int(cv2.IMWRITE_JPEG_QUALITY), self.jpeg_quality]
            )
            if not ok:
                self.stats.errors += 1
                return

            jpg_bytes = buf.tobytes()

            # Colabga yuborish
            t0 = time.monotonic()
            resp = await self._client.post(
                self.frame_url,
                content=jpg_bytes,
                headers=self._headers,
            )
            latency_ms = (time.monotonic() - t0) * 1000
            self.stats.add_latency(latency_ms)

            if resp.status_code == 200:
                self.stats.sent_frames += 1
                data = resp.json()
                logger.debug(
                    f"[colab] fno={data.get('fno')} "
                    f"fps={data.get('fps')} "
                    f"tracks={data.get('tracks')} "
                    f"latency={latency_ms:.0f}ms"
                )
            else:
                self.stats.errors += 1
                logger.warning(f"[colab] frame rejected: {resp.status_code}")

        except httpx.TimeoutException:
            self.stats.skipped_frames += 1
            # Timeout bo'lsa kadrni o'tkazib yuboramiz — keyingisi bor
        except httpx.ConnectError:
            self.stats.errors += 1
            logger.warning("[colab] Colab bilan aloqa uzildi, qayta urinmoqda...")
            await asyncio.sleep(2.0)
        except Exception as e:
            self.stats.errors += 1
            logger.error(f"[colab] send_frame xato: {e}")