"""
Detection Pipeline Control API.

Provides endpoints to start/stop/monitor the automated detection pipeline.
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from app.services.detection_pipeline import DetectionPipeline
from app.services.camera.simulated_camera import SimulatedCameraService
from app.services.ai.yolo_service import get_yolo_service
from app.api.v1.websocket import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/pipeline",
    tags=["pipeline"],
)

# Global pipeline instance
_pipeline: Optional[DetectionPipeline] = None


@router.post(
    "/start",
    summary="Start automated detection pipeline",
    description="""
    Start the automated detection pipeline.
    
    **Flow:**
    1. Camera captures frames
    2. YOLO detects animals
    3. Weight is estimated
    4. Measurement saved to database
    5. WebSocket broadcast to all clients
    
    **Use case:** Begin continuous monitoring
    """,
)
async def start_pipeline(
    camera_fps: int = 10,
    skip_frames: int = 5,
) -> dict:
    """
    Start detection pipeline.
    
    Returns pipeline status.
    """
    global _pipeline
    
    if _pipeline and _pipeline.is_running:
        raise HTTPException(
            status_code=400,
            detail="Pipeline already running"
        )
    
    try:
        # Get services
        yolo_service = get_yolo_service()
        
        try:
            ws_manager = get_ws_manager()
        except RuntimeError:
            ws_manager = None
            logger.warning("WebSocket manager not available")
        
        # Create simulated camera
        # Create simulated camera in VIDEO mode
        video_file = "/app/ml/test_assets/video.mp4" # <--- Sizning videongiz
        
        camera = SimulatedCameraService(
            camera_id="SIM-MAIN-001",
            fps=camera_fps,
            mode="video",           # <--- RANDOM o'rniga VIDEO
            video_path=video_file,  # <--- Fayl yo'li
        )
        
        # Create pipeline
        _pipeline = DetectionPipeline(
            camera_service=camera,
            yolo_service=yolo_service,
            ws_manager=ws_manager,
        )
        
        # Start pipeline
        await _pipeline.start()
        
        logger.info("✓ Pipeline started via API")
        
        return {
            "status": "started",
            "message": "Detection pipeline started successfully",
            "config": {
                "camera_fps": camera_fps,
                "skip_frames": skip_frames,
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to start pipeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start pipeline: {str(e)}"
        )


@router.post(
    "/stop",
    summary="Stop automated detection pipeline",
    description="Gracefully stop the detection pipeline.",
)
async def stop_pipeline() -> dict:
    """
    Stop detection pipeline.
    
    Returns final statistics.
    """
    global _pipeline
    
    if not _pipeline or not _pipeline.is_running:
        raise HTTPException(
            status_code=400,
            detail="Pipeline not running"
        )
    
    try:
        # Get stats before stopping
        stats = _pipeline.get_stats()
        
        # Stop pipeline
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
    """
    Get pipeline status and stats.
    
    Returns runtime information and performance metrics.
    """
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