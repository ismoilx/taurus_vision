"""
Taurus Vision — Camera Management API

Camera CRUD, start/stop, health — barcha operatsiyalar
camera_manager (in-memory singleton) orqali bajariladi.

API kontrakt (testlar bilan kelishilgan):
  POST   /cameras/          → 201  {"success", "camera_id", "message", "data"}
  GET    /cameras/          → 200  [camera_id, ...]          # ID lar ro'yxati
  GET    /cameras/stats/all → 200  {camera_id: stats, ...}
  GET    /cameras/health    → 200  {total_cameras, healthy_cameras, ...}
  POST   /cameras/start-all → 200  {"success", "data": {"started", "total"}}
  POST   /cameras/stop-all  → 200  {"success", "data": {"stopped"}}
  DELETE /cameras/{id}      → 200  {"success", "message"}
  GET    /cameras/{id}/stats→ 200  {camera_id, frame_count, fps, running, ...}
  POST   /cameras/{id}/start→ 200  {"success", "message"}
  POST   /cameras/{id}/stop → 200  {"success", "message"}
  GET    /cameras/{id}/stream → multipart/x-mixed-replace MJPEG

HTTP xatolar:
  400 — biznes qoida buzilishi (masalan, RTSP url yo'q)
  404 — kamera topilmadi
  500 — takroriy camera_id yoki boshqa kutilmagan xato
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional, AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import CurrentUser, CurrentManager
from app.core.database import get_db
from app.core.security import decode_token
from app.repositories.user_repository import UserRepository
from app.services.camera.camera_manager import camera_manager
from app.services.camera.camera_factory import CameraFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cameras", tags=["Cameras"])


# =============================================================================
# REQUEST / RESPONSE SCHEMAS
# =============================================================================

class CameraRegisterRequest(PydanticModel):
    """
    Kamera ro'yxatga olish so'rovi.

    Umumiy maydonlar barcha turlarga tegishli.
    Tur-spesifik maydonlar ixtiyoriy — validatsiya endpoint da.
    """
    camera_id:          str  = Field(..., min_length=1, max_length=100)
    type:               str  = Field(..., pattern="^(simulated|rtsp|usb)$")
    fps:                int  = Field(10, ge=1, le=60)
    width:              int  = Field(640, ge=1)
    height:             int  = Field(480, ge=1)
    auto_start:         bool = Field(True)
    # RTSP specific
    url:                Optional[str] = None
    reconnect_interval: Optional[int] = Field(None, ge=1)
    connection_timeout: Optional[int] = Field(None, ge=1)
    # USB specific
    device_index:       Optional[int] = Field(None, ge=0)
    auto_reconnect:     Optional[bool] = None


class CameraStatsResponse(PydanticModel):
    """Kamera statistikasi javobi."""
    camera_id:   str
    running:     bool
    fps:         float
    frame_count: int
    type:        Optional[str]  = None
    resolution:  Optional[Any]  = None
    error_count: Optional[int]  = None


class CameraHealthResponse(PydanticModel):
    """Kamera tizimi sog'liq holati."""
    total_cameras:     int
    healthy_cameras:   int
    health_percentage: float
    timestamp:         str


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

def _build_camera_data(camera_id: str, cam_type: str) -> dict:
    """POST javobi uchun kamera info dict."""
    stats = camera_manager.get_camera_stats(camera_id) or {}
    return {
        "camera_id": camera_id,
        "type":      cam_type,
        "running":   stats.get("running", False),
        "fps":       stats.get("fps", 0.0),
    }


def _stats_to_response(camera_id: str, stats: dict) -> CameraStatsResponse:
    return CameraStatsResponse(
        camera_id=   camera_id,
        running=     bool(stats.get("running", False)),
        fps=         float(stats.get("fps", 0.0)),
        frame_count= int(stats.get("frame_count", 0)),
        type=        stats.get("type"),
        resolution=  stats.get("resolution"),
        error_count= stats.get("error_count"),
    )


def _require_camera(camera_id: str) -> dict:
    """
    Kamera statistikasini qaytaradi yoki 404 beradi.

    Returns:
        stats dict

    Raises:
        HTTPException 404: Kamera topilmadi.
    """
    stats = camera_manager.get_camera_stats(camera_id)
    if stats is None:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{camera_id}' topilmadi.",
        )
    return stats


# =============================================================================
# STATIC ENDPOINTS
# (aniq path — /{camera_id} pattern dan OLDIN ro'yxatda turishi shart)
# =============================================================================

