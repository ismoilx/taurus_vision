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
import logging
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator
import numpy as np

from app.services.camera.base import (
    CameraServiceInterface,
    CameraFrame,
    CameraInfo,
)

logger = logging.getLogger(__name__)


class SimulatedCamera:
    """
    Synchronous simulated camera for testing.
    
    Generates synthetic frames with random colored rectangles.
    Compatible with RTSPCamera and USBCamera interface.
    
    Features:
    - Random colored frames
    - Configurable resolution and FPS
    - Thread-safe operation
    - Statistics tracking
    """
    
    def __init__(
        self,
        camera_id: str,
        fps: int = 10,
        width: int = 1920,
        height: int = 1080,
    ):
        """
        Initialize simulated camera.
        
        Args:
            camera_id: Unique camera identifier
            fps: Target frames per second
            width: Frame width
            height: Frame height
        """
        self.camera_id = camera_id
        self.fps = fps
        self.width = width
        self.height = height
        
        self._running = False
        self._frame_count = 0
        self._error_count = 0
        
        logger.info(f"Simulated camera initialized: {camera_id}")
    
    def start(self) -> None:
        """Start camera stream."""
        if self._running:
            logger.warning(f"Camera {self.camera_id} already running")
            return
        
        self._running = True
        logger.info(f"Simulated camera started: {self.camera_id}")
    
    def stop(self) -> None:
        """Stop camera stream."""
        self._running = False
        logger.info(f"Simulated camera stopped: {self.camera_id}")
    
    def get_frame(self) -> np.ndarray | None:
        """
        Get simulated frame.
        
        Returns:
            Synthetic frame as numpy array (BGR format)
        """
        if not self._running:
            return None
        
        try:
            # Generate random colored frame
            frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            
            # Add random colored rectangles (simulate animals)
            num_objects = np.random.randint(1, 5)

            # Faqat yetarli katta kadrda tasodifiy to'rtburchaklar chizish.
            # 100×100 dan kichik o'lchamda (masalan 1×1 test rejimi) bu qadamni o'tkazib yuboramiz.
            if self.width >= 100 and self.height >= 100:
                for _ in range(num_objects):
                    x1 = np.random.randint(0, self.width - 100)
                    y1 = np.random.randint(0, self.height - 100)
                    x2 = x1 + np.random.randint(50, 200)
                    y2 = y1 + np.random.randint(50, 200)

                    color = (
                        np.random.randint(0, 255),
                        np.random.randint(0, 255),
                        np.random.randint(0, 255),
                    )
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, -1)

            # Matn faqat kenglik 50+ bo'lganda chiziladi (kichik o'lchamlarda putText xato beradi)
            if self.width >= 50 and self.height >= 40:
                cv2.putText(
                    frame,
                    f"Frame: {self._frame_count}",
                    (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1,
                    (255, 255, 255),
                    2,
                )
            
            self._frame_count += 1
            return frame
            
        except Exception as e:
            logger.error(f"Error generating frame from {self.camera_id}: {e}")
            self._error_count += 1
            return None
    
    def is_opened(self) -> bool:
        """Check if camera is running."""
        return self._running
    
    def get_fps(self) -> float:
        """Get configured FPS."""
        return float(self.fps)
    
    def get_resolution(self) -> tuple[int, int]:
        """Get frame resolution."""
        return (self.width, self.height)
    
    def get_stats(self) -> dict:
        """Get camera statistics."""
        return {
            "camera_id": self.camera_id,
            "type": "simulated",
            "connected": self._running,
            "running": self._running,
            "frame_count": self._frame_count,
            "error_count": self._error_count,
            "fps": self.get_fps(),
            "resolution": self.get_resolution(),
            "last_frame_age_seconds": 0.0,
        }


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
        test_images_dir="./test_data/cattle",
        video_path="./test_data/sample.mp4",
        mode="video"
    )
    
    await camera.initialize()
    await camera.start()
    
    async for frame in camera.stream_frames(skip_frames=5):
        result = await yolo_service.detect(frame.frame)
    ```
    """
    
    def __init__(
        self,
        camera_id: str = "SIM-CAM-001",
        resolution: tuple[int, int] = (640, 480),
        fps: int = 30,
        test_images_dir: Path | str | None = None,
        video_path: str | None = None,
        mode: str = "random",  # 'random', 'images', or 'video'
    ):
        self._camera_id = camera_id
        self._resolution = resolution
        self._fps = fps
        self._mode = mode
        self._test_images_dir = Path(test_images_dir) if test_images_dir else None
        self._video_path = video_path
        
        self._is_active = False
        self._frame_count = 0
        self._test_images: list[np.ndarray] = []
        self._current_image_index = 0
        self._cap: cv2.VideoCapture | None = None
    
    async def initialize(self) -> None:
        logger.info(f"Initializing simulated camera: {self._camera_id}")
        
        if self._mode == "images" and self._test_images_dir:
            await self._load_test_images()
        
        # --- VIDEO REJIMINI QO'SHAMIZ ---
        if self._mode == "video" and self._video_path:
            self._cap = cv2.VideoCapture(self._video_path)
            if not self._cap.isOpened():
                logger.error(f"Video faylni ochib bo'lmadi: {self._video_path}. Random rejimga o'tilmoqda.")
                self._mode = "random"
                self._cap = None
        # -------------------------------

        self._is_active = True
        self._frame_count = 0
    
    # ----------------------------------------------------
    #  start() funksiyasi:
    # ----------------------------------------------------
    async def start(self) -> None:
        """Start camera processing."""
        logger.info(f"Starting simulated camera service: {self._camera_id}")
        if not self._is_active:
            await self.initialize()
    # ----------------------------------------------------
            
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
        # 1. VIDEO REJIMI
        if self._mode == "video" and self._cap is not None:
            ret, frame = self._cap.read()
            if not ret:  # Video tugasa, boshidan boshlaymiz (Loop)
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self._cap.read()
            
            # Agar kadr muvaffaqiyatli o'qilgan bo'lsa
            if ret and frame is not None:
                return cv2.resize(frame, self._resolution)
            else:
                logger.warning("Kadrni o'qib bo'lmadi, random kadr ishlatilmoqda.")
                # Agar videoda qandaydir jiddiy muammo bo'lsa, tushib ketmasligi uchun:
                return self._generate_random_frame()
        
        # 2. RASMLAR REJIMI
        elif self._mode == "images" and self._test_images:
            frame = self._test_images[self._current_image_index]
            self._current_image_index = (self._current_image_index + 1) % len(self._test_images)
            return frame
        
        # 3. RANDOM REJIMI
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
        
        # Video faylni xotiradan tozalash
        if self._cap is not None:
            self._cap.release()
            self._cap = None
    
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