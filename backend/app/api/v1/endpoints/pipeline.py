"""
Taurus Vision — Detection Pipeline Control API

SPRINT 10: Multi-camera pipeline boshqaruvi.

Har bir kamera o'z pipeliniga ega — parallel ishlaydi.
PipelineManager barcha pipelinelarni markaziy boshqaradi.

ENDPOINTLAR:
    POST /pipeline/start                    — Bitta kamerani ishga tushirish (DB dan)
    POST /pipeline/stop                     — Bitta kamerani to'xtatish
    POST /pipeline/stop-all                 — Barcha pipelinelarni to'xtatish
    GET  /pipeline/status                   — Barcha pipelinelar holati (umumiy)
    GET  /pipeline/status/{camera_id}       — Bitta kamera pipeline holati
    POST /pipeline/start-video              — Video fayl orqali (legacy sprint 6)
    POST /pipeline/inject                   — Dev: fake detection inject

AUTENTIFIKATSIYA:
    O'qish (GET): VIEWER+
    Yozish (POST): MANAGER+
"""

import asyncio
import logging
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status as http_status
from pydantic import BaseModel as PydanticModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.api.v1.deps import CurrentUser, CurrentManager
from app.api.v1.websocket import get_ws_manager
from app.repositories.camera_repository import CameraRepository
from app.services.pipeline_manager import get_pipeline_manager
from app.services.camera.simulated_camera import SimulatedCameraService
from app.services.detection_pipeline import DetectionPipeline
from app.services.ai.yolo_service import get_yolo_service
from app.models.animal import Animal
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement

logger = logging.getLogger(__name__)

WEIGHT_CONFIDENCE_THRESHOLD = 0.70

router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


# =============================================================================
# SCHEMAS
# =============================================================================

class PipelineStartRequest(PydanticModel):
    """Kamera pipeline ishga tushirish uchun request."""
    camera_id:   str  = Field(..., description="DB dagi kamera identifikatori")
    skip_frames: int  = Field(3, ge=1, le=20, description="Har N-chi kadrni qayta ishlash")
    colab_mode:  bool = Field(False, description="Colab GPU ga yuborish rejimi")


class ColabUrlRequest(PydanticModel):
    """Colab stream URL ni sozlash."""
    url: str = Field(..., description="Colab Cloudflare/ngrok URL (https://...)")


class PipelineStatusResponse(PydanticModel):
    """Pipeline holat response."""
    camera_id:  str
    running:    bool
    started_at: Optional[str]
    stats:      Optional[dict]


class AllPipelinesResponse(PydanticModel):
    """Barcha pipelinelar holati."""
    total_running: int
    running_cameras: list[str]
    pipelines: dict


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post(
    "/start",
    status_code=http_status.HTTP_200_OK,
    summary="Kamera pipelineni ishga tushirish",
    description=(
        "Belgilangan kamerani DB dan olib pipeline ishga tushiradi. "
        "Bir vaqtda bir nechta kamera parallel ishlashi mumkin."
    ),
)
async def start_pipeline(
    body:         PipelineStartRequest,
    current_user: CurrentManager = ...,
    db:           AsyncSession   = Depends(get_db),
) -> dict:
    """
    Kamera pipelineni ishga tushirish.

    1. camera_id bo'yicha kamerani DB dan oladi
    2. PipelineManager orqali pipeline ishga tushiradi
    3. Status qaytaradi

    Raises:
        404: Kamera topilmasa
        400: Pipeline allaqachon ishlayapti
        500: Ishga tushirib bo'lmasa
    """
    repo   = CameraRepository(db)
    camera = await repo.get_by_camera_id_or_raise(body.camera_id)

    manager = get_pipeline_manager()

    if manager.is_running(body.camera_id):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline '{body.camera_id}' allaqachon ishlayapti",
        )

    # ── Colab GPU rejimi ──────────────────────────────────────────────────────
    if body.colab_mode:
        from app.services.colab_pipeline import ColabPipeline
        from app.services.camera.camera_factory import CameraFactory
        from app.config import settings as cfg

        colab_url = get_colab_url()
        if not colab_url:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Colab URL sozlanmagan. set-colab-url endpointiga URL yuboring. "
                    "Misol: POST /api/v1/pipeline/set-colab-url"
                ),
            )

        cam_service = CameraFactory.create_camera({
            "camera_id":    camera.camera_id,
            "type":         camera.type.value,
            "url":          camera.source,          # RTSP uchun
            "device_index": camera.device_index,    # USB uchun
            "fps":          camera.fps or 15,
        })
        if cam_service is None:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Kamera '{camera.camera_id}' ni yaratib bo'lmadi",
            )
        pipeline = ColabPipeline(
            camera_service = cam_service,
            colab_url      = colab_url,
            colab_secret   = cfg.COLAB_SECRET_KEY,
            target_fps     = camera.fps or 15,
        )
        ok, reason = await manager.start_colab_pipeline(camera.camera_id, pipeline)
    else:
        ok, reason = await manager.start_camera(
            camera_id    = camera.camera_id,
            camera_type  = camera.type.value,
            source       = camera.source,
            device_index = camera.device_index,
            fps          = camera.fps,
            skip_frames  = body.skip_frames,
        )

    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=reason or f"Pipeline '{body.camera_id}' ni ishga tushirib bo'lmadi",
        )

    mode = "colab_gpu" if body.colab_mode else "local_cpu"
    return {
        "status":        "started",
        "camera_id":     body.camera_id,
        "mode":          mode,
        "message":       f"Pipeline muvaffaqiyatli ishga tushirildi ({mode})",
        "total_running": manager.total_running(),
    }


