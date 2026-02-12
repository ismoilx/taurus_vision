"""
AI Detection API endpoints.

Provides real-time object detection using YOLOv11.
"""

import base64
import io
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from PIL import Image
import numpy as np
import logging

from app.services.ai.yolo_service import get_yolo_service, YoloService
from app.schemas.detection import (
    InferenceResultResponse,
    DetectionResponse,
    BoundingBoxResponse,
    ModelInfoResponse,
)
from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/detection",
    tags=["detection"],
)


def image_to_numpy(image: Image.Image) -> np.ndarray:
    """
    Convert PIL Image to numpy array (BGR format for YOLO).
    
    Args:
        image: PIL Image
        
    Returns:
        Numpy array in BGR format
    """
    # Convert to RGB (if not already)
    if image.mode != 'RGB':
        image = image.convert('RGB')
    
    # Convert to numpy array
    img_array = np.array(image)
    
    # Convert RGB to BGR (OpenCV/YOLO format)
    img_bgr = img_array[:, :, ::-1].copy()
    
    return img_bgr


@router.post(
    "/detect-upload",
    response_model=InferenceResultResponse,
    summary="Detect objects in uploaded image",
    description="""
    Upload an image file for object detection.
    
    **Supported formats:** JPG, PNG, BMP
    
    **Process:**
    1. Upload image
    2. YOLOv11 performs detection
    3. Returns all detected objects with bounding boxes
    
    **Use case:** Manual testing, web upload
    """,
)
async def detect_from_upload(
    file: UploadFile = File(..., description="Image file to analyze"),
    confidence_threshold: float = Query(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    ),
    target_classes: str | None = Query(
        default=None,
        description="Comma-separated class IDs (e.g., '19' for cow)",
    ),
    yolo_service: YoloService = Depends(get_yolo_service),
) -> InferenceResultResponse:
    """
    Detect objects in uploaded image file.
    
    Returns detection results with bounding boxes and confidence scores.
    """
    try:
        # Read and validate image
        contents = await file.read()
        
        try:
            image = Image.open(io.BytesIO(contents))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid image file: {e}",
            )
        
        # Convert to numpy array
        frame = image_to_numpy(image)
        
        # Parse target classes
        classes = None
        if target_classes:
            try:
                classes = [int(c.strip()) for c in target_classes.split(',')]
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail="Invalid target_classes format. Use comma-separated integers.",
                )
        
        # Run detection
        result = await yolo_service.detect(
            frame=frame,
            confidence_threshold=confidence_threshold,
            target_classes=classes,
        )
        
        logger.info(
            f"Detection completed: {result.detection_count} objects found "
            f"in {result.inference_time_ms:.2f}ms"
        )
        
        # Convert to response schema
        detections = [
            DetectionResponse(
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                bounding_box=BoundingBoxResponse(**d.bounding_box.to_dict()),
                timestamp=d.timestamp,
                has_mask=d.mask is not None,
                extra_data=d.extra_data or {},
            )
            for d in result.detections
        ]
        
        return InferenceResultResponse(
            detections=detections,
            detection_count=result.detection_count,
            inference_time_ms=result.inference_time_ms,
            model_name=result.model_name,
            frame_shape=result.frame_shape,
            timestamp=result.timestamp,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}",
        )


@router.post(
    "/detect-base64",
    response_model=InferenceResultResponse,
    summary="Detect objects in base64-encoded image",
    description="""
    Send base64-encoded image for detection.
    
    **Use case:** Camera streams, mobile apps, embedded devices
    """,
)
async def detect_from_base64(
    image_base64: str,
    confidence_threshold: float = 0.5,
    target_classes: list[int] | None = None,
    yolo_service: YoloService = Depends(get_yolo_service),
) -> InferenceResultResponse:
    """
    Detect objects in base64-encoded image.
    
    Useful for camera streams and mobile apps.
    """
    try:
        # Decode base64
        try:
            image_data = base64.b64decode(image_base64)
            image = Image.open(io.BytesIO(image_data))
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base64 image: {e}",
            )
        
        # Convert to numpy array
        frame = image_to_numpy(image)
        
        # Run detection
        result = await yolo_service.detect(
            frame=frame,
            confidence_threshold=confidence_threshold,
            target_classes=target_classes,
        )
        
        # Convert to response schema
        detections = [
            DetectionResponse(
                class_id=d.class_id,
                class_name=d.class_name,
                confidence=d.confidence,
                bounding_box=BoundingBoxResponse(**d.bounding_box.to_dict()),
                timestamp=d.timestamp,
                has_mask=d.mask is not None,
                extra_data=d.extra_data or {},
            )
            for d in result.detections
        ]
        
        return InferenceResultResponse(
            detections=detections,
            detection_count=result.detection_count,
            inference_time_ms=result.inference_time_ms,
            model_name=result.model_name,
            frame_shape=result.frame_shape,
            timestamp=result.timestamp,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Detection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Detection failed: {str(e)}",
        )


@router.get(
    "/model-info",
    response_model=ModelInfoResponse,
    summary="Get AI model information",
    description="Returns metadata about the loaded AI model.",
)
async def get_model_info(
    yolo_service: YoloService = Depends(get_yolo_service),
) -> ModelInfoResponse:
    """
    Get AI model metadata.
    
    Includes performance statistics and model details.
    """
    info = yolo_service.get_model_info()
    return ModelInfoResponse(**info)


@router.get(
    "/health",
    summary="Check AI service health",
    description="Verify that AI model is loaded and ready.",
)
async def ai_health_check(
    yolo_service: YoloService = Depends(get_yolo_service),
) -> dict:
    """
    AI service health check.
    
    Returns model status and readiness.
    """
    return {
        "status": "healthy" if yolo_service.is_loaded else "unhealthy",
        "model_loaded": yolo_service.is_loaded,
        "model_name": yolo_service.model_name,
    }