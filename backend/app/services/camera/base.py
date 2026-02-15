"""
Abstract Camera Service Interface.

Defines the contract for camera implementations (real, simulated, RTSP, etc.).
Allows swapping camera sources without changing business logic.

DESIGN PATTERN: Strategy Pattern
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
import numpy as np


@dataclass
class CameraFrame:
    """
    Single camera frame with metadata.
    
    Represents one captured frame from any camera source.
    """
    frame: np.ndarray  # Image data (BGR format)
    timestamp: datetime
    camera_id: str
    frame_number: int
    resolution: tuple[int, int]  # (width, height)
    
    @property
    def shape(self) -> tuple[int, int, int]:
        """Get frame shape (height, width, channels)."""
        return self.frame.shape
    
    @property
    def width(self) -> int:
        """Get frame width."""
        return self.resolution[0]
    
    @property
    def height(self) -> int:
        """Get frame height."""
        return self.resolution[1]


@dataclass
class CameraInfo:
    """Camera metadata and capabilities."""
    camera_id: str
    name: str
    type: str  # 'rtsp', 'usb', 'simulated', 'file'
    resolution: tuple[int, int]
    fps: int
    is_active: bool
    location: str | None = None  # Physical location (e.g., "North Barn")


class CameraInterface(ABC):
    """
    Synchronous camera interface for real-time camera access.
    
    Simplified interface for RTSP, USB, and simulated cameras.
    All methods are synchronous for real-time frame capture.
    
    USAGE:
    ```python
    camera = RTSPCamera(camera_id="CAM-01", rtsp_url="rtsp://...")
    camera.start()
    
    frame = camera.get_frame()  # Sync call
    if frame is not None:
        # Process frame
        pass
    
    camera.stop()
    ```
    """
    
    @abstractmethod
    def start(self) -> None:
        """
        Start camera stream.
        
        Establishes connection and begins frame capture.
        """
        pass
    
    @abstractmethod
    def stop(self) -> None:
        """
        Stop camera stream.
        
        Closes connection and releases resources.
        """
        pass
    
    @abstractmethod
    def get_frame(self) -> np.ndarray | None:
        """
        Get latest frame from camera.
        
        Returns:
            Frame as numpy array (BGR format) or None if unavailable
        """
        pass
    
    @abstractmethod
    def is_opened(self) -> bool:
        """
        Check if camera is connected and operational.
        
        Returns:
            True if camera is ready, False otherwise
        """
        pass
    
    @abstractmethod
    def get_fps(self) -> float:
        """
        Get actual frames per second.
        
        Returns:
            Current FPS
        """
        pass
    
    @abstractmethod
    def get_resolution(self) -> tuple[int, int]:
        """
        Get frame resolution.
        
        Returns:
            Tuple of (width, height)
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> dict:
        """
        Get camera statistics.
        
        Returns:
            Dictionary with camera stats (frame_count, errors, etc.)
        """
        pass


class CameraServiceInterface(ABC):
    """
    Abstract base class for camera services (LEGACY - Async version).
    
    All camera implementations (RTSP, USB, simulated) must implement this.
    Ensures consistent API regardless of camera source.
    
    USAGE:
    ```python
    # Swap camera sources with zero code changes
    camera = SimulatedCameraService()  # or RTSPCameraService()
    
    async for frame in camera.stream_frames():
        # Process frame
        pass
    ```
    """
    
    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize camera connection.
        
        Should be called once before streaming.
        
        Raises:
            CameraError: If initialization fails
        """
        pass
    
    @abstractmethod
    async def stream_frames(
        self,
        skip_frames: int = 1,
    ) -> AsyncGenerator[CameraFrame, None]:
        """
        Stream frames from camera.
        
        Args:
            skip_frames: Process every Nth frame (for throttling)
            
        Yields:
            CameraFrame objects
            
        Raises:
            CameraError: If streaming fails
        """
        pass
    
    @abstractmethod
    async def get_frame(self) -> CameraFrame:
        """
        Get single frame from camera.
        
        Returns:
            Single CameraFrame
            
        Raises:
            CameraError: If capture fails
        """
        pass
    
    @abstractmethod
    async def stop(self) -> None:
        """
        Stop camera and release resources.
        
        Should be called during cleanup.
        """
        pass
    
    @abstractmethod
    def get_info(self) -> CameraInfo:
        """
        Get camera metadata.
        
        Returns:
            CameraInfo object
        """
        pass
    
    @property
    @abstractmethod
    def is_active(self) -> bool:
        """Check if camera is active and ready."""
        pass
    
    @property
    @abstractmethod
    def camera_id(self) -> str:
        """Get camera identifier."""
        pass