"""
Detection Pipeline Control API.

Provides endpoints to start/stop/monitor the automated detection pipeline.
Development mode includes /inject endpoint for testing without real camera.

SPRINT 6 ADDITION:
    /start-video — Video fayl orqali pipeline ishga tushirish.
    Real sigir rasmlari bilan muzzle embedding ro'yxatdan o'tkazilgandan
    so'ng video pipeline uni tanishi mumkin.
"""
import asyncio
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import logging


from app.core.database import get_db
from app.api.v1.deps import get_current_active_user
from app.models.animal import Animal
from app.models.detection import Detection
from app.models.weight_measurement import WeightMeasurement

WEIGHT_CONFIDENCE_THRESHOLD = 0.70
from app.services.detection_pipeline import DetectionPipeline
from app.services.camera.simulated_camera import SimulatedCameraService
from app.services.ai.yolo_service import get_yolo_service
from app.api.v1.websocket import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
    dependencies=[Depends(get_current_active_user)],
)

# Global pipeline instance
_pipeline: Optional[DetectionPipeline] = None


@router.post(
    "/start",
    summary="Start automated detection pipeline",
    description="""
    Start the automated detection pipeline with simulated (random) camera.

    **Flow:**
    1. Camera captures frames
    2. YOLO detects animals
    3. Detection saved to database
    4. WebSocket broadcast to all clients

    **Use case:** Begin continuous monitoring
    """,
)
async def start_pipeline(
    camera_fps: int = 10,
    skip_frames: int = 5,
) -> dict:
    """Start detection pipeline with simulated random camera."""
    global _pipeline

    if _pipeline and _pipeline.is_running:
        raise HTTPException(
            status_code=400,
            detail="Pipeline already running"
        )

    try:
        yolo_service = get_yolo_service()

        try:
            ws_manager = get_ws_manager()
        except RuntimeError:
            ws_manager = None
            logger.warning("WebSocket manager not available")

        # Simulated camera — random frames (development mode)
        camera = SimulatedCameraService(
            camera_id="SIM-MAIN-001",
            fps=camera_fps,
            mode="random",
        )

        _pipeline = DetectionPipeline(
            camera_service=camera,
            yolo_service=yolo_service,
            ws_manager=ws_manager,
        )

        if skip_frames > 0 and camera_fps > 0:
            _pipeline.MIN_FRAME_INTERVAL = skip_frames / camera_fps
        logger.info("✓ Pipeline started via API (random mode)")

        asyncio.create_task(_pipeline.start())

        return {
            "status": "started",
            "message": "Detection pipeline started successfully",
            "config": {
                "camera_fps": camera_fps,
                "skip_frames": skip_frames,
                "mode": "random",
                "note": "Real test uchun POST /pipeline/start-video ishlatiling.",
            }
        }

    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start pipeline: {str(e)}"
        )


