"""
RTSP Camera implementation for IP cameras.

Supports:
- RTSP/RTMP streams
- H.264/H.265 codecs
- Auto-reconnect on failure
- Configurable timeout and buffer
"""

import cv2
import time
import logging
import threading
from typing import Optional, Dict, Any
from datetime import datetime
import numpy as np

from app.services.camera.base import CameraInterface


logger = logging.getLogger(__name__)


class RTSPCamera(CameraInterface):
    """
    RTSP camera implementation for IP cameras.
    
    Supports standard RTSP streams from IP cameras:
    - rtsp://username:password@ip:port/stream
    - rtsp://ip:port/stream
    
    Features:
    - Auto-reconnect on connection loss
    - Configurable buffer size
    - Frame timeout handling
    - Connection health monitoring
    """
    
    def __init__(
        self,
        camera_id: str,
        rtsp_url: str,
        fps: int = 10,
        width: int = 1920,
        height: int = 1080,
        reconnect_interval: int = 5,
        connection_timeout: int = 10,
        buffer_size: int = 1,
    ):
        """
        Initialize RTSP camera.
        
        Args:
            camera_id: Unique camera identifier
            rtsp_url: RTSP stream URL
            fps: Target frames per second
            width: Frame width
            height: Frame height
            reconnect_interval: Seconds between reconnect attempts
            connection_timeout: Connection timeout in seconds
            buffer_size: OpenCV buffer size (1 = latest frame only)
        """
        self.camera_id = camera_id
        self.rtsp_url = rtsp_url
        self.fps = fps
        self.width = width
        self.height = height
        self.reconnect_interval = reconnect_interval
        self.connection_timeout = connection_timeout
        self.buffer_size = buffer_size
        
        self._capture: Optional[cv2.VideoCapture] = None
        self._running = False
        self._connected = False
        self._last_frame: Optional[np.ndarray] = None
        self._last_frame_time: Optional[float] = None
        self._frame_count = 0
        self._error_count = 0
        self._total_errors = 0
        self._lock = threading.Lock()
        
        logger.info(f"RTSP camera initialized: {camera_id}")
    
    def start(self) -> None:
        """Start camera stream."""
        if self._running:
            logger.warning(f"Camera {self.camera_id} already running")
            return
        
        self._running = True
        self._connect()
        
        logger.info(f"RTSP camera started: {self.camera_id}")
    
    def stop(self) -> None:
        """Stop camera stream."""
        self._running = False
        self._disconnect()
        
        logger.info(f"RTSP camera stopped: {self.camera_id}")
    
    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get latest frame from camera.
        
        Returns:
            Frame as numpy array (BGR format) or None if unavailable
        """
        if not self._running:
            return None
        
        # Try to reconnect if disconnected
        if not self._connected:
            self._connect()
            if not self._connected:
                self._error_count += 1
                self._total_errors += 1
                return None
        
        try:
            # Read frame from capture
            ret, frame = self._capture.read()
            
            if not ret or frame is None:
                logger.warning(f"Failed to read frame from {self.camera_id}")
                self._error_count += 1
                self._total_errors += 1
                
                # Reconnect after multiple failures
                if self._error_count >= 10 and self._error_count % 10 == 0:
                    logger.error(f"Too many errors, reconnecting {self.camera_id}")
                    self._disconnect()
                    time.sleep(self.reconnect_interval)
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
            return float(self._capture.get(cv2.CAP_PROP_FPS))
        except Exception:
            return float(self.fps)
    
    def get_resolution(self) -> tuple[int, int]:
        """Get frame resolution (width, height)."""
        return (self.width, self.height)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get camera statistics."""
        with self._lock:
            last_frame_age = None
            if self._last_frame_time:
                last_frame_age = time.time() - self._last_frame_time
        
        return {
            "camera_id": self.camera_id,
            "type": "rtsp",
            "url": self._mask_credentials(self.rtsp_url),
            "connected": self._connected,
            "running": self._running,
            "frame_count": self._frame_count,
            "error_count": self._error_count,
            "fps": self.get_fps(),
            "resolution": self.get_resolution(),
            "last_frame_age_seconds": last_frame_age,
        }
    
    def _connect(self) -> None:
        """Establish connection to RTSP stream."""
        try:
            logger.info(f"Connecting to RTSP stream: {self.camera_id}")
            
            # Create capture object
            self._capture = cv2.VideoCapture(self.rtsp_url)
            
            # Set buffer size (1 = no buffering, always latest frame)
            self._capture.set(38, self.buffer_size)   # CAP_PROP_BUFFERSIZE = 38
            
            # Set timeout
            self._capture.set(41, self.connection_timeout * 1000)   # CAP_PROP_OPEN_TIMEOUT_MSEC = 41 (legacy)
            
            # Verify connection
            if not self._capture.isOpened():
                raise ConnectionError(f"Failed to open RTSP stream: {self.camera_id}")
            
            # Connection established
            self._connected = True
            logger.info(f"RTSP camera connected: {self.camera_id}")
            
        except Exception as e:
            logger.error(f"Failed to connect to {self.camera_id}: {e}")
            self._connected = False
            if self._capture:
                self._capture.release()
                self._capture = None
    
    def _disconnect(self) -> None:
        """Close connection to RTSP stream."""
        self._connected = False
        
        if self._capture:
            try:
                self._capture.release()
            except Exception as e:
                logger.error(f"Error releasing capture for {self.camera_id}: {e}")
            finally:
                self._capture = None
        
        logger.info(f"RTSP camera disconnected: {self.camera_id}")
    
    @staticmethod
    def _mask_credentials(url: str) -> str:
        """Mask username and password in RTSP URL for logging."""
        import re
        # rtsp://username:password@host -> rtsp://***:***@host
        return re.sub(r'://([^:]+):([^@]+)@', r'://***:***@', url)