@router.post("/", status_code=201, summary="Kamera ro'yxatga olish")
async def register_camera(
    body: CameraRegisterRequest,
    _: CurrentManager,
) -> dict:
    """
    Yangi kamerani ro'yxatga olish.

    CameraFactory orqali instance yaratib, camera_manager ga qo'shadi.
    auto_start=True bo'lsa kamera darhol ishga tushiriladi.

    Returns:
        {"success": True, "camera_id": ..., "message": ..., "data": {...}}

    Raises:
        400: Tur-spesifik validatsiya xatosi (masalan, RTSP url yo'q).
        500: Takroriy camera_id yoki boshqa kutilmagan xato.
    """
    # --- Tur-spesifik biznes validatsiya (422 → 400) ---
    if body.type == "rtsp" and not body.url:
        raise HTTPException(
            status_code=400,
            detail="RTSP kamera uchun 'url' maydoni majburiy.",
        )
    if body.type == "usb" and body.device_index is None:
        raise HTTPException(
            status_code=400,
            detail="USB kamera uchun 'device_index' maydoni majburiy.",
        )

    # --- Factory orqali camera instance yaratish ---
    config: dict[str, Any] = body.model_dump(exclude_none=True)
    camera = CameraFactory.create_camera(config)
    if camera is None:
        raise HTTPException(
            status_code=400,
            detail=f"Kamera konfiguratsiyasi noto'g'ri: {body.camera_id}",
        )

    # --- camera_manager ga qo'shish ---
    # Duplicate camera_id → ValueError → 500 (test kutadi)
    try:
        camera_manager.register_camera(
            camera_id=  body.camera_id,
            camera=     camera,
            auto_start= body.auto_start,
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:
        logger.error(f"Kamera ro'yxatga olishda xato [{body.camera_id}]: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "success":   True,
        "camera_id": body.camera_id,
        "message":   f"Camera '{body.camera_id}' registered successfully.",
        "data":      _build_camera_data(body.camera_id, body.type),
    }


@router.get("/", summary="Barcha kameralar ID ro'yxati")
async def list_cameras(
    _: CurrentUser,
) -> list[str]:
    """
    Ro'yxatga olingan barcha kamera ID larini qaytaradi.

    Returns:
        ["CAM-001", "CAM-002", ...]
    """
    return camera_manager.list_cameras()


@router.get("/stats/all", summary="Barcha kameralar statistikasi")
async def get_all_stats(
    _: CurrentUser,
) -> dict[str, CameraStatsResponse]:
    """
    Barcha kameralarning statistikasini bir so'rovda qaytaradi.

    Returns:
        {"CAM-001": {stats}, "CAM-002": {stats}, ...}
    """
    return {
        cid: _stats_to_response(cid, s)
        for cid, s in camera_manager.get_all_stats().items()
    }


@router.get("/health", response_model=CameraHealthResponse, summary="Kamera tizimi sog'lig'i")
async def camera_health(
    _: CurrentUser,
) -> CameraHealthResponse:
    """
    Kamera tizimining umumiy sog'liq holatini qaytaradi.

    healthy_cameras = hozir ishlayotgan (running=True) kameralar soni.
    """
    all_stats  = camera_manager.get_all_stats()
    total      = len(all_stats)
    healthy    = sum(1 for s in all_stats.values() if s.get("running", False))
    return CameraHealthResponse(
        total_cameras=     total,
        healthy_cameras=   healthy,
        health_percentage= (healthy / total * 100.0) if total > 0 else 0.0,
        timestamp=         datetime.now(timezone.utc).isoformat(),
    )


@router.post("/start-all", summary="Barcha kameralarni ishga tushirish")
async def start_all_cameras(
    _: CurrentManager,
) -> dict:
    """
    Barcha ro'yxatdagi kameralarni ishga tushiradi.

    Returns:
        {"success": True, "data": {"started": N, "total": N}}
    """
    total   = len(camera_manager.list_cameras())
    started = camera_manager.start_all()
    return {
        "success": True,
        "data":    {"started": started, "total": total},
    }


@router.post("/stop-all", summary="Barcha kameralarni to'xtatish")
async def stop_all_cameras(
    _: CurrentManager,
) -> dict:
    """
    Barcha kameralarni to'xtatadi.

    Returns:
        {"success": True, "data": {"stopped": N}}
    """
    stopped = camera_manager.stop_all()
    return {
        "success": True,
        "data":    {"stopped": stopped},
    }


# =============================================================================
# DYNAMIC ENDPOINTS /{camera_id}
# (statik endpointlardan KEYIN ro'yxatda turishi shart)
# =============================================================================

@router.get("/{camera_id}/stats", response_model=CameraStatsResponse, summary="Kamera statistikasi")
async def get_camera_stats(
    camera_id: str,
    _: CurrentUser,
) -> CameraStatsResponse:
    """
    Bitta kamera statistikasini qaytaradi.

    Raises:
        404: Kamera topilmadi.
    """
    stats = _require_camera(camera_id)
    return _stats_to_response(camera_id, stats)


@router.post("/{camera_id}/start", summary="Kamerani ishga tushirish")
async def start_camera(
    camera_id: str,
    _: CurrentManager,
) -> dict:
    """
    Kamerani ishga tushiradi.

    Raises:
        500: Kamera topilmadi yoki ishga tushmadi.
    """
    ok = camera_manager.start_camera(camera_id)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Camera '{camera_id}' ishga tushmadi yoki topilmadi.",
        )
    return {
        "success": True,
        "message": f"Camera '{camera_id}' started successfully.",
    }


@router.post("/{camera_id}/stop", summary="Kamerani to'xtatish")
async def stop_camera(
    camera_id: str,
    _: CurrentManager,
) -> dict:
    """
    Kamerani to'xtatadi.

    Raises:
        500: Kamera topilmadi yoki to'xtatilmadi.
    """
    ok = camera_manager.stop_camera(camera_id)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Camera '{camera_id}' to'xtatilmadi yoki topilmadi.",
        )
    return {
        "success": True,
        "message": f"Camera '{camera_id}' stopped successfully.",
    }


@router.delete("/{camera_id}", status_code=200, summary="Kamerani o'chirish")
async def unregister_camera(
    camera_id: str,
    _: CurrentManager,
) -> dict:
    """
    Kamerani to'xtatib, ro'yxatdan o'chiradi.

    Raises:
        404: Kamera topilmadi.
    """
    if camera_manager.get_camera(camera_id) is None:
        raise HTTPException(
            status_code=404,
            detail=f"Camera '{camera_id}' topilmadi.",
        )
    ok = camera_manager.unregister_camera(camera_id)
    if not ok:
        raise HTTPException(
            status_code=500,
            detail=f"Camera '{camera_id}' o'chirib bo'lmadi.",
        )
    return {
        "success": True,
        "message": f"Camera '{camera_id}' unregistered successfully.",
    }


# =============================================================================
# MJPEG LIVE STREAM  (schema dan tashqarida — auth query param orqali)
# =============================================================================

_FONT   = cv2.FONT_HERSHEY_SIMPLEX
_JPEG_Q = 75
_MAX_W  = 1280


def _no_signal_frame(camera_id: str) -> bytes:
    """Kamera mavjud bo'lmasa yoki to'xtatilganda ko'rsatiladigan kadr."""
    f = np.zeros((360, 640, 3), dtype=np.uint8)
    f[:] = (18, 18, 28)
    for i in range(0, 640, 40):
        cv2.line(f, (i, 0), (i, 360), (32, 32, 42), 1)
    for i in range(0, 360, 40):
        cv2.line(f, (0, i), (640, i), (32, 32, 42), 1)
    cv2.putText(f, "NO SIGNAL", (198, 210), _FONT, 1.1, (90, 90, 110), 2, cv2.LINE_AA)
    cv2.putText(f, f"ID: {camera_id}", (198, 250), _FONT, 0.55, (60, 60, 80), 1, cv2.LINE_AA)
    _, j = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 50])
    return j.tobytes()


async def _mjpeg_generator(camera_id: str) -> AsyncGenerator[bytes, None]:
    """MJPEG kadr generatori — camera_manager.get_camera() orqali."""
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    no_sig   = _no_signal_frame(camera_id)

    while True:
        try:
            cam = camera_manager.get_camera(camera_id)
            if cam is None or not cam.is_opened():
                yield boundary + no_sig + b"\r\n"
                await asyncio.sleep(1.0)
                continue

            raw = await asyncio.to_thread(cam.get_frame)
            if raw is None:
                yield boundary + no_sig + b"\r\n"
                await asyncio.sleep(1.0)
                continue

            frame = raw.copy()
            h, w  = frame.shape[:2]
            if w > _MAX_W:
                sc    = _MAX_W / w
                frame = cv2.resize(frame, (int(w * sc), int(h * sc)),
                                   interpolation=cv2.INTER_LINEAR)

            ok, j = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
            if ok:
                yield boundary + j.tobytes() + b"\r\n"

            await asyncio.sleep(0.04)   # ~25 FPS

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"[{camera_id}] MJPEG xato: {exc}")
            await asyncio.sleep(0.5)


@router.get("/{camera_id}/stream", include_in_schema=False)
async def stream_mjpeg(
    camera_id: str,
    token:     Optional[str]    = Query(default=None),
    db:        AsyncSession     = Depends(get_db),
) -> StreamingResponse:
    """MJPEG live stream — token query param bilan autentifikatsiya."""
    if not token:
        return Response(status_code=401, content="Token kerak")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("access token kerak")
        uid  = int(payload.get("sub", 0))
        user = await UserRepository(db).get_by_id(uid)
        if not user or not user.is_active:
            return Response(status_code=403, content="Ruxsat yo'q")
    except Exception:
        return Response(status_code=401, content="Token noto'g'ri")

    return StreamingResponse(
        _mjpeg_generator(camera_id),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control":     "no-cache, no-store, must-revalidate",
            "Pragma":            "no-cache",
            "X-Accel-Buffering": "no",
        },
    )