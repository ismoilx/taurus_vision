"""
YOLOv11 Detection Service.

Production-grade implementation of YOLO-based object detection
with singleton pattern and non-blocking inference.

FEATURES:
- Singleton pattern (load model once)
- Non-blocking inference (ThreadPoolExecutor)
- Model-agnostic (swap v8/v11 via config)
- Robust error handling
- Performance monitoring
"""

import time
from datetime import datetime
from pathlib import Path
from typing import Any
import numpy as np
import logging
from concurrent.futures import ThreadPoolExecutor

from app.services.ai.base import (
    AIServiceInterface,
    Detection,
    BoundingBox,
    InferenceResult,
)
from app.config import settings

logger = logging.getLogger(__name__)


class YoloService(AIServiceInterface):
    """
    YOLOv11 (or v8) object detection service.
    
    Singleton service that loads YOLO model once and provides
    non-blocking inference for real-time detection.
    
    THREAD SAFETY:
    - Model loading: Main thread (startup)
    - Inference: ThreadPool (non-blocking)
    
    COCO CLASSES:
    - 0: person
    - 19: cow (OUR TARGET)
    - 20: sheep
    - etc.
    """
    
    _instance: "YoloService | None" = None
    _model = None
    _executor: ThreadPoolExecutor | None = None
    
    def __new__(cls):
        """Singleton pattern - only one instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize service (called once)."""
        if not hasattr(self, '_initialized'):
            self._initialized = False
            self._model_path: Path | None = None
            self._device = "cpu"  # Will be set during load
            self._class_names: dict[int, str] = {}
            
            # Performance tracking
            self._total_inferences = 0
            self._total_inference_time = 0.0
    
    async def load_model(self) -> None:
        """
        Load YOLO model from disk.
        
        MODEL SELECTION:
        Controlled via config.py (reads from .env):
        - YOLO_MODEL=yolo11n.pt → YOLOv11
        - YOLO_MODEL=yolov8n.pt → YOLOv8
        
        ZERO code changes to swap!
        
        Raises:
            RuntimeError: If model fails to load
        """
        if self._initialized:
            logger.warning("Model already loaded")
            return
        
        try:
            # Import here to avoid loading on module import
            from ultralytics import YOLO
            
            # Construct model path
            #######################################################################################
            #Buni gemini maslahat bergan
            model_name = settings.YOLO_MODEL
            model_path = Path("/app/ml/models") / model_name  
            ########################################################################################
            logger.info(f"Loading YOLO model: {model_path}")
            
            # Check if model file exists
            if not model_path.exists():
                logger.warning(f"Model file not found: {model_path}")
                logger.info("Downloading model from Ultralytics...")
                # YOLO will auto-download if not found
                model_path = model_name
            
            # Load model
            start_time = time.time()
            self._model = YOLO(str(model_path))
            load_time = time.time() - start_time
            
            # Get model info
            self._model_path = model_path
            self._class_names = self._model.names  # COCO class names
            
            # Determine device
            import torch
            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            
            # Warm up model (first inference is slow)
            logger.info("Warming up model...")
            dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
            _ = self._model.predict(dummy_frame, verbose=False)
            
            # Initialize thread pool for non-blocking inference
            self._executor = ThreadPoolExecutor(
                max_workers=2,
                thread_name_prefix="yolo_inference"
            )
            
            self._initialized = True
            
            logger.info(
                f"✓ Model loaded successfully in {load_time:.2f}s "
                f"(device: {self._device})"
            )
            logger.info(f"Model type: {model_name}")
            logger.info(f"Available classes: {len(self._class_names)}")
            
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}", exc_info=True)
            raise RuntimeError(f"Model loading failed: {e}")
    
    def _run_inference(
        self,
        frame: np.ndarray,
        confidence_threshold: float,
        target_classes: list[int] | None,
    ) -> tuple[list, float]:
        """
        Internal method to run YOLO inference.
        
        Runs in thread pool to avoid blocking event loop.
        
        Returns:
            (results, inference_time_ms)
        """
        start_time = time.time()
        
        # Run YOLO prediction
        results = self._model.predict(
            frame,
            conf=confidence_threshold,
            classes=target_classes,
            verbose=False,
            # Optimize for speed
            imgsz=640,
            half=False,  # FP16 (if GPU supports)
        )
        
        inference_time = (time.time() - start_time) * 1000  # Convert to ms
        
        return results, inference_time
    
    async def detect(
        self,
        frame: np.ndarray,
        confidence_threshold: float = 0.5,
        target_classes: list[int] | None = None,
    ) -> InferenceResult:
        """
        Perform non-blocking object detection.
        
        Uses ThreadPoolExecutor to run YOLO inference without
        blocking FastAPI's event loop.
        
        Args:
            frame: Input image (BGR, numpy array)
            confidence_threshold: Min confidence (0.0-1.0)
            target_classes: Filter classes (e.g., [19] for cow only)
            
        Returns:
            InferenceResult with all detections
            
        Raises:
            RuntimeError: If model not loaded
            ValueError: If frame is invalid
        """
        if not self._initialized or self._model is None:
            raise RuntimeError("Model not loaded. Call load_model() first.")
        
        # Validate frame
        if frame is None or frame.size == 0:
            raise ValueError("Invalid frame: empty or None")
        
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise ValueError(
                f"Invalid frame shape: {frame.shape}. "
                f"Expected (height, width, 3)"
            )
        
        # Run inference in thread pool (non-blocking)
        import asyncio
        loop = asyncio.get_event_loop()
        
        results, inference_time = await loop.run_in_executor(
            self._executor,
            self._run_inference,
            frame,
            confidence_threshold,
            target_classes,
        )
        
        # Parse results
        detections = self._parse_results(results[0], frame.shape)
        
        # Update stats
        self._total_inferences += 1
        self._total_inference_time += inference_time
        
        logger.debug(
            f"Inference completed: {len(detections)} detections "
            f"in {inference_time:.2f}ms"
        )
        
        return InferenceResult(
            detections=detections,
            inference_time_ms=inference_time,
            model_name=self.model_name,
            frame_shape=frame.shape,
            timestamp=datetime.utcnow(),
        )
    
    def _parse_results(
        self,
        result,
        frame_shape: tuple,
    ) -> list[Detection]:
        """
        Parse YOLO results into Detection objects.
        
        Args:
            result: YOLO result object
            frame_shape: (height, width, channels)
            
        Returns:
            List of Detection objects
        """
        detections = []
        
        if result.boxes is None or len(result.boxes) == 0:
            return detections
        
        height, width = frame_shape[:2]
        
        # Extract boxes
        boxes = result.boxes.xyxy.cpu().numpy()  # [x1, y1, x2, y2]
        confidences = result.boxes.conf.cpu().numpy()
        class_ids = result.boxes.cls.cpu().numpy().astype(int)
        
        for box, conf, cls_id in zip(boxes, confidences, class_ids):
            # Convert to center + width/height format (normalized)
            x1, y1, x2, y2 = box
            
            center_x = ((x1 + x2) / 2) / width
            center_y = ((y1 + y2) / 2) / height
            box_width = (x2 - x1) / width
            box_height = (y2 - y1) / height
            
            # Create BoundingBox
            bbox = BoundingBox(
                x=float(center_x),
                y=float(center_y),
                width=float(box_width),
                height=float(box_height),
            )
            
            # Get class name
            class_name = self._class_names.get(cls_id, f"class_{cls_id}")
            
            # Create Detection
            detection = Detection(
                class_id=int(cls_id),
                class_name=class_name,
                confidence=float(conf),
                bounding_box=bbox,
                timestamp=datetime.utcnow(),
                extra_data={
                    'absolute_box': {
                        'x1': int(x1),
                        'y1': int(y1),
                        'x2': int(x2),
                        'y2': int(y2),
                    }
                }
            )
            
            detections.append(detection)
        
        return detections
    
    def get_model_info(self) -> dict[str, Any]:
        """Get model metadata."""
        return {
            'name': self.model_name,
            'version': 'v11' if 'yolo11' in str(self._model_path).lower() else 'v8',
            'type': 'object_detection',
            'loaded': self._initialized,
            'device': self._device,
            'model_path': str(self._model_path) if self._model_path else None,
            'total_inferences': self._total_inferences,
            'avg_inference_time_ms': (
                self._total_inference_time / self._total_inferences
                if self._total_inferences > 0 else 0
            ),
            'available_classes': len(self._class_names),
        }
    
    async def unload_model(self) -> None:
        """Unload model and cleanup resources."""
        logger.info("Unloading YOLO model...")
        
        # Shutdown thread pool
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
        
        # Clear model
        self._model = None
        self._initialized = False
        
        logger.info("✓ Model unloaded")
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._initialized and self._model is not None
    
    @property
    def model_name(self) -> str:
        """Get model name."""
        if self._model_path:
            return self._model_path.name
        return settings.YOLO_MODEL


# Global singleton instance
_yolo_service: YoloService | None = None


def get_yolo_service() -> YoloService:
    """
    Get global YoloService instance.
    
    Returns:
        Singleton YoloService instance
        
    Raises:
        RuntimeError: If service not initialized
    """
    global _yolo_service
    
    if _yolo_service is None:
        _yolo_service = YoloService()
    
    if not _yolo_service.is_loaded:
        raise RuntimeError(
            "YOLO service not loaded. "
            "Ensure load_ai_models() is called in startup event."
        )
    
    return _yolo_service


async def initialize_yolo_service() -> YoloService:
    """
    Initialize YOLO service (call in startup event).
    
    Returns:
        Initialized YoloService
    """
    global _yolo_service
    
    if _yolo_service is None:
        _yolo_service = YoloService()
    
    await _yolo_service.load_model()
    
    return _yolo_service


async def shutdown_yolo_service() -> None:
    """Shutdown YOLO service (call in shutdown event)."""
    global _yolo_service
    
    if _yolo_service is not None:
        await _yolo_service.unload_model()