@router.post(
    "/start-video",
    summary="[Sprint 6] Start pipeline with video file",
    description="""
    **Sprint 6 — Real sigir testi uchun.**

    Video fayl orqali detection pipeline ishga tushiradi.
    Video Docker container ichida `/app/data/videos/` papkasida bo'lishi kerak.

    **Oldindan bajarish kerak:**
    1. Sigirni tizimga qo'shish: `POST /api/v1/animals/`
    2. Muzzle embedding ro'yxatdan o'tkazish: `POST /api/v1/registration/{animal_id}/register`
    3. Video faylni loyiha papkasiga ko'chirish: `~/taurus-vision/data/videos/`

    **Parametrlar:**
    - `video_filename`: `data/videos/` papkasidagi fayl nomi (masalan: `sigir_test.mp4`)
    - `camera_fps`: Simulyatsiya FPS (10 tavsiya etiladi)
    - `loop`: True = video tugagach boshidan qayta ishlaydi

    **Natija:** YOLO sigirni aniqlaganda, muzzle embedding taqqoslanadi.
    Agar cosine similarity >= 0.80 bo'lsa — animal_id biriktiriladi.
    """,
    tags=["pipeline", "sprint6"],
)
async def start_video_pipeline(
    video_filename: str = "sigir_test.mp4",
    camera_fps: int = 10,
    skip_frames: int = 3,
) -> dict:
    """
    Start detection pipeline using a video file.

    Designed for Sprint 6 real-world testing with actual cattle footage.

    Args:
        video_filename: Video file name in /app/data/videos/ directory
        camera_fps:     Frames per second for processing (10 recommended for CPU)
        skip_frames:    Process every Nth frame (3 = good balance)

    Returns:
        Pipeline start confirmation with video info

    Raises:
        HTTPException 400: Pipeline already running
        HTTPException 404: Video file not found in container
        HTTPException 500: Failed to initialize pipeline
    """
    global _pipeline

    if _pipeline and _pipeline.is_running:
        raise HTTPException(
            status_code=400,
            detail=(
                "Pipeline allaqachon ishlayapti. "
                "Avval POST /pipeline/stop orqali to'xtating."
            )
        )

    # Video faylni tekshirish — container ichidagi manzil
    video_path = Path(f"/app/data/videos/{video_filename}")

    if not video_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Video fayl topilmadi: {video_path}\n"
                f"Mahalliy kompyuterda: ~/taurus-vision/data/videos/{video_filename}\n"
                f"Tekshiring: ls -lh ~/taurus-vision/data/videos/"
            )
        )

    # Fayl hajmini log ga yozamiz
    file_size_mb = video_path.stat().st_size / (1024 * 1024)
    logger.info(
        f"[Sprint6] Video fayl topildi: {video_path} ({file_size_mb:.1f} MB)"
    )

    try:
        yolo_service = get_yolo_service()

        try:
            ws_manager = get_ws_manager()
        except RuntimeError:
            ws_manager = None
            logger.warning("WebSocket manager not available — WebSocket broadcast o'chirilgan")

        # SimulatedCameraService video rejimida
        # Bu klass allaqachon video fayldan kadrlarni o'qiy oladi
        camera = SimulatedCameraService(
            camera_id="VIDEO-TEST-001",
            fps=camera_fps,
            resolution=(1280, 720),  # HD — muzzle recognition uchun yaxshiroq
            mode="video",
            video_path=str(video_path),
        )

        _pipeline = DetectionPipeline(
            camera_service=camera,
            yolo_service=yolo_service,
            ws_manager=ws_manager,
        )

        # skip_frames moslashtirish — har 3-chi kadrni qayta ishlash
        if skip_frames > 0 and camera_fps > 0:
            _pipeline.MIN_FRAME_INTERVAL = skip_frames / camera_fps

        logger.info(
            f"[Sprint6] ✓ Video pipeline started | "
            f"file={video_filename} | fps={camera_fps} | skip={skip_frames}"
        )
        asyncio.create_task(_pipeline.start())

        return {
            "status": "started",
            "message": f"Video pipeline muvaffaqiyatli ishga tushdi: {video_filename}",
            "config": {
                "video_file": video_filename,
                "video_path_container": str(video_path),
                "file_size_mb": round(file_size_mb, 1),
                "camera_fps": camera_fps,
                "skip_frames": skip_frames,
                "resolution": "1280x720",
                "mode": "video",
            },
            "next_steps": [
                "Pipeline holatini kuzating: GET /pipeline/status",
                "WebSocket ulanib deteksiyalarni real vaqtda ko'ring: ws://localhost:8000/api/v1/live/ws",
                "Deteksiyalar ro'yxati: GET /api/v1/detections/",
                "To'xtatish: POST /pipeline/stop",
            ]
        }

    except Exception as e:
        logger.error(f"[Sprint6] Video pipeline ishga tushirishda xato: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Video pipeline ishga tushirib bo'lmadi: {str(e)}"
        )


@router.post(
    "/stop",
    summary="Stop automated detection pipeline",
    description="Gracefully stop the detection pipeline.",
)
async def stop_pipeline() -> dict:
    """Stop detection pipeline. Returns final statistics."""
    global _pipeline

    if not _pipeline or not _pipeline.is_running:
        raise HTTPException(
            status_code=400,
            detail="Pipeline not running"
        )

    try:
        stats = _pipeline.get_stats()
        await _pipeline.stop()
        logger.info("✓ Pipeline stopped via API")

        return {
            "status": "stopped",
            "message": "Detection pipeline stopped successfully",
            "stats": stats,
        }

    except Exception as e:
        logger.error(f"Failed to stop pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to stop pipeline: {str(e)}"
        )


@router.get(
    "/status",
    summary="Get pipeline status",
    description="Get current pipeline status and statistics.",
)
async def get_pipeline_status() -> dict:
    """Get pipeline status and stats."""
    global _pipeline

    if not _pipeline:
        return {
            "status": "not_initialized",
            "running": False,
        }

    stats = _pipeline.get_stats()

    return {
        "status": "running" if _pipeline.is_running else "stopped",
        "running": _pipeline.is_running,
        "stats": stats,
    }


