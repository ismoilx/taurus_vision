"""
Taurus Vision — Camera Management API

/api/v1/cameras/ prefiksi ostidagi barcha kamera endpointlari.

ENDPOINTLAR:
    GET    /cameras/              — Barcha kameralar ro'yxati (DB + runtime holat)
    POST   /cameras/              — Yangi kamera qo'shish
    DELETE /cameras/{id}          — Kamerani o'chirish
    GET    /cameras/stats/all     — Barcha kameralar runtime statistikasi
    GET    /cameras/health        — Kamera tizimi sog'liq holati
    POST   /cameras/{id}/start    — Kamerani ishga tushirish
    POST   /cameras/{id}/stop     — Kamerani to'xtatish
    GET    /cameras/{id}/stream   — MJPEG video stream (bbox overlay bilan)

DB vs RUNTIME:
    DB (Camera model):       konfiguratsiya — camera_id, name, type, source, fps
    CameraManager (xotira):  runtime holat  — is_active, fps, frames_captured

AUTENTIFIKATSIYA:
    Barcha endpointlar: VIEWER+ (get_current_active_user)
    Yozish operatsiyalari: MANAGER+ (require_manager)
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, AsyncGenerator

import cv2
import numpy as np
from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import decode_token
from app.core.exceptions import AuthenticationError
from app.api.v1.deps import CurrentUser, CurrentManager
from app.repositories.camera_repository import CameraRepository
from app.repositories.user_repository import UserRepository
from app.models.camera import CameraType
from app.services.camera.camera_manager import camera_manager
from app.services.camera.camera_factory import CameraFactory
from app.services.pipeline_manager import get_pipeline_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cameras", tags=["Cameras"])


# =============================================================================
# PYDANTIC SCHEMAS
# =============================================================================

class CameraCreateRequest(PydanticModel):
    """
    Yangi kamera qo'shish uchun request body.

    Frontend AddCameraModal yuboradigan formatga to'liq mos.
    """
    name:       str        = Field(..., min_length=1, max_length=100, description="Kamera nomi")
    type:       CameraType = Field(CameraType.SIMULATED,              description="simulated | usb | rtsp")
    source:     Optional[str] = Field(None,                           description="RTSP URL (rtsp uchun)")
    device_id:  Optional[int] = Field(None, ge=0,                     description="USB device indeksi")
    fps:        int        = Field(10,  ge=1, le=60,                  description="FPS (1–60)")
    enabled:    bool       = Field(True,                              description="Darhol faollashtirish")


class CameraResponse(PydanticModel):
    """
    Kamera konfiguratsiyasi response.

    Frontend CameraConfig interfeysi bilan to'liq mos:
        id       → camera_id (string)
        name     → name
        type     → type
        source   → source
        device_id → device_index
        fps      → fps
        enabled  → is_enabled
        status   → runtime holat
    """
    id:         str
    name:       str
    type:       CameraType
    source:     Optional[str]
    device_id:  Optional[int]
    fps:        int
    enabled:    bool
    status:     str  # 'active' | 'inactive' | 'error'

    model_config = {"from_attributes": True}


class CameraStatusResponse(PydanticModel):
    """
    Kamera runtime statistikasi.

    Frontend CameraStatus interfeysi bilan mos.
    """
    camera_id:       str
    is_active:       bool
    fps:             float
    frames_captured: int
    last_frame_time: Optional[str]
    error:           Optional[str]


class CameraHealthResponse(PydanticModel):
    """Kamera tizimi sog'liq holati."""
    total_cameras:     int
    enabled_cameras:   int
    active_cameras:    int
    health_percentage: float
    timestamp:         str


# =============================================================================
# HELPERS
# =============================================================================

def _runtime_status(camera_id: str) -> str:
    """
    CameraManager dan runtime holatni oladi.

    Returns:
        'active'   — kamera ishlayapti
        'inactive' — kamera to'xtatilgan
        'error'    — kamera xatolikda
    """
    try:
        cam = camera_manager.get_camera(camera_id)
        if cam is None:
            return "inactive"
        if cam.is_opened():
            return "active"
        return "inactive"
    except Exception:
        return "error"


def _build_camera_response(camera) -> CameraResponse:
    """Camera ORM model → CameraResponse Pydantic."""
    return CameraResponse(
        id        = camera.camera_id,
        name      = camera.name,
        type      = camera.type,
        source    = camera.source,
        device_id = camera.device_index,
        fps       = camera.fps,
        enabled   = camera.is_enabled,
        status    = _runtime_status(camera.camera_id),
    )


