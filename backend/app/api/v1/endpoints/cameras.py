"""
Camera management API endpoints.

Provides REST API for:
- Camera registration and management
- Camera control (start/stop)
- Health monitoring
- Statistics retrieval
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from app.services.camera.camera_manager import camera_manager
from app.services.camera.camera_factory import CameraFactory


logger = logging.getLogger(__name__)

# Barcha endpointlar bitta qatorda "Cameras" papkasiga tushishi uchun
# shu yerni o'zgartirdik:
router = APIRouter(tags=["Cameras"])


# Pydantic schemas
class CameraConfig(BaseModel):
    """Camera configuration schema."""
    
    camera_id: str = Field(..., description="Unique camera identifier")
    type: str = Field(..., description="Camera type: rtsp, usb, simulated")
    
    # RTSP specific
    url: Optional[str] = Field(None, description="RTSP stream URL")
    
    # USB specific
    device_index: Optional[int] = Field(None, description="USB device index")
    
    # Common parameters
    fps: int = Field(10, ge=1, le=60, description="Target FPS")
    width: int = Field(1920, ge=320, le=3840, description="Frame width")
    height: int = Field(1080, ge=240, le=2160, description="Frame height")
    
    # Optional parameters
    reconnect_interval: Optional[int] = Field(5, description="Reconnect interval in seconds")
    connection_timeout: Optional[int] = Field(10, description="Connection timeout in seconds")
    auto_reconnect: Optional[bool] = Field(True, description="Auto-reconnect on failure")
    auto_start: bool = Field(True, description="Auto-start after registration")


class CameraResponse(BaseModel):
    """Camera operation response."""
    
    success: bool
    message: str
    camera_id: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# =========================================================================
# 1. ANIQ (STATIC) ENDPOINTLAR (Tepada turishi shart!)
# =========================================================================

@router.post("/cameras/", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def register_camera(config: CameraConfig):
    """
    Register a new camera.
    
    Creates and registers a camera based on provided configuration.
    Camera can be automatically started if auto_start is True.
    """
    try:
        # Validate configuration
        is_valid, error_msg = CameraFactory.validate_config(config.dict())
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        
        # Create camera
        camera = CameraFactory.create_camera(config.dict())
        if camera is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create camera instance"
            )
        
        # Register with manager
        success = camera_manager.register_camera(
            camera_id=config.camera_id,
            camera=camera,
            auto_start=config.auto_start,
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register camera"
            )
        
        return CameraResponse(
            success=True,
            message=f"Camera {config.camera_id} registered successfully",
            camera_id=config.camera_id,
            data=camera.get_stats(),
        )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to register camera: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/cameras/", response_model=List[str])
async def list_cameras():
    """
    List all registered cameras.
    
    Returns list of camera IDs.
    """
    return camera_manager.list_cameras()


@router.get("/cameras/stats/all")
async def get_all_camera_stats():
    """
    Get statistics for all cameras.
    
    Returns dictionary mapping camera_id to statistics.
    """
    return camera_manager.get_all_stats()


@router.post("/cameras/start-all", response_model=CameraResponse)
async def start_all_cameras():
    """
    Start all registered cameras.
    
    Returns number of cameras started successfully.
    """
    count = camera_manager.start_all()
    total = len(camera_manager.list_cameras())
    
    return CameraResponse(
        success=True,
        message=f"Started {count}/{total} cameras",
        data={"started": count, "total": total},
    )


@router.post("/cameras/stop-all", response_model=CameraResponse)
async def stop_all_cameras():
    """
    Stop all registered cameras.
    
    Returns number of cameras stopped successfully.
    """
    count = camera_manager.stop_all()
    total = len(camera_manager.list_cameras())
    
    return CameraResponse(
        success=True,
        message=f"Stopped {count}/{total} cameras",
        data={"stopped": count, "total": total},
    )


@router.get("/cameras/status")
async def get_camera_status():
    """
    Get overall camera system health status.
    
    Returns summary of camera system health including counts and percentages.
    """
    return camera_manager.get_health_status()


# =========================================================================
# 2. O'ZGARUVCHAN (DYNAMIC) ENDPOINTLAR (Eng pastda turishi kerak!)
# =========================================================================

@router.delete("/cameras/{camera_id}", response_model=CameraResponse)
async def unregister_camera(camera_id: str):
    """
    Unregister a camera.
    
    Stops and removes camera from the system.
    """
    success = camera_manager.unregister_camera(camera_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found"
        )
    
    return CameraResponse(
        success=True,
        message=f"Camera {camera_id} unregistered successfully",
        camera_id=camera_id,
    )


@router.get("/cameras/{camera_id}/stats")
async def get_camera_stats(camera_id: str):
    """
    Get statistics for a specific camera.
    
    Returns detailed statistics including frame count, errors, FPS, etc.
    """
    stats = camera_manager.get_camera_stats(camera_id)
    
    if stats is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Camera {camera_id} not found"
        )
    
    return stats


@router.post("/cameras/{camera_id}/start", response_model=CameraResponse)
async def start_camera(camera_id: str):
    """
    Start a specific camera.
    
    Initiates camera stream if not already running.
    """
    success = camera_manager.start_camera(camera_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start camera {camera_id}"
        )
    
    return CameraResponse(
        success=True,
        message=f"Camera {camera_id} started successfully",
        camera_id=camera_id,
    )


@router.post("/cameras/{camera_id}/stop", response_model=CameraResponse)
async def stop_camera(camera_id: str):
    """
    Stop a specific camera.
    
    Halts camera stream and releases resources.
    """
    success = camera_manager.stop_camera(camera_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop camera {camera_id}"
        )
    
    return CameraResponse(
        success=True,
        message=f"Camera {camera_id} stopped successfully",
        camera_id=camera_id,
    )
