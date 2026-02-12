"""
Pydantic schemas for AI detection operations.

Defines request/response models for detection endpoints.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field, ConfigDict


class BoundingBoxResponse(BaseModel):
    """Bounding box coordinates (normalized 0-1)."""
    
    x: float = Field(..., description="Center X (normalized)")
    y: float = Field(..., description="Center Y (normalized)")
    width: float = Field(..., description="Width (normalized)")
    height: float = Field(..., description="Height (normalized)")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "x": 0.5,
                "y": 0.5,
                "width": 0.3,
                "height": 0.4,
            }
        }
    )


class DetectionResponse(BaseModel):
    """Single object detection."""
    
    class_id: int = Field(..., description="COCO class ID")
    class_name: str = Field(..., description="Class name (e.g., 'cow')")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    bounding_box: BoundingBoxResponse
    timestamp: datetime
    has_mask: bool = Field(False, description="Whether segmentation mask is available")
    extra_data: dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "class_id": 19,
                "class_name": "cow",
                "confidence": 0.92,
                "bounding_box": {
                    "x": 0.5,
                    "y": 0.5,
                    "width": 0.3,
                    "height": 0.4,
                },
                "timestamp": "2026-02-12T10:30:00Z",
                "has_mask": False,
                "extra_data": {},
            }
        },
    )


class InferenceResultResponse(BaseModel):
    """Complete inference result for a frame."""
    
    detections: list[DetectionResponse] = Field(
        ...,
        description="List of detected objects",
    )
    
    detection_count: int = Field(
        ...,
        description="Number of detections",
    )
    
    inference_time_ms: float = Field(
        ...,
        description="Inference latency in milliseconds",
    )
    
    model_name: str = Field(
        ...,
        description="AI model used (e.g., yolo11n.pt)",
    )
    
    frame_shape: tuple[int, int, int] = Field(
        ...,
        description="Frame dimensions (height, width, channels)",
    )
    
    timestamp: datetime
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "detections": [
                    {
                        "class_id": 19,
                        "class_name": "cow",
                        "confidence": 0.92,
                        "bounding_box": {
                            "x": 0.5,
                            "y": 0.5,
                            "width": 0.3,
                            "height": 0.4,
                        },
                        "timestamp": "2026-02-12T10:30:00Z",
                        "has_mask": False,
                        "extra_data": {},
                    }
                ],
                "detection_count": 1,
                "inference_time_ms": 45.2,
                "model_name": "yolo11n.pt",
                "frame_shape": [640, 640, 3],
                "timestamp": "2026-02-12T10:30:00Z",
            }
        },
    )


class DetectFromImageRequest(BaseModel):
    """Request for image-based detection (base64 or URL)."""
    
    image_base64: Optional[str] = Field(
        None,
        description="Base64-encoded image",
    )
    
    image_url: Optional[str] = Field(
        None,
        description="URL to image",
    )
    
    confidence_threshold: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold",
    )
    
    target_classes: Optional[list[int]] = Field(
        None,
        description="Filter for specific class IDs (e.g., [19] for cow only)",
    )


class ModelInfoResponse(BaseModel):
    """AI model information."""
    
    name: str
    version: str
    type: str
    loaded: bool
    device: str
    model_path: Optional[str] = None
    total_inferences: int
    avg_inference_time_ms: float
    available_classes: int
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "name": "yolo11n.pt",
                "version": "v11",
                "type": "object_detection",
                "loaded": True,
                "device": "cpu",
                "model_path": "./ml/models/yolo11n.pt",
                "total_inferences": 1523,
                "avg_inference_time_ms": 42.5,
                "available_classes": 80,
            }
        },
    )