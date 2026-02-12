"""
Simulated Camera Service.

Generates synthetic camera frames for testing and development.
Useful when real cameras are not available.

FEATURES:
- Generates random frames or loads test images
- Configurable FPS and resolution
- Frame throttling support
- Realistic frame metadata
"""
import cv2
import asyncio
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
import numpy as np
import logging

from app.services.camera.base import (
    CameraServiceInterface,
    CameraFrame,
    CameraInfo,
)

logger = logging.getLogger(__name__)


class SimulatedCameraService(CameraServiceInterface):
    """
    Simulated camera for testing.
    
    Generates synthetic frames or loads test images.
    Perfect for development and CI/CD pipelines.
    
    USAGE:
    ```python
    camera = SimulatedCameraService(
        camera_id="SIM-001",
        fps=30,
        test_images_dir="./test_data/cattle"
    )
    
    await camera.initialize()
    
    async for frame in camera.stream_frames(skip_frames=5):
        # Process every 5th frame
        result = await yolo_service.detect(frame.frame)
    ```
    """
    
    def __init__(
        self,
        camera_id: str = "SIM-CAM-001",
        resolution: tuple[int, int] = (640, 480),
        fps: int = 30,
        test_images_dir: Path | str | None = None,
        video_path: str | None = None,  # <--- Yangi qator
        mode: str = "random",  # 'random', 'images', or 'video'
    ):
        self._camera_id = camera_id
        self._resolution = resolution
        self._fps = fps
        self._mode = mode
        self._test_images_dir = Path(test_images_dir) if test_images_dir else None
        self._video_path = video_path  # <--- Yangi qator
        
        self._is_active = False
        self._frame_count = 0
        self._test_images: list[np.ndarray] = []
        self._current_image_index = 0
        self._cap = None  # <--- Videoni ushlab turish uchun
    
    async def initialize(self) -> None:
        logger.info(f"Initializing simulated camera: {self._camera_id}")
        
        if self._mode == "images" and self._test_images_dir:
            await self._load_test_images()
        
        # --- VIDEO REJIMINI QO'SHAMIZ ---
        if self._mode == "video" and self._video_path:
            self._cap = cv2.VideoCapture(self._video_path)
            if not self._cap.isOpened():
                logger.error(f"Video faylni ochib bo'lmadi: {self._video_path}")
                self._mode = "random"
        # -------------------------------

        self._is_active = True
        self._frame_count = 0
    
    async def _load_test_images(self) -> None:
        """Load test images from directory."""
        if not self._test_images_dir or not self._test_images_dir.exists():
            logger.warning(
                f"Test images directory not found: {self._test_images_dir}"
            )
            logger.info("Falling back to random frame generation")
            self._mode = "random"
            return
        
        try:
            import cv2
            
            image_extensions = ('.jpg', '.jpeg', '.png', '.bmp')
            image_files = [
                f for f in self._test_images_dir.iterdir()
                if f.suffix.lower() in image_extensions
            ]
            
            if not image_files:
                logger.warning("No test images found, using random frames")
                self._mode = "random"
                return
            
            for image_file in image_files:
                img = cv2.imread(str(image_file))
                if img is not None:
                    # Resize to target resolution
                    img = cv2.resize(img, self._resolution)
                    self._test_images.append(img)
            
            logger.info(f"Loaded {len(self._test_images)} test images")
            
        except Exception as e:
            logger.error(f"Failed to load test images: {e}")
            logger.info("Falling back to random frame generation")
            self._mode = "random"
    
    def _generate_random_frame(self) -> np.ndarray:
        """
        Generate synthetic random frame.
        
        Creates a frame with random noise and some geometric shapes
        to simulate objects.
        
        Returns:
            Numpy array (BGR format)
        """
        # Create base frame with random noise
        frame = np.random.randint(
            50, 150,
            size=(self._resolution[1], self._resolution[0], 3),
            dtype=np.uint8
        )
        
        # Add some "objects" (rectangles) to simulate animals
        import cv2
        
        num_objects = np.random.randint(0, 3)
        
        for _ in range(num_objects):
            # Random rectangle (simulated animal)
            x1 = np.random.randint(0, self._resolution[0] - 100)
            y1 = np.random.randint(0, self._resolution[1] - 100)
            x2 = x1 + np.random.randint(80, 200)
            y2 = y1 + np.random.randint(100, 250)
            
            # Draw filled rectangle
            color = (
                np.random.randint(80, 120),
                np.random.randint(60, 100),
                np.random.randint(40, 80),
            )
            cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)
        
        return frame
    
    def _get_next_frame_data(self) -> np.ndarray:
        if self._mode == "video" and self._cap:
            ret, frame = self._cap.read()
            if not ret:  # Video tugasa, boshidan boshlaymiz (Loop)
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
            
            if ret:
                return cv2.resize(frame, self._resolution)
        
        if self._mode == "images" and self._test_images:
            frame = self._test_images[self._current_image_index]
            self._current_image_index = (self._current_image_index + 1) % len(self._test_images)
            return frame
        
        return self._generate_random_frame()
    
    async def get_frame(self) -> CameraFrame:
        """
        Get single frame.
        
        Returns:
            CameraFrame object
        """
        if not self._is_active:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        
        frame_data = self._get_next_frame_data()
        
        self._frame_count += 1
        
        return CameraFrame(
            frame=frame_data,
            timestamp=datetime.utcnow(),
            camera_id=self._camera_id,
            frame_number=self._frame_count,
            resolution=self._resolution,
        )
    
    async def stream_frames(
        self,
        skip_frames: int = 1,
    ) -> AsyncGenerator[CameraFrame, None]:
        """
        Stream frames continuously.
        
        Args:
            skip_frames: Process every Nth frame (1 = all frames)
            
        Yields:
            CameraFrame objects
        """
        if not self._is_active:
            raise RuntimeError("Camera not initialized. Call initialize() first.")
        
        logger.info(
            f"Starting frame stream (fps: {self._fps}, skip: {skip_frames})"
        )
        
        frame_delay = 1.0 / self._fps  # Seconds between frames
        
        try:
            while self._is_active:
                # Get frame
                frame = await self.get_frame()
                
                # Yield only every Nth frame
                if self._frame_count % skip_frames == 0:
                    yield frame
                
                # Simulate frame rate
                await asyncio.sleep(frame_delay)
                
        except asyncio.CancelledError:
            logger.info("Frame stream cancelled")
        except Exception as e:
            logger.error(f"Frame stream error: {e}", exc_info=True)
            raise
    
    async def stop(self) -> None:
        """Stop camera and cleanup."""
        logger.info(f"Stopping simulated camera: {self._camera_id}")
        self._is_active = False
        self._frame_count = 0
    
    def get_info(self) -> CameraInfo:
        """Get camera metadata."""
        return CameraInfo(
            camera_id=self._camera_id,
            name=f"Simulated Camera {self._camera_id}",
            type="simulated",
            resolution=self._resolution,
            fps=self._fps,
            is_active=self._is_active,
            location="Test Environment",
        )
    
    @property
    def is_active(self) -> bool:
        """Check if camera is active."""
        return self._is_active
    
    @property
    def camera_id(self) -> str:
        """Get camera ID."""
        return self._camera_id