@router.post(
    "/stop",
    status_code=http_status.HTTP_200_OK,
    summary="Kamera pipelineni to'xtatish",
)
async def stop_pipeline(
    camera_id:    str,
    current_user: CurrentManager = ...,
) -> dict:
    """
    Bitta kamera pipelineni to'xtatadi.

    Args:
        camera_id: To'xtatilishi kerak bo'lgan kamera

    Raises:
        400: Pipeline ishlamayapti
    """
    manager = get_pipeline_manager()

    if not manager.is_running(camera_id):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline '{camera_id}' ishlamayapti",
        )

    stats = manager.get_status(camera_id).get("stats")
    ok, reason = await manager.stop_camera(camera_id)

    return {
        "status":        "stopped" if ok else "error",
        "camera_id":     camera_id,
        "message":       "Pipeline to'xtatildi" if ok else reason,
        "final_stats":   stats,
        "total_running": manager.total_running(),
    }


@router.post(
    "/stop-all",
    status_code=http_status.HTTP_200_OK,
    summary="Barcha pipelinelarni to'xtatish",
)
async def stop_all_pipelines(
    current_user: CurrentManager = ...,
) -> dict:
    """Hozir ishlayotgan barcha kamera pipelinelarini to'xtatadi."""
    manager = get_pipeline_manager()
    running_before = manager.list_running()
    stopped = await manager.stop_all()

    return {
        "status":  "stopped",
        "stopped": stopped,
        "message": f"{stopped} ta pipeline to'xtatildi",
        "was_running": running_before,
    }


@router.get(
    "/status",
    response_model=AllPipelinesResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Barcha pipelinelar holati",
    description=(
        "Hozir ishlayotgan barcha kamera pipelinelarining holati va statistikasini qaytaradi. "
        "Dashboard har 2 soniyada shu endpointni so'raydi."
    ),
)
async def get_all_pipeline_status(
    current_user: CurrentUser = ...,
) -> AllPipelinesResponse:
    """
    Barcha pipelinelar holati.

    Frontend DashboardPage uchun asosiy status endpoint.
    """
    manager = get_pipeline_manager()

    return AllPipelinesResponse(
        total_running    = manager.total_running(),
        running_cameras  = manager.list_running(),
        pipelines        = manager.get_all_status(),
    )


@router.get(
    "/status/{camera_id}",
    response_model=PipelineStatusResponse,
    status_code=http_status.HTTP_200_OK,
    summary="Bitta kamera pipeline holati",
)
async def get_camera_pipeline_status(
    camera_id:    str,
    current_user: CurrentUser = ...,
) -> PipelineStatusResponse:
    """Bitta kamera pipelini holati va real-time statistikasi."""
    manager = get_pipeline_manager()
    s       = manager.get_status(camera_id)

    return PipelineStatusResponse(
        camera_id  = camera_id,
        running    = s["running"],
        started_at = s.get("started_at"),
        stats      = s.get("stats"),
    )


# =============================================================================
# LEGACY ENDPOINTS (Sprint 5-6 backcompat)
# =============================================================================

