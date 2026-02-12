"""
Abstract AI Service Interface.

Defines the contract for all AI detection models.
This allows swapping between YOLOv8, YOLOv11, or custom models
without changing any business logic.

DESIGN PATTERN: Strategy Pattern + Abstract Factory
"""

from abc import ABC, abstractmethod
from typing import Any
from dataclasses import dataclass
from datetime import datetime
import numpy as np


@dataclass
class BoundingBox:
    """
    Bounding box coordinates.
    
    Normalized to [0, 1] for resolution independence.
    """
    x: float  # Center X (normalized)
    y: float  # Center Y (normalized)
    width: float  # Width (normalized)
    height: float  # Height (normalized)
    
    def to_dict(self) -> dict[str, float]:
        """Convert to dictionary for JSON serialization."""
        return {
            'x': self.x,
            'y': self.y,
            'width': self.width,
            'height': self.height,
        }
    
    def to_absolute(self, image_width: int, image_height: int) -> dict[str, int]:
        """Convert to absolute pixel coordinates."""
        return {
            'x': int(self.x * image_width),
            'y': int(self.y * image_height),
            'width': int(self.width * image_width),
            'height': int(self.height * image_height),
        }


@dataclass
class Detection:
    """
    Single object detection result.
    
    Represents one detected animal with its bounding box,
    confidence score, and metadata.
    """
    class_id: int
    class_name: str
    confidence: float
    bounding_box: BoundingBox
    timestamp: datetime
    
    # Optional: Segmentation mask (for advanced models)
    mask: np.ndarray | None = None
    
    # Optional: Additional model-specific data
    extra_data: dict[str, Any] | None = None
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'class_id': self.class_id,
            'class_name': self.class_name,
            'confidence': self.confidence,
            'bounding_box': self.bounding_box.to_dict(),
            'timestamp': self.timestamp.isoformat(),
            'has_mask': self.mask is not None,
            'extra_data': self.extra_data or {},
        }


@dataclass
class InferenceResult:
    """
    Complete inference result for a single frame.
    
    Contains all detections and metadata.
    """
    detections: list[Detection]
    inference_time_ms: float
    model_name: str
    frame_shape: tuple[int, int, int]  # (height, width, channels)
    timestamp: datetime
    
    @property
    def has_detections(self) -> bool:
        """Check if any objects were detected."""
        return len(self.detections) > 0
    
    @property
    def detection_count(self) -> int:
        """Get number of detections."""
        return len(self.detections)
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'detections': [d.to_dict() for d in self.detections],
            'detection_count': self.detection_count,
            'inference_time_ms': self.inference_time_ms,
            'model_name': self.model_name,
            'frame_shape': self.frame_shape,
            'timestamp': self.timestamp.isoformat(),
        }


class AIServiceInterface(ABC):
    """
    Abstract base class for AI detection services.
    
    All AI models (YOLO, custom, etc.) must implement this interface.
    This ensures consistent API regardless of underlying model.
    
    USAGE:
    ```python
    # Swap models with zero code changes
    service = YoloV11Service()  # or YoloV8Service()
    result = await service.detect(frame)
    ```
    """
    
    @abstractmethod
    async def load_model(self) -> None:
        """
        Load AI model into memory.
        
        Should be called once during application startup.
        Raises:
            ModelLoadError: If model fails to load
        """
        pass
    
    @abstractmethod
    async def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: float = 0.5,
        target_classes: list[int] | None = None,
    ) -> InferenceResult:
        """
        Perform object detection on a single frame.
        
        Args:
            frame: Input image as numpy array (BGR format)
            confidence_threshold: Minimum confidence score (0.0-1.0)
            target_classes: Filter for specific class IDs (None = all classes)
            
        Returns:
            InferenceResult containing all detections
            
        Raises:
            InferenceError: If detection fails
        """
        pass
    
    @abstractmethod
    def get_model_info(self) -> dict[str, Any]:
        """
        Get model metadata.
        
        Returns:
            Dictionary with model information:
            - name: Model name
            - version: Model version
            - type: Model type (detection, segmentation, etc.)
            - loaded: Whether model is loaded
            - device: Device (CPU/GPU)
        """
        pass
    
    @abstractmethod
    async def unload_model(self) -> None:
        """
        Unload model from memory.
        
        Should be called during application shutdown.
        """
        pass
    
    @property
    @abstractmethod
    def is_loaded(self) -> bool:
        """Check if model is loaded and ready."""
        pass
    
    @property
    @abstractmethod
    def model_name(self) -> str:
        """Get model name."""
        pass
