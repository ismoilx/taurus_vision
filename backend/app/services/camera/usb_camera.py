"""
USB Camera implementation for webcams.

Supports:
- USB webcams (V4L2 on Linux, DirectShow on Windows)
- Multiple device selection
- Auto-detection
- Configurable resolution and FPS
"""

import cv2
import time
import logging
import threading
from typing import Optional, Dict, Any, List
import numpy as np

from app.services.camera.base import CameraInterface


logger = logging.getLogger(__name__)


class USBCamera(CameraInterface):
    """
    USB camera implementation for webcams.
    
    Supports standard USB webcams via OpenCV VideoCapture.
    Device can be specified by index (0, 1, 2...) or by path (/dev/video0).
    
    Features:
    - Auto device detection
    - Configurable resolution and FPS
    - Frame caching
    - Connection health monitoring
    """
    
    def __init__(
        self,
        camera_id: str,
        device_index: int = 0,
        fps: int = 10,
        width: int = 1920,
        height: int = 1080,
        auto_reconnect: bool = True,
    ):
        """
        Initialize USB camera.
        
        Args:
            camera_id: Unique camera identifier
            device_index: USB device index (0, 1, 2...) or device path
            fps: Target frames per second
            width: Frame width
            height: Frame height
            auto_reconnect: Automatically reconnect on failure
        """
        self.camera_id = camera_id
        self.device_index = device_index
        self.fps = fps
        self.width = width
        self.height = height
        self.auto_reconnect = auto_reconnect
        
        self._capture: Optional[cv2.VideoCapture] = None
        self._running = False
        self._connected = False
        self._last_frame: Optional[np.ndarray] = None
        self._last_frame_time: Optional[float] = None
        self._frame_count = 0
        self._error_count = 0
        self._total_errors = 0
        self._lock = threading.Lock()
        
        logger.info(f"USB camera initialized: {camera_id} (device: {device_index})")
    
    def start(self) -> None:
        """Start camera stream."""
        if self._running:
            logger.warning(f"Camera {self.camera_id} already running")
            return
        
        self._running = True
        self._connect()
        
        logger.info(f"USB camera started: {self.camera_id}")
    
    def stop(self) -> None:
        """Stop camera stream."""
        self._running = False
        self._disconnect()
        
        logger.info(f"USB camera stopped: {self.camera_id}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get latest frame from camera.
        
        Returns:
            Frame as numpy array (BGR format) or None if unavailable
        """
        if not self._running:
            return None
        
        # Try to reconnect if disconnected
        if not self._connected and self.auto_reconnect:
            self._connect()
            if not self._connected:
                return None
        
        try:
            # Read frame from capture
            ret, frame = self._capture.read()
            
            if not ret or frame is None:
                logger.warning(f"Failed to read frame from {self.camera_id}")
                self._error_count += 1
                self._total_errors += 1
                
                # Reconnect after multiple failures
                if self._error_count >= 5 and self.auto_reconnect:
                    logger.error(f"Too many errors, reconnecting {self.camera_id}")
                    self._disconnect()
                    time.sleep(1)
                    self._connect()
                
                # Return last known good frame
                with self._lock:
                    return self._last_frame
            
            # Resize frame if needed
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))
            
            # Update statistics
            self._frame_count += 1
            self._error_count = 0
            
            # Cache frame
            with self._lock:
                self._last_frame = frame.copy()
                self._last_frame_time = time.time()
            
            return frame
            
        except Exception as e:
            logger.error(f"Error reading frame from {self.camera_id}: {e}")
            self._error_count += 1
            self._total_errors += 1
            
            with self._lock:
                return self._last_frame
    
    def is_opened(self) -> bool:
        """Check if camera is connected."""
        return self._connected and self._capture is not None and self._capture.isOpened()
    
    def get_fps(self) -> float:
        """Get actual FPS."""
        if self._capture is None or not self._capture.isOpened():
            return 0.0
        
        try:
            actual_fps = self._capture.get(cv2.CAP_PROP_FPS)
            # Some webcams return 0, fallback to configured FPS
            return float(actual_fps) if actual_fps > 0 else float(self.fps)
        except Exception:
            return float(self.fps)
    
    def get_resolution(self) -> tuple[int, int]:
        """Get frame resolution (width, height)."""
        if self._capture and self._capture.isOpened():
            try:
                actual_width = int(self._capture.get(cv2.CAP_PROP_FRAME_WIDTH))
                actual_height = int(self._capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
                if actual_width > 0 and actual_height > 0:
                    return (actual_width, actual_height)
            except Exception:
                pass
        
        return (self.width, self.height)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera statistics."""
        with self._lock:
            last_frame_age = None
            if self._last_frame_time:
                last_frame_age = time.time() - self._last_frame_time
        
        return {
            "camera_id": self.camera_id,
            "type": "usb",
            "device_index": self.device_index,
            "connected": self._connected,
            "running": self._running,
            "frame_count": self._frame_count,
            "error_count": self._total_errors,
            "fps": self.get_fps(),
            "resolution": self.get_resolution(),
            "last_frame_age_seconds": last_frame_age,
        }
    
    def _connect(self) -> None:
        """Establish connection to USB camera."""
        try:
            logger.info(f"Connecting to USB camera: {self.camera_id} (device: {self.device_index})")
            
            # Create capture object
            self._capture = cv2.VideoCapture(self.device_index)
            
            # Verify connection
            if not self._capture.isOpened():
                raise ConnectionError(f"Failed to open USB device: {self.device_index}")
            
            # Set resolution
            self._capture.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self._capture.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            # Set FPS (may not be supported by all cameras)
            self._capture.set(cv2.CAP_PROP_FPS, self.fps)
            
            self._connected = True
            actual_res = self.get_resolution()
            logger.info(
                f"USB camera connected: {self.camera_id} "
                f"(resolution: {actual_res[0]}x{actual_res[1]}, fps: {self.get_fps()})"
            )
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.camera_id}: {e}")
            self._connected = False
            if self._capture:
                self._capture.release()
                self._capture = None
    
    def _disconnect(self) -> None:
        """Close connection to USB camera."""
        self._connected = False
        
        if self._capture:
            try:
                self._capture.release()
            except Exception as e:
                logger.error(f"Error releasing capture for {self.camera_id}: {e}")
            finally:
                self._capture = None
        
        logger.info(f"USB camera disconnected: {self.camera_id}")
    
    @staticmethod
    def list_available_cameras() -> List[int]:
        """
        List available USB camera devices.
        
        Returns:
            List of available device indices
        """
        available = []
        
        # Test first 10 device indices
        for index in range(10):
            try:
                cap = cv2.VideoCapture(index)
                if cap.isOpened():
                    ret, _ = cap.read()
                    if ret:
                        available.append(index)
                cap.release()
            except Exception:
                pass
        
        return available