@router.post(
    "/start-video",
    status_code=http_status.HTTP_200_OK,
    summary="[Legacy] Video fayl orqali pipeline",
    tags=["Pipeline", "legacy"],
)
async def start_video_pipeline(
    video_filename: str = "sigir_test.mp4",
    camera_fps:     int = 10,
    skip_frames:    int = 3,
    current_user:   CurrentManager = ...,
) -> dict:
    """
    Video fayl orqali pipeline ishga tushiradi (Sprint 6 legacy).

    Yangi loyihalarda /pipeline/start ishlatish tavsiya etiladi.
    """
    video_path = Path(f"/app/data/videos/{video_filename}")
    if not video_path.exists():
        raise HTTPException(
            status_code=http_status.HTTP_404_NOT_FOUND,
            detail=(
                f"Video fayl topilmadi: {video_path}\n"
                f"Mahalliy: ~/taurus-vision/data/videos/{video_filename}"
            ),
        )

    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    camera_id    = "VIDEO-TEST-001"
    manager      = get_pipeline_manager()

    if manager.is_running(camera_id):
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="Video pipeline allaqachon ishlayapti. Avval to'xtating.",
        )

    ok, reason = await manager.start_camera(
        camera_id   = camera_id,
        camera_type = "simulated",
        fps         = camera_fps,
        skip_frames = skip_frames,
    )

    if not ok:
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Video pipeline ishga tushirib bo'lmadi",
        )

    return {
        "status":  "started",
        "message": f"Video pipeline ishga tushdi: {video_filename}",
        "config": {
            "video_file":   video_filename,
            "file_size_mb": round(file_size_mb, 1),
            "camera_fps":   camera_fps,
            "skip_frames":  skip_frames,
            "camera_id":    camera_id,
        },
    }


# =============================================================================
# COLAB GPU SOZLAMALARI
# =============================================================================

# Pydantic Settings immutable — runtime URL ni shu global da saqlaymiz
_colab_stream_url: Optional[str] = None


def get_colab_url() -> Optional[str]:
    """Colab URL ni qaytaradi (settings yoki runtime da o'rnatilgan)."""
    from app.config import settings
    return _colab_stream_url or settings.COLAB_STREAM_URL


@router.post(
    "/set-colab-url",
    status_code=http_status.HTTP_200_OK,
    summary="Colab stream URL ni sozlash",
    description="Colab Cell 6 dan olingan URL ni backend ga beradi.",
)
async def set_colab_url(
    body:         ColabUrlRequest,
    current_user: CurrentManager = ...,
) -> dict:
    """
    Colab URL ni runtime da o'rnatish.

    Cell 6 ishga tushgandan keyin chiqadigan URL ni bu yerga yuboring.
    Misol: {"url": "https://ceramic-benjamin-folder-reno.trycloudflare.com"}
    """
    global _colab_stream_url
    _colab_stream_url = body.url.rstrip("/")

    # URL ishlayotganini tekshirish
    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{_colab_stream_url}/status")
            if r.status_code == 200:
                data = r.json()
                return {
                    "ok":      True,
                    "url":     _colab_stream_url,
                    "message": "Colab ulandi va tayyor",
                    "colab":   data,
                }
    except Exception:
        pass

    return {
        "ok":      True,
        "url":     _colab_stream_url,
        "message": "URL saqlandi (lekin Colab hozir javob bermadi — Cell 6 ishlamoqdami?)",
    }


@router.get(
    "/colab-status",
    status_code=http_status.HTTP_200_OK,
    summary="Colab stream holati",
)
async def get_colab_status(
    current_user: CurrentUser = ...,
) -> dict:
    """Colab server holati va statistikasi."""
    url = get_colab_url()
    if not url:
        return {"connected": False, "message": "Colab URL sozlanmagan"}

    import httpx
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{url}/status")
            if r.status_code == 200:
                return {"connected": True, "url": url, **r.json()}
    except Exception as e:
        return {"connected": False, "url": url, "error": str(e)}


# =============================================================================
# DEV ENDPOINT
# =============================================================================