@router.post(
    "/inject",
    summary="[DEV] Test detection inject",
    description="""
    **Development only.** Bypass camera and YOLO — directly inject a fake
    detection into the database and broadcast via WebSocket.

    Simulates the full pipeline: DB write → WebSocket → Frontend update.

    Args:
        animal_id: Existing animal ID (optional; None = unidentified)
        camera_id: Camera identifier string
        confidence: Detection confidence 0.0–1.0
        count: How many fake detections to inject
    """,
    tags=["pipeline", "dev"],
)
async def inject_test_detection(
    animal_id: Optional[int] = None,
    camera_id: str = "SIM-MAIN-001",
    confidence: float = 0.92,
    count: int = 1,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Inject fake detections directly into DB + WebSocket.

    Purpose: Validate the full DB → WebSocket → Frontend chain
    without requiring a real camera or YOLO to detect animals.

    Args:
        animal_id: Optional existing animal ID to link detection
        camera_id: Camera identifier to use
        confidence: Confidence score (0.0–1.0)
        count: Number of detections to inject
        db: Database session

    Returns:
        Summary of injected detections

    Raises:
        HTTPException 404: If animal_id provided but not found
        HTTPException 400: If count > 20 (safety limit)
    """
    if count < 1 or count > 20:
        raise HTTPException(
            status_code=400,
            detail="count must be between 1 and 20"
        )
    if not 0.0 <= confidence <= 1.0:
        raise HTTPException(
            status_code=400,
            detail="confidence must be between 0.0 and 1.0"
        )

    # Jonivorni tekshirish
    animal: Optional[Animal] = None
    animal_tag_id: Optional[str] = None

    if animal_id is not None:
        result = await db.execute(select(Animal).where(Animal.id == animal_id))
        animal = result.scalar_one_or_none()
        if animal is None:
            raise HTTPException(
                status_code=404,
                detail=f"Animal id={animal_id} not found"
            )
        animal_tag_id = animal.tag_id

    # WebSocket manager
    try:
        ws_manager = get_ws_manager()
    except RuntimeError:
        ws_manager = None

    injected = []

    for i in range(count):
        # Random realistic bbox
        cx = round(random.uniform(0.1, 0.9), 3)
        cy = round(random.uniform(0.1, 0.9), 3)
        w  = round(random.uniform(0.15, 0.40), 3)
        h  = round(random.uniform(0.20, 0.50), 3)
        bbox = {"x": cx, "y": cy, "w": w, "h": h}

        # Bbox dan og'irlik taxminiy hisoblash
        estimated_weight_kg = round(
            max(80.0, min(700.0, (w * h * 4000) + 120)), 1
        )

        now = datetime.now(timezone.utc)
        now_naive = now.replace(tzinfo=None)  # mark_detected() naive kutadi

        # DB ga detection yozish
        det = Detection(
            animal_id=        animal_id,
            camera_id=        camera_id,
            timestamp=        now,
            confidence=       round(confidence, 3),
            class_id=         19,        # COCO: cow
            class_name=       "cow",
            bbox=             bbox,
            estimated_weight= estimated_weight_kg,
            frame_number=     i + 1,
            inference_time_ms=float(random.randint(320, 650)),
        )
        db.add(det)

        # Animal.last_detected_at yangilash
        if animal:
            animal.mark_detected(now_naive)

        # WeightMeasurement yaratish — confidence yetarli bo'lsa
        if animal_id and confidence >= WEIGHT_CONFIDENCE_THRESHOLD:
            weight = WeightMeasurement(
                animal_id=          animal_id,
                timestamp=          now,
                estimated_weight_kg=estimated_weight_kg,
                confidence_score=   round(confidence, 3),
                camera_id=          camera_id,
                raw_ai_data={
                    "bbox":         bbox,
                    "class_name":   "cow",
                    "source":       "inject_endpoint",
                    "inject_index": i + 1,
                },
            )
            db.add(weight)

        await db.flush()
        await db.refresh(det)

        # WebSocket broadcast
        if ws_manager:
            payload = {
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
                "pipeline_stats": {
                    "fps": 2.0,
                    "frames": i + 1,
                },
            }
            await ws_manager.broadcast(payload)

        injected.append({
            "detection_id":        det.id,
            "animal_id":           animal_id,
            "animal_tag_id":       animal_tag_id,
            "camera_id":           camera_id,
            "confidence":          round(confidence, 3),
            "estimated_weight_kg": estimated_weight_kg,
            "bbox":                bbox,
            "timestamp":           now.isoformat(),
        })

    await db.commit()

    logger.info(
        f"[DEV] Injected {count} fake detection(s) | "
        f"animal_id={animal_id} | camera={camera_id}"
    )

    return {
        "status":   "ok",
        "injected": len(injected),
        "websocket_broadcast": ws_manager is not None,
        "detections": injected,
    }