def _to_status_response(camera_id: str, raw: dict) -> CameraStatusResponse:
    """
    CameraManager.get_stats() raw dict → CameraStatusResponse.

    SimulatedCamera.get_stats() qaytaradi:
        {"camera_id", "type", "connected", "running",
         "frame_count", "error_count", "fps", "resolution", ...}

    Bularni frontend kutgan formatga o'giramiz.
    """
    is_active       = raw.get("running", False) or raw.get("connected", False)
    frames_captured = raw.get("frame_count", 0) or raw.get("frames_captured", 0)
    fps             = float(raw.get("fps", 0.0))
    error           = raw.get("error", None) or (
        f"{raw.get('error_count', 0)} xato" if raw.get("error_count", 0) > 0 else None
    )

    return CameraStatusResponse(
        camera_id       = camera_id,
        is_active       = is_active,
        fps             = fps,
        frames_captured = frames_captured,
        last_frame_time = datetime.utcnow().isoformat() if is_active else None,
        error           = error,
    )


def _start_camera_in_manager(camera_id: str, camera_type: CameraType,
                               source: Optional[str], device_index: Optional[int],
                               fps: int) -> bool:
    """
    CameraManager da kamerani ro'yxatdan o'tkazib ishga tushiradi.

    Agar allaqachon ro'yxatda bo'lsa — o'tkazib yuboradi.

    Returns:
        True — muvaffaqiyatli, False — xatolik
    """
    try:
        if camera_id in camera_manager.list_cameras():
            logger.debug(f"Camera {camera_id} allaqachon CameraManager da")
            return True

        config = {
            "camera_id": camera_id,
            "type":      camera_type.value,
            "fps":       fps,
        }
        if source:       config["url"]          = source
        if device_index is not None: config["device_index"] = device_index

        camera_obj = CameraFactory.create_camera(config)
        if camera_obj is None:
            logger.error(f"CameraFactory {camera_id} uchun None qaytardi")
            return False

        camera_manager.register_camera(
            camera_id  = camera_id,
            camera     = camera_obj,
            auto_start = True,
        )
        logger.info(f"Camera {camera_id} CameraManager ga qo'shildi va ishga tushirildi")
        return True

    except Exception as exc:
        logger.error(
            f"CameraManager ga qo'shishda xato: {exc}",
            extra={"extra_data": {"camera_id": camera_id}},
        )
        return False


# =============================================================================
# ENDPOINTS — STATIC (dynamic dan oldin turishi shart)
# =============================================================================

@router.get(
    "/",
    response_model=list[CameraResponse],
    status_code=status.HTTP_200_OK,
    summary="Barcha kameralar ro'yxati",
    description=(
        "DB da saqlangan barcha kamera konfiguratsiyalarini qaytaradi. "
        "Har bir kamera uchun runtime holat (active/inactive/error) ham qo'shiladi."
    ),
)
async def list_cameras(
    only_enabled: bool             = False,
    current_user: CurrentUser      = ...,
    db:           AsyncSession     = Depends(get_db),
) -> list[CameraResponse]:
    """
    Barcha kameralar ro'yxati — DB + runtime holat.

    Args:
        only_enabled: True bo'lsa faqat yoqilgan kameralar
        current_user: Autentifikatsiya tekshiruvi
        db:           DB session

    Returns:
        List[CameraResponse] — konfiguratsiya + runtime holat
    """
    repo    = CameraRepository(db)
    cameras = await repo.get_all(only_enabled=only_enabled)
    return [_build_camera_response(c) for c in cameras]


@router.post(
    "/",
    response_model=CameraResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Yangi kamera qo'shish",
    description=(
        "Yangi kamera konfiguratsiyasini DB ga saqlaydi va "
        "enabled=True bo'lsa darhol CameraManager ga ro'yxatdan o'tkazadi."
    ),
)
async def create_camera(
    body:         CameraCreateRequest,
    current_user: CurrentManager   = ...,
    db:           AsyncSession     = Depends(get_db),
) -> CameraResponse:
    """
    Yangi kamera yaratish.

    Args:
        body:         Kamera konfiguratsiyasi
        current_user: MANAGER yoki ADMIN talab qilinadi
        db:           DB session

    Returns:
        Yaratilgan CameraResponse

    Raises:
        409: camera_id allaqachon mavjud
    """
    repo   = CameraRepository(db)
    camera = await repo.create(
        name         = body.name,
        camera_type  = body.type,
        source       = body.source,
        device_index = body.device_id,
        fps          = body.fps,
        is_enabled   = body.enabled,
    )

    # Enabled bo'lsa darhol CameraManager ga qo'shish
    if body.enabled:
        _start_camera_in_manager(
            camera_id    = camera.camera_id,
            camera_type  = camera.type,
            source       = camera.source,
            device_index = camera.device_index,
            fps          = camera.fps,
        )

    return _build_camera_response(camera)


