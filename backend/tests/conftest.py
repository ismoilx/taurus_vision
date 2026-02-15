"""
Global pytest fixtures and configuration.

Provides reusable fixtures for all tests:
- Mock cameras
- Test data
- Database fixtures
- API client
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
import numpy as np
from unittest.mock import Mock, MagicMock, patch
from fastapi.testclient import TestClient

from app.main import app
from app.services.camera.camera_manager import camera_manager


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_client() -> Generator[TestClient, None, None]:
    """
    FastAPI test client.
    
    Provides synchronous HTTP client for API testing.
    """
    client = TestClient(app)
    yield client


@pytest.fixture
def mock_frame() -> np.ndarray:
    """
    Generate mock camera frame.
    
    Returns 640x480 BGR image with random content.
    """
    return np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)


@pytest.fixture
def mock_large_frame() -> np.ndarray:
    """
    Generate large mock frame (1920x1080).
    """
    return np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)


@pytest.fixture
def sample_camera_config() -> dict:
    """
    Sample camera configuration.
    """
    return {
        "camera_id": "TEST-CAM-001",
        "type": "simulated",
        "fps": 10,
        "width": 640,
        "height": 480,
        "auto_start": True,
    }


@pytest.fixture
def sample_rtsp_config() -> dict:
    """
    Sample RTSP camera configuration.
    """
    return {
        "camera_id": "RTSP-TEST-001",
        "type": "rtsp",
        "url": "rtsp://test:test@localhost:554/stream",
        "fps": 25,
        "width": 1920,
        "height": 1080,
        "reconnect_interval": 5,
        "connection_timeout": 10,
        "auto_start": False,
    }


@pytest.fixture
def sample_usb_config() -> dict:
    """
    Sample USB camera configuration.
    """
    return {
        "camera_id": "USB-TEST-001",
        "type": "usb",
        "device_index": 0,
        "fps": 30,
        "width": 640,
        "height": 480,
        "auto_reconnect": True,
        "auto_start": False,
    }


@pytest.fixture
def mock_opencv_capture():
    """
    Mock cv2.VideoCapture for testing without actual camera.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.get.return_value = 30.0  # FPS
    mock_cap.read.return_value = (True, np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8))
    return mock_cap


@pytest.fixture
def mock_opencv_capture_failed():
    """
    Mock failed cv2.VideoCapture.
    """
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False
    mock_cap.read.return_value = (False, None)
    return mock_cap


@pytest.fixture(autouse=True)
def cleanup_camera_manager():
    """
    Cleanup camera manager after each test.
    
    Ensures tests don't interfere with each other.
    """
    yield
    # Cleanup all cameras after test
    try:
        camera_manager.stop_all()
        for camera_id in list(camera_manager.list_cameras()):
            camera_manager.unregister_camera(camera_id)
    except Exception:
        pass


@pytest.fixture
def mock_yolo_service():
    """
    Mock YOLO service for integration tests.
    """
    mock_service = MagicMock()
    mock_service._initialized = True
    mock_service.detect.return_value = {
        "detections": [
            {
                "class_id": 19,  # cow
                "class_name": "cow",
                "confidence": 0.85,
                "bbox": [100, 100, 300, 300],
            }
        ],
        "count": 1,
        "inference_time": 0.05,
    }
    return mock_service


@pytest.fixture
def mock_detection_result():
    """
    Mock detection result from YOLO.
    """
    return {
        "detections": [
            {
                "class_id": 19,
                "class_name": "cow",
                "confidence": 0.85,
                "bbox": [100, 100, 300, 300],
            },
            {
                "class_id": 19,
                "class_name": "cow",
                "confidence": 0.78,
                "bbox": [400, 150, 600, 350],
            },
        ],
        "count": 2,
        "inference_time": 0.05,
    }


# Performance measurement utilities

class PerformanceMonitor:
    """Helper class for performance testing."""
    
    def __init__(self):
        self.measurements = []
    
    def measure(self, func, *args, **kwargs):
        """Measure function execution time."""
        import time
        start = time.time()
        result = func(*args, **kwargs)
        duration = time.time() - start
        self.measurements.append(duration)
        return result, duration
    
    def average(self):
        """Get average execution time."""
        return sum(self.measurements) / len(self.measurements) if self.measurements else 0
    
    def max(self):
        """Get maximum execution time."""
        return max(self.measurements) if self.measurements else 0


@pytest.fixture
def performance_monitor():
    """Performance monitoring fixture."""
    return PerformanceMonitor()


# Custom assertions

def assert_valid_frame(frame: np.ndarray, width: int = None, height: int = None):
    """
    Assert frame is valid.
    
    Args:
        frame: Frame to validate
        width: Expected width (optional)
        height: Expected height (optional)
    """
    assert frame is not None, "Frame is None"
    assert isinstance(frame, np.ndarray), "Frame is not numpy array"
    assert len(frame.shape) == 3, "Frame is not 3D array (HxWxC)"
    assert frame.shape[2] == 3, "Frame does not have 3 channels (BGR)"
    
    if width is not None:
        assert frame.shape[1] == width, f"Frame width {frame.shape[1]} != expected {width}"
    
    if height is not None:
        assert frame.shape[0] == height, f"Frame height {frame.shape[0]} != expected {height}"


def assert_camera_stats_valid(stats: dict):
    """
    Assert camera statistics are valid.
    
    Args:
        stats: Camera statistics dictionary
    """
    required_keys = [
        "camera_id", "type", "connected", "running",
        "frame_count", "error_count", "fps", "resolution"
    ]
    
    for key in required_keys:
        assert key in stats, f"Missing key: {key}"
    
    assert isinstance(stats["frame_count"], int), "frame_count not int"
    assert isinstance(stats["error_count"], int), "error_count not int"
    assert isinstance(stats["fps"], (int, float)), "fps not numeric"
    assert isinstance(stats["resolution"], (list, tuple)), "resolution not list/tuple"
    assert len(stats["resolution"]) == 2, "resolution not (width, height)"
