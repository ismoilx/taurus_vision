"""
Taurus Vision — Camera Management API

/api/v1/cameras/ prefiksi ostidagi barcha kamera endpointlari.

ENDPOINTLAR:
    GET    /cameras/           — Barcha kameralar ro'yxati (DB + runtime holat)
    POST   /cameras/           — Yangi kamera qo'shish (DB ga saqlash + CameraManager ga ro'yxatdan o'tkazish)
    DELETE /cameras/{id}       — Kamerani o'chirish (DB + CameraManager dan)
    GET    /cameras/stats/all  — Barcha kameralar runtime statistikasi
    GET    /cameras/health     — Kamera tizimi sog'liq holati
    POST   /cameras/{id}/start — Kamerani ishga tushirish (CameraManager)
    POST   /cameras/{id}/stop  — Kamerani to'xtatish (CameraManager)

DB vs RUNTIME:
    DB (Camera model):       konfiguratsiya — camera_id, name, type, source, fps
    CameraManager (xotira):  runtime holat  — is_active, fps, frames_captured

AUTENTIFIKATSIYA:
    Barcha endpointlar: VIEWER+ (get_current_active_user)
    Yozish operatsiyalari: MANAGER+ (require_manager)
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager
from app.repositories.camera_repository import CameraRepository
from app.models.camera import CameraType
from app.services.camera.camera_manager import camera_manager
from app.services.camera.camera_factory import CameraFactory

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