@router.get(
    "/stats/all",
    response_model=dict[str, CameraStatusResponse],
    status_code=status.HTTP_200_OK,
    summary="Barcha kameralar runtime statistikasi",
    description=(
        "CameraManager dan barcha kameralarning real-time holatini oladi. "
        "Frontend dashboard uchun har 3 soniyada so'raladi."
    ),
)
async def get_all_stats(
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> dict[str, CameraStatusResponse]:
    """
    Barcha kameralar statistikasi.

    DB dagi kameralar ro'yxatidan boshlab,
    har biri uchun CameraManager dan runtime ma'lumot oladi.

    Returns:
        Dict[camera_id, CameraStatusResponse]
    """
    repo    = CameraRepository(db)
    cameras = await repo.get_all()

    result: dict[str, CameraStatusResponse] = {}

    for cam in cameras:
        try:
            raw = camera_manager.get_camera_stats(cam.camera_id)
            if raw is not None:
                result[cam.camera_id] = _to_status_response(cam.camera_id, raw)
            else:
                # CameraManager da yo'q — DB da bor lekin run etilmagan
                result[cam.camera_id] = CameraStatusResponse(
                    camera_id       = cam.camera_id,
                    is_active       = False,
                    fps             = 0.0,
                    frames_captured = 0,
                    last_frame_time = None,
                    error           = None,
                )
        except Exception as exc:
            logger.warning(f"Stats olishda xato {cam.camera_id}: {exc}")
            result[cam.camera_id] = CameraStatusResponse(
                camera_id       = cam.camera_id,
                is_active       = False,
                fps             = 0.0,
                frames_captured = 0,
                last_frame_time = None,
                error           = str(exc),
            )

    return result


@router.get(
    "/health",
    response_model=CameraHealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Kamera tizimi sog'lig'i",
)
async def get_camera_health(
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> CameraHealthResponse:
    """
    Kamera tizimining umumiy sog'liq holati.

    Returns:
        CameraHealthResponse — jami, yoqilgan, faol kameralar soni
    """
    repo         = CameraRepository(db)
    all_cameras  = await repo.get_all()
    enabled      = [c for c in all_cameras if c.is_enabled]
    active_count = sum(
        1 for c in all_cameras
        if _runtime_status(c.camera_id) == "active"
    )

    total = len(all_cameras)

    return CameraHealthResponse(
        total_cameras     = total,
        enabled_cameras   = len(enabled),
        active_cameras    = active_count,
        health_percentage = (active_count / total * 100) if total > 0 else 0.0,
        timestamp         = datetime.utcnow().isoformat(),
    )


@router.post(
    "/start-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Barcha kameralarni ishga tushirish",
)
async def start_all_cameras(
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """Barcha yoqilgan kameralarni CameraManager orqali ishga tushiradi."""
    repo    = CameraRepository(db)
    cameras = await repo.get_all(only_enabled=True)

    started = 0
    for cam in cameras:
        ok = _start_camera_in_manager(
            camera_id    = cam.camera_id,
            camera_type  = cam.type,
            source       = cam.source,
            device_index = cam.device_index,
            fps          = cam.fps,
        )
        if ok:
            started += 1

    return {"started": started, "total": len(cameras), "message": f"{started}/{len(cameras)} kamera ishga tushdi"}


@router.post(
    "/stop-all",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Barcha kameralarni to'xtatish",
)
async def stop_all_cameras(
    current_user: CurrentManager = ...,
) -> dict:
    """Barcha faol kameralarni to'xtatadi."""
    stopped = camera_manager.stop_all()
    return {"stopped": stopped, "message": f"{stopped} kamera to'xtatildi"}


# =============================================================================
# ENDPOINTS — DYNAMIC /{camera_id} (ENG PASTDA turishi shart!)
# =============================================================================

@router.delete(
    "/{camera_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Kamerani o'chirish",
    description="Kamerani DB dan o'chiradi va CameraManager dan to'xtatadi.",
)
async def delete_camera(
    camera_id:    str,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> None:
    """
    Kamerani o'chirish.

    Args:
        camera_id:    O'chiriladigan kamera identifikatori
        current_user: MANAGER yoki ADMIN
        db:           DB session

    Raises:
        404: Kamera topilmasa
    """
    repo = CameraRepository(db)
    # EntityNotFoundError → 404 (exception_handlers da)
    await repo.get_by_camera_id_or_raise(camera_id)

    # CameraManager dan to'xtatish
    if camera_id in camera_manager.list_cameras():
        camera_manager.unregister_camera(camera_id)

    # DB dan o'chirish
    await repo.delete(camera_id)


@router.get(
    "/{camera_id}/stats",
    response_model=CameraStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Bitta kamera statistikasi",
)
async def get_camera_stats(
    camera_id:    str,
    current_user: CurrentUser  = ...,
    db:           AsyncSession = Depends(get_db),
) -> CameraStatusResponse:
    """
    Bitta kamera runtime statistikasi.

    Args:
        camera_id:    Kamera identifikatori
        current_user: Autentifikatsiya
        db:           DB session

    Returns:
        CameraStatusResponse

    Raises:
        404: Kamera topilmasa
    """
    repo = CameraRepository(db)
    await repo.get_by_camera_id_or_raise(camera_id)

    raw = camera_manager.get_camera_stats(camera_id)
    if raw is None:
        return CameraStatusResponse(
            camera_id       = camera_id,
            is_active       = False,
            fps             = 0.0,
            frames_captured = 0,
            last_frame_time = None,
            error           = None,
        )

    return _to_status_response(camera_id, raw)


@router.post(
    "/{camera_id}/start",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Kamerani ishga tushirish",
)
async def start_camera(
    camera_id:    str,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Bitta kamerani CameraManager orqali ishga tushiradi.

    Raises:
        404: Kamera topilmasa
        500: Ishga tushirib bo'lmasa
    """
    repo   = CameraRepository(db)
    camera = await repo.get_by_camera_id_or_raise(camera_id)

    ok = _start_camera_in_manager(
        camera_id    = camera.camera_id,
        camera_type  = camera.type,
        source       = camera.source,
        device_index = camera.device_index,
        fps          = camera.fps,
    )

    if not ok:
        from app.core.exceptions import BusinessRuleViolationError
        raise BusinessRuleViolationError(
            message=f"Kamera {camera_id} ni ishga tushirib bo'lmadi"
        )

    return {"success": True, "camera_id": camera_id, "message": "Kamera ishga tushirildi"}


@router.post(
    "/{camera_id}/stop",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Kamerani to'xtatish",
)
async def stop_camera(
    camera_id:    str,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Bitta kamerani to'xtatadi.

    Raises:
        404: Kamera topilmasa
    """
    repo = CameraRepository(db)
    await repo.get_by_camera_id_or_raise(camera_id)

    if camera_id not in camera_manager.list_cameras():
        return {"success": True, "camera_id": camera_id, "message": "Kamera allaqachon to'xtatilgan"}

    ok = camera_manager.stop_camera(camera_id)
    return {
        "success":   ok,
        "camera_id": camera_id,
        "message":   "Kamera to'xtatildi" if ok else "To'xtatishda xato",
    }

# =============================================================================
# MJPEG VIDEO STREAM — Kameradan real-time kadrlar + bbox overlay
# =============================================================================

# BBox rang sozlamalari
_COLOR_IDENTIFIED   = (34, 197, 94)    # Yashil — tanilgan jonivor
_COLOR_UNIDENTIFIED = (239, 68, 68)    # Qizil — tanilmagan
_COLOR_TEXT_BG      = (0, 0, 0)        # Qora — matn fon
_BOX_THICKNESS      = 2
_FONT               = cv2.FONT_HERSHEY_SIMPLEX
_FONT_SCALE         = 0.65
_FONT_THICKNESS     = 2

# Kadr hajmi cheklov (CPU tejash uchun)
_STREAM_MAX_WIDTH   = 1280
_STREAM_JPEG_QUALITY = 75


def _draw_detection_overlay(
    frame: np.ndarray,
    det: dict,
) -> np.ndarray:
    """
    Kadrga YOLO detection bbox va jonivor nomini chizadi.

    Args:
        frame: BGR numpy kadr
        det:   pipeline_manager.get_latest_detection() natijasi
                {bbox: {x,y,w,h}, animal_tag, confidence, class_name}

    Returns:
        Annotatsiya qilingan kadr (nusxa)
    """
    h, w = frame.shape[:2]
    bbox       = det["bbox"]          # normalized 0-1
    animal_tag = det.get("animal_tag")
    confidence = det.get("confidence", 0.0)
    identified = animal_tag is not None and animal_tag != "UNKNOWN"

    # Piksel koordinatalari
    x1 = int(bbox.get("x", 0) * w)
    y1 = int(bbox.get("y", 0) * h)
    x2 = int((bbox.get("x", 0) + bbox.get("w", 0.1)) * w)
    y2 = int((bbox.get("y", 0) + bbox.get("h", 0.2)) * h)

    # Chegaralarni tekshirish
    x1, y1 = max(0, x1), max(0, y1)
    x2, y2 = min(w - 1, x2), min(h - 1, y2)
    if x2 <= x1 or y2 <= y1:
        return frame

    color = _COLOR_IDENTIFIED if identified else _COLOR_UNIDENTIFIED

    # Asosiy to'rtburchak
    cv2.rectangle(frame, (x1, y1), (x2, y2), color, _BOX_THICKNESS)

    # Burchak aksenti (estetik)
    clen = min(20, (x2 - x1) // 4, (y2 - y1) // 4)
    for px, py in [(x1, y1), (x2, y1), (x1, y2), (x2, y2)]:
        dx = clen if px == x1 else -clen
        dy = clen if py == y1 else -clen
        cv2.line(frame, (px, py), (px + dx, py), color, _BOX_THICKNESS + 1)
        cv2.line(frame, (px, py), (px, py + dy), color, _BOX_THICKNESS + 1)

    # Label matn
    label     = animal_tag if identified else "?"
    conf_str  = f"{confidence:.0%}"
    text_line = f"{label}  {conf_str}"

    (tw, th), baseline = cv2.getTextSize(
        text_line, _FONT, _FONT_SCALE, _FONT_THICKNESS
    )

    # Matn fon paneli
    pad       = 4
    label_y   = max(y1 - baseline - pad * 2, th + baseline + pad * 2)
    rect_x1   = x1
    rect_y1   = label_y - th - baseline - pad * 2
    rect_x2   = x1 + tw + pad * 2
    rect_y2   = label_y

    overlay = frame.copy()
    cv2.rectangle(overlay, (rect_x1, rect_y1), (rect_x2, rect_y2), color, -1)
    cv2.addWeighted(overlay, 0.75, frame, 0.25, 0, frame)

    cv2.putText(
        frame, text_line,
        (x1 + pad, label_y - baseline - pad),
        _FONT, _FONT_SCALE,
        (255, 255, 255), _FONT_THICKNESS, cv2.LINE_AA,
    )

    return frame


async def _mjpeg_frame_generator(
    camera_id: str,
    db,
) -> AsyncGenerator[bytes, None]:
    """
    Kameradan MJPEG kadr generatori.

    - Pipeline aktiv bo'lsa: cam_service.get_frame() orqali kadrlar olinadi
    - RTSP + Simulated + USB kamera servislarini bir xil interfeys orqali ishlaydi
    - Oxirgi detection 2s dan yangi bo'lsa bbox + label overlay chiziladi
    - Pipeline to'xtatilsa: "No Signal" kadr (1 FPS)
    """
    pm        = get_pipeline_manager()
    no_signal = _make_no_signal_frame(camera_id)
    boundary  = b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"

    while True:
        try:
            cam_service = pm.get_camera_service(camera_id)

            if cam_service is None or not getattr(cam_service, "_is_active", False):
                # Pipeline to'xtatilgan — "No Signal" ko'rsatish (1 FPS yetarli)
                _, jpeg = cv2.imencode(
                    ".jpg", no_signal,
                    [cv2.IMWRITE_JPEG_QUALITY, _STREAM_JPEG_QUALITY],
                )
                yield boundary + jpeg.tobytes() + b"\r\n"
                await asyncio.sleep(1.0)
                continue

            # CameraServiceInterface.get_frame() → CameraFrame
            # Barcha kamera turlari (RTSP, Simulated, USB) uchun bir xil metod
            try:
                cam_frame = await cam_service.get_frame()
            except Exception:
                await asyncio.sleep(0.1)
                continue

            if cam_frame is None:
                await asyncio.sleep(0.05)
                continue

            # CameraFrame.frame — numpy ndarray (BGR)
            frame = cam_frame.frame.copy()

            # Hajmni cheklash (network band tejash)
            h, w = frame.shape[:2]
            if w > _STREAM_MAX_WIDTH:
                scale  = _STREAM_MAX_WIDTH / w
                new_w  = int(w * scale)
                new_h  = int(h * scale)
                frame  = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_LINEAR)

            # Bbox + label overlay (detection 2s dan yangi bo'lsa)
            det = pm.get_latest_detection(camera_id)
            if det:
                frame = _draw_detection_overlay(frame, det)

            # JPEG encode va MJPEG multipart
            ok, jpeg = cv2.imencode(
                ".jpg", frame,
                [cv2.IMWRITE_JPEG_QUALITY, _STREAM_JPEG_QUALITY],
            )
            if ok:
                yield boundary + jpeg.tobytes() + b"\r\n"

            # ~20 FPS — ko'z uchun yetarli, CPU uchun tejamli
            await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.warning(f"[{camera_id}] MJPEG generator xatosi: {exc}")
            await asyncio.sleep(0.5)


def _make_no_signal_frame(camera_id: str) -> np.ndarray:
    """'No Signal' kadr — pipeline to'xtatilganda ko'rsatiladi."""
    frame = np.zeros((360, 640, 3), dtype=np.uint8)
    frame[:] = (20, 20, 30)   # To'q ko'k-qora fon

    # Grid pattern
    for i in range(0, 640, 40):
        cv2.line(frame, (i, 0), (i, 360), (35, 35, 45), 1)
    for i in range(0, 360, 40):
        cv2.line(frame, (0, i), (640, i), (35, 35, 45), 1)

    # Kamera belgisi
    cx, cy = 320, 150
    cv2.circle(frame, (cx, cy), 45, (80, 80, 100), 2)
    cv2.circle(frame, (cx, cy), 20, (80, 80, 100), 2)
    cv2.rectangle(frame, (cx - 55, cy - 30), (cx + 55, cy + 30), (80, 80, 100), 2)
    pts = np.array([[cx + 40, cy - 25], [cx + 65, cy - 40], [cx + 65, cy + 10], [cx + 40, cy + 5]])
    cv2.polylines(frame, [pts], True, (80, 80, 100), 2)

    cv2.putText(
        frame, "NO SIGNAL",
        (200, 230), _FONT, 1.1, (120, 120, 140), 2, cv2.LINE_AA,
    )
    cv2.putText(
        frame, f"Camera: {camera_id}",
        (190, 270), _FONT, 0.6, (80, 80, 100), 1, cv2.LINE_AA,
    )
    cv2.putText(
        frame, "Pipeline to'xtatilgan",
        (175, 300), _FONT, 0.6, (70, 70, 90), 1, cv2.LINE_AA,
    )
    return frame


@router.get(
    "/{camera_id}/stream",
    summary="MJPEG video stream",
    description=(
        "Kameradan real-time video oqimi — MJPEG multipart format. "
        "Aktiv detection bo'lsa bbox va jonivor nomi overlay qilinadi. "
        "Pipeline to'xtatilgan bo'lsa 'No Signal' ko'rsatiladi. "
        "Autentifikatsiya: ?token=<jwt_access_token> query parametri."
    ),
    response_class=StreamingResponse,
    tags=["Cameras"],
)
async def stream_camera_mjpeg(
    camera_id: str,
    token:     Optional[str] = Query(
        default=None,
        description="JWT access token (?token=<access_token>)",
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Kamera MJPEG video stream endpoint.

    Browser va frontend `<img src="/api/v1/cameras/{id}/stream?token=...">` orqali ishlatadi.
    Detection pipeline aktiv bo'lsa kadrlar ustiga bbox + jonivor nomi chiziladi.

    Auth: HTTP Bearer token WebSocket kabi ?token= parametr orqali uzatiladi.
    """
    # --- Autentifikatsiya ---
    if not token:
        from fastapi.responses import Response
        return Response(status_code=401, content="Token talab qilinadi")

    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise AuthenticationError("Access token talab qilinadi")

        user_id = int(payload.get("sub", 0))
        user_repo = UserRepository(db)
        user = await user_repo.get_by_id(user_id)
        if not user or not user.is_active:
            from fastapi.responses import Response
            return Response(status_code=403, content="Ruxsat yo'q")
    except (AuthenticationError, ValueError, Exception):
        from fastapi.responses import Response
        return Response(status_code=401, content="Token noto'g'ri")

    return StreamingResponse(
        _mjpeg_frame_generator(camera_id, db),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control":   "no-cache, no-store, must-revalidate",
            "Pragma":          "no-cache",
            "Expires":         "0",
            "X-Accel-Buffering": "no",  # Nginx buffering o'chirish
        },
    )