@router.post(
    "/inject",
    status_code=http_status.HTTP_200_OK,
    summary="[DEV] Fake detection inject",
    tags=["Pipeline", "dev"],
)
async def inject_test_detection(
    animal_id:    Optional[int] = None,
    camera_id:    str           = "CAM-TEST-KAMERA",
    confidence:   float         = 0.92,
    count:        int           = 1,
    current_user: CurrentManager = ...,
    db:           AsyncSession  = Depends(get_db),
) -> dict:
    """
    Fake detection DB ga yozadi va WebSocket orqali broadcast qiladi.

    Development va test uchun — real kamera va YOLO kerak emas.
    """
    if not (1 <= count <= 20):
        raise HTTPException(status_code=400, detail="count: 1–20")
    if not (0.0 <= confidence <= 1.0):
        raise HTTPException(status_code=400, detail="confidence: 0.0–1.0")

    animal: Optional[Animal]   = None
    animal_tag_id: Optional[str] = None

    if animal_id is not None:
        result = await db.execute(select(Animal).where(Animal.id == animal_id))
        animal = result.scalar_one_or_none()
        if animal is None:
            raise HTTPException(status_code=404, detail=f"Animal id={animal_id} topilmadi")
        animal_tag_id = animal.tag_id

    try:
        ws_manager = get_ws_manager()
    except RuntimeError:
        ws_manager = None

    injected = []

    for i in range(count):
        cx = round(random.uniform(0.1, 0.9), 3)
        cy = round(random.uniform(0.1, 0.9), 3)
        w  = round(random.uniform(0.15, 0.40), 3)
        h  = round(random.uniform(0.20, 0.50), 3)
        bbox = {"x": cx, "y": cy, "w": w, "h": h}
        estimated_weight_kg = round(max(80.0, min(700.0, (w * h * 4000) + 120)), 1)
        now = datetime.now(timezone.utc)

        det = Detection(
            animal_id         = animal_id,
            camera_id         = camera_id,
            timestamp         = now,
            confidence        = round(confidence, 3),
            class_id          = 19,
            class_name        = "cow",
            bbox              = bbox,
            estimated_weight  = estimated_weight_kg,
            frame_number      = i + 1,
            inference_time_ms = float(random.randint(320, 650)),
        )
        db.add(det)

        if animal:
            animal.mark_detected(now.replace(tzinfo=None))

        if animal_id and confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
            db.add(WeightMeasurement(
                animal_id           = animal_id,
                timestamp           = now,
                estimated_weight_kg = estimated_weight_kg,
                confidence_score    = round(confidence, 3),
                camera_id           = camera_id,
                raw_ai_data         = {"bbox": bbox, "source": "inject"},
            ))

        await db.flush()
        await db.refresh(det)

        if ws_manager:
            await ws_manager.broadcast({
                "type":                "detection",
                "timestamp":           now.isoformat(),
                "camera_id":           camera_id,
                "animal_id":           animal_id,
                "animal_tag_id":       animal_tag_id or "UNKNOWN",
                "class_name":          "cow",
                "confidence":          round(confidence, 3),
                "confidence_score":    round(confidence, 3),
                "estimated_weight_kg": estimated_weight_kg,
                "bbox":                bbox,
                "identified":          animal_id is not None,
                "pipeline_stats":      {"fps": 2.0, "frames": i + 1},
            })

        injected.append({
            "detection_id":        det.id,
            "animal_id":           animal_id,
            "camera_id":           camera_id,
            "confidence":          round(confidence, 3),
            "estimated_weight_kg": estimated_weight_kg,
            "timestamp":           now.isoformat(),
        })

    await db.commit()

    return {
        "status":              "ok",
        "injected":            len(injected),
        "websocket_broadcast": ws_manager is not None,
        "detections":          injected,
    }

# ============================================================================
# SPRINT 9-10: Tizim metrikalari
# ============================================================================

@router.get(
    "/system-metrics",
    status_code=200,
    summary="Tizim resurslari va load balancing holati",
    description=(
        "CPU, RAM, aktiv pipelinelar soni va load balancer holati. "
        "Dashboard va monitoring uchun."
    ),
)
async def get_system_metrics(
    current_user: CurrentUser = ...,
) -> dict:
    """
    Tizim resurslari va pipeline load balancing ma'lumotlari.

    Returns:
        {
            "cpu_percent":         float  — CPU yuki (%),
            "ram_percent":         float  — RAM yuki (%),
            "ram_available_mb":    float  — Bo'sh RAM (MB),
            "active_pipelines":    int    — Ishlayotgan pipelinelar,
            "max_pipelines":       int    — Maksimal ruxsat etilgan,
            "current_skip_frames": int    — Hozirgi adaptiv skip,
            "can_start_new":       bool   — Yangi pipeline qo'shish mumkinmi,
        }
    """
    manager = get_pipeline_manager()
    return manager.get_system_metrics()