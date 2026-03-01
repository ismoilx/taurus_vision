"""
Taurus Vision — Camera Management API

Asosiy tuzatishlar:
  1. MJPEG stream frame_cache dan oladi (race condition yo'q)
  2. Pipeline stop — timeout bilan (osilib qolmaydi)
  3. Barcha holat pipeline_manager dan (camera_manager olib tashlangan)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError, BusinessRuleViolationError
from app.api.v1.deps import CurrentUser, CurrentManager
from app.repositories.camera_repository import CameraRepository
from app.repositories.user_repository import UserRepository
from app.models.camera import CameraType
from app.services.pipeline_manager import get_pipeline_manager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/cameras", tags=["Cameras"])


# ─── Schemas ─────────────────────────────────────────────────────────────────

class CameraCreateRequest(PydanticModel):
    name:      str        = Field(..., min_length=1, max_length=100)
    type:      CameraType = Field(CameraType.SIMULATED)
    source:    Optional[str] = None
    device_id: Optional[int] = Field(None, ge=0)
    fps:       int        = Field(10, ge=1, le=60)
    enabled:   bool       = Field(True)


class CameraResponse(PydanticModel):
    id:        str
    name:      str
    type:      CameraType
    source:    Optional[str]
    device_id: Optional[int]
    fps:       int
    enabled:   bool
    status:    str
    model_config = {"from_attributes": True}


class CameraStatusResponse(PydanticModel):
    camera_id:       str
    is_active:       bool
    fps:             float
    frames_captured: int
    last_frame_time: Optional[str]
    error:           Optional[str]


class CameraHealthResponse(PydanticModel):
    total_cameras:     int
    enabled_cameras:   int
    active_cameras:    int
    health_percentage: float
    timestamp:         str


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _pm_status(camera_id: str) -> str:
    return "active" if get_pipeline_manager().is_running(camera_id) else "inactive"


def _build_response(camera) -> CameraResponse:
    return CameraResponse(
        id=camera.camera_id, name=camera.name, type=camera.type,
        source=camera.source, device_id=camera.device_index,
        fps=camera.fps, enabled=camera.is_enabled,
        status=_pm_status(camera.camera_id),
    )


def _build_stats(camera_id: str) -> CameraStatusResponse:
    pm    = get_pipeline_manager()
    entry = pm.get_status(camera_id)
    if not entry.get("running"):
        return CameraStatusResponse(
            camera_id=camera_id, is_active=False,
            fps=0.0, frames_captured=0,
            last_frame_time=None, error=None,
        )
    stats = entry.get("stats") or {}
    return CameraStatusResponse(
        camera_id=camera_id, is_active=True,
        fps=float(stats.get("fps", 0.0)),
        frames_captured=int(stats.get("processed_frames", 0)),
        last_frame_time=datetime.utcnow().isoformat(),
        error=None,
    )


# ─── Static endpoints ────────────────────────────────────────────────────────

@router.get("/", response_model=list[CameraResponse])
async def list_cameras(
    only_enabled: bool = False,
    _: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
):
    cameras = await CameraRepository(db).get_all(only_enabled=only_enabled)
    return [_build_response(c) for c in cameras]


@router.post("/", response_model=CameraResponse, status_code=201)
async def create_camera(
    body: CameraCreateRequest,
    _: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
):
    camera = await CameraRepository(db).create(
        name=body.name, camera_type=body.type, source=body.source,
        device_index=body.device_id, fps=body.fps, is_enabled=body.enabled,
    )
    if body.enabled:
        pm = get_pipeline_manager()
        ok, reason = await pm.start_camera(
            camera_id=camera.camera_id, camera_type=camera.type.value,
            source=camera.source, device_index=camera.device_index, fps=camera.fps,
        )
        if not ok:
            logger.warning(f"Camera yaratildi lekin pipeline ishlamadi: {reason}")
    return _build_response(camera)


@router.get("/stats/all", response_model=dict[str, CameraStatusResponse])
async def get_all_stats(
    _: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
):
    cameras = await CameraRepository(db).get_all()
    return {c.camera_id: _build_stats(c.camera_id) for c in cameras}


@router.get("/health", response_model=CameraHealthResponse)
async def camera_health(
    _: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
):
    all_cams  = await CameraRepository(db).get_all()
    running   = get_pipeline_manager().list_running()
    active    = sum(1 for c in all_cams if c.camera_id in running)
    total     = len(all_cams)
    return CameraHealthResponse(
        total_cameras=total,
        enabled_cameras=len([c for c in all_cams if c.is_enabled]),
        active_cameras=active,
        health_percentage=(active / total * 100) if total else 0.0,
        timestamp=datetime.utcnow().isoformat(),
    )


@router.post("/start-all", response_model=dict)
async def start_all(
    _: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
):
    cameras = await CameraRepository(db).get_all(only_enabled=True)
    pm = get_pipeline_manager()
    started, failed = 0, []
    for cam in cameras:
        if pm.is_running(cam.camera_id):
            started += 1; continue
        ok, reason = await pm.start_camera(
            camera_id=cam.camera_id, camera_type=cam.type.value,
            source=cam.source, device_index=cam.device_index, fps=cam.fps,
        )
        if ok: started += 1
        else: failed.append({"camera_id": cam.camera_id, "reason": reason})
    return {"started": started, "total": len(cameras), "failed": failed}


@router.post("/stop-all", response_model=dict)
async def stop_all(_: CurrentManager = ...):
    stopped = await get_pipeline_manager().stop_all()
    return {"stopped": stopped}


@router.get("/detect-webcams", response_model=list[dict])
async def detect_webcams(_: CurrentUser = ...):
    found: list[dict] = []
    def _scan():
        for i in range(5):
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    found.append({
                        "device_index": i,
                        "label": f"Webcam {i} (/dev/video{i})",
                        "suggested_name": f"Webcam {i}",
                    })
                    cap.release()
            except Exception:
                pass
    await asyncio.to_thread(_scan)
    return found


# ─── Dynamic endpoints /{camera_id} ─────────────────────────────────────────

@router.delete("/{camera_id}", status_code=204)
async def delete_camera(
    camera_id: str,
    _: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
):
    repo = CameraRepository(db)
    await repo.get_by_camera_id_or_raise(camera_id)
    pm = get_pipeline_manager()
    if pm.is_running(camera_id):
        await pm.stop_camera(camera_id)
    await repo.delete(camera_id)


@router.get("/{camera_id}/stats", response_model=CameraStatusResponse)
async def camera_stats(
    camera_id: str,
    _: CurrentUser = ...,
    db: AsyncSession = Depends(get_db),
):
    await CameraRepository(db).get_by_camera_id_or_raise(camera_id)
    return _build_stats(camera_id)


@router.post("/{camera_id}/start", response_model=dict)
async def start_camera(
    camera_id: str,
    _: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
):
    camera = await CameraRepository(db).get_by_camera_id_or_raise(camera_id)
    pm = get_pipeline_manager()
    if pm.is_running(camera_id):
        raise BusinessRuleViolationError(message=f"Pipeline '{camera_id}' allaqachon ishlayapti")
    ok, reason = await pm.start_camera(
        camera_id=camera.camera_id, camera_type=camera.type.value,
        source=camera.source, device_index=camera.device_index, fps=camera.fps,
    )
    if not ok:
        raise BusinessRuleViolationError(message=f"Pipeline ishga tushmadi: {reason}")
    return {"success": True, "camera_id": camera_id}


@router.post("/{camera_id}/stop", response_model=dict)
async def stop_camera(
    camera_id: str,
    _: CurrentManager = ...,
    db: AsyncSession = Depends(get_db),
):
    await CameraRepository(db).get_by_camera_id_or_raise(camera_id)
    pm = get_pipeline_manager()
    if not pm.is_running(camera_id):
        return {"success": True, "camera_id": camera_id, "message": "Allaqachon to'xtatilgan"}
    ok, reason = await pm.stop_camera(camera_id)
    return {"success": ok, "camera_id": camera_id, "message": "" if ok else reason}


# ─── MJPEG Stream ────────────────────────────────────────────────────────────
#
# MUAMMO (ESKI):
#   MJPEG generator va DetectionPipeline bir vaqtda camera.get_frame() chaqirar edi.
#   OpenCV VideoCapture thread-safe emas → race condition → 1s da crash.
#
# YECHIM (YANGI):
#   DetectionPipeline har frame olganda pm.update_latest_frame(id, frame) chaqiradi.
#   MJPEG generator shu cache dan oladi (pm.get_latest_frame).
#   Ikki joy bitta VideoCapture ga tegmaydi.

_FONT      = cv2.FONT_HERSHEY_SIMPLEX
_CLR_ID    = (34, 197, 94)
_CLR_UNID  = (239, 68, 68)
_JPEG_Q    = 75
_MAX_W     = 1280


def _draw_bbox(frame: np.ndarray, det: dict) -> np.ndarray:
    h, w = frame.shape[:2]
    b    = det["bbox"]
    tag  = det.get("animal_tag")
    conf = det.get("confidence", 0.0)
    idd  = tag is not None and tag != "UNKNOWN"
    col  = _CLR_ID if idd else _CLR_UNID

    x1 = max(0, int(b.get("x", 0) * w))
    y1 = max(0, int(b.get("y", 0) * h))
    x2 = min(w-1, int((b.get("x",0)+b.get("w",0.1)) * w))
    y2 = min(h-1, int((b.get("y",0)+b.get("h",0.2)) * h))
    if x2 <= x1 or y2 <= y1:
        return frame

    cv2.rectangle(frame, (x1,y1), (x2,y2), col, 2)
    cl = min(18, (x2-x1)//4, (y2-y1)//4)
    for px, py in [(x1,y1),(x2,y1),(x1,y2),(x2,y2)]:
        cv2.line(frame,(px,py),(px+(cl if px==x1 else -cl),py),col,3)
        cv2.line(frame,(px,py),(px,py+(cl if py==y1 else -cl)),col,3)

    txt = f"{tag if idd else '?'}  {conf:.0%}"
    (tw,th),bl = cv2.getTextSize(txt, _FONT, 0.55, 2)
    p = 3
    ly = max(y1-bl-p*2, th+bl+p*2)
    ov = frame.copy()
    cv2.rectangle(ov,(x1,ly-th-bl-p*2),(x1+tw+p*2,ly),col,-1)
    cv2.addWeighted(ov,0.7,frame,0.3,0,frame)
    cv2.putText(frame,txt,(x1+p,ly-bl-p),_FONT,0.55,(255,255,255),2,cv2.LINE_AA)
    return frame


def _no_signal_frame(camera_id: str) -> bytes:
    """Pipeline to'xtatilganda ko'rsatiladigan kadr."""
    f = np.zeros((360,640,3), dtype=np.uint8)
    f[:] = (18,18,28)
    for i in range(0,640,40): cv2.line(f,(i,0),(i,360),(32,32,42),1)
    for i in range(0,360,40): cv2.line(f,(0,i),(640,i),(32,32,42),1)
    cv2.putText(f,"NO SIGNAL",(198,210),_FONT,1.1,(90,90,110),2,cv2.LINE_AA)
    cv2.putText(f,f"ID: {camera_id}",(198,250),_FONT,0.55,(60,60,80),1,cv2.LINE_AA)
    cv2.putText(f,"Pipeline to'xtatilgan",(165,280),_FONT,0.55,(50,50,70),1,cv2.LINE_AA)
    _, j = cv2.imencode(".jpg", f, [cv2.IMWRITE_JPEG_QUALITY, 50])
    return j.tobytes()


async def _mjpeg_generator(camera_id: str) -> AsyncGenerator[bytes, None]:
    """
    MJPEG kadr generatori.

    Frame manbai: pm.get_latest_frame(camera_id)
    - Pipeline aktiv: DetectionPipeline cache ga yozadi → biz o'qiymiz
    - Pipeline to'xtatilgan: no-signal kadr (1 FPS)

    MUHIM: camera.get_frame() CHAQIRILMAYDI — race condition yo'q.
    """
    pm       = get_pipeline_manager()
    boundary = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
    no_sig   = _no_signal_frame(camera_id)

    while True:
        try:
            raw = pm.get_latest_frame(camera_id)

            if raw is None:
                # Pipeline hali kadr bermaganida yoki to'xtatilganda
                yield boundary + no_sig + b"\r\n"
                await asyncio.sleep(1.0)
                continue

            frame = raw.copy()

            # O'lchamni cheklaymiz
            h, w = frame.shape[:2]
            if w > _MAX_W:
                sc    = _MAX_W / w
                frame = cv2.resize(frame, (int(w*sc), int(h*sc)),
                                   interpolation=cv2.INTER_LINEAR)

            # Bbox overlay
            det = pm.get_latest_detection(camera_id)
            if det:
                frame = _draw_bbox(frame, det)

            ok, j = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, _JPEG_Q])
            if ok:
                yield boundary + j.tobytes() + b"\r\n"

            await asyncio.sleep(0.04)   # ~25 FPS

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"[{camera_id}] MJPEG xato: {exc}")
            await asyncio.sleep(0.5)


@router.get("/{camera_id}/stream")
async def stream_mjpeg(
    camera_id: str,
    token: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    if not token:
        return Response(status_code=401, content="Token kerak")
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise AuthenticationError("Access token kerak")
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