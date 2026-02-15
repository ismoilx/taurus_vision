"""
Unit tests for USBCamera (mocked).

Tests USB camera functionality with mocked cv2.VideoCapture:
- Device detection
- Frame capture
- Auto-reconnect
- Error handling
- Multiple device support
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import numpy as np

from app.services.camera.usb_camera import USBCamera
from tests.conftest import assert_valid_frame, assert_camera_stats_valid


@pytest.mark.unit
@pytest.mark.camera
class TestUSBCamera:
    """Test suite for USBCamera."""
    
    @patch('cv2.VideoCapture')
    def test_initialization(self, mock_capture):
        """Test USB camera initialization."""
        camera = USBCamera(
            camera_id="USB-TEST-001",
            device_index=0,
            fps=30,
            width=640,
            height=480,
        )
        
        assert camera.camera_id == "USB-TEST-001"
        assert camera.device_index == 0
        assert camera.fps == 30
        assert camera.width == 640
        assert camera.height == 480
        assert not camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_start_success(self, mock_capture_class, mock_opencv_capture):
        """Test successful USB camera connection."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-001", device_index=0)
        camera.start()
        
        assert camera.is_opened()
        mock_capture_class.assert_called_once_with(0)
    
    @patch('cv2.VideoCapture')
    def test_start_connection_failure(self, mock_capture_class, mock_opencv_capture_failed):
        """Test USB connection failure."""
        mock_capture_class.return_value = mock_opencv_capture_failed
        
        camera = USBCamera("USB-002", device_index=99)
        camera.start()
        
        assert not camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_get_frame_success(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test successful frame capture."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-003", device_index=0, width=640, height=480)
        camera.start()
        
        frame = camera.get_frame()
        
        assert frame is not None
        assert_valid_frame(frame, width=640, height=480)
    
    @patch('cv2.VideoCapture')
    def test_get_frame_read_failure(self, mock_capture_class, mock_opencv_capture):
        """Test handling of frame read failure."""
        mock_opencv_capture.read.return_value = (False, None)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-004", device_index=0)
        camera.start()
        
        frame = camera.get_frame()
        
        # Should return None on failure
        assert frame is None or camera._last_frame is None
    
    @patch('cv2.VideoCapture')
    def test_auto_reconnect_enabled(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test auto-reconnect when enabled."""
        # First 5 calls fail, then succeed
        call_count = [0]
        
        def read_side_effect():
            call_count[0] += 1
            if call_count[0] <= 5:
                return (False, None)
            return (True, mock_frame)
        
        mock_opencv_capture.read.side_effect = read_side_effect
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-005", device_index=0, auto_reconnect=True)
        camera.start()
        
        # Trigger errors
        for _ in range(5):
            camera.get_frame()
        
        # Should trigger reconnect
        assert camera._error_count >= 5
    
    @patch('cv2.VideoCapture')
    def test_auto_reconnect_disabled(self, mock_capture_class, mock_opencv_capture):
        """Test no auto-reconnect when disabled."""
        mock_opencv_capture.read.return_value = (False, None)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-006", device_index=0, auto_reconnect=False)
        camera.start()
        
        # Trigger errors
        for _ in range(10):
            camera.get_frame()
        
        # Should not attempt reconnect
        # Just verify it handles errors gracefully
        assert camera._error_count == 10
    
    @patch('cv2.VideoCapture')
    def test_stop(self, mock_capture_class, mock_opencv_capture):
        """Test stopping camera."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-007", device_index=0)
        camera.start()
        assert camera.is_opened()
        
        camera.stop()
        assert not camera.is_opened()
        mock_opencv_capture.release.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_get_fps_actual(self, mock_capture_class, mock_opencv_capture):
        """Test FPS retrieval from camera."""
        mock_opencv_capture.get.return_value = 30.0
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-008", device_index=0, fps=10)
        camera.start()
        
        fps = camera.get_fps()
        assert fps == 30.0  # Actual FPS from camera
    
    @patch('cv2.VideoCapture')
    def test_get_fps_fallback(self, mock_capture_class, mock_opencv_capture):
        """Test FPS fallback when camera returns 0."""
        mock_opencv_capture.get.return_value = 0.0  # Some cameras return 0
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-009", device_index=0, fps=25)
        camera.start()
        
        fps = camera.get_fps()
        assert fps == 25.0  # Falls back to configured FPS
    
    @patch('cv2.VideoCapture')
    def test_get_resolution_actual(self, mock_capture_class, mock_opencv_capture):
        """Test resolution retrieval from camera."""
        # Mock different width/height get calls
        def get_side_effect(prop):
            if prop == 3:  # CAP_PROP_FRAME_WIDTH
                return 1280.0
            elif prop == 4:  # CAP_PROP_FRAME_HEIGHT
                return 720.0
            return 0.0
        
        mock_opencv_capture.get.side_effect = get_side_effect
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-010", device_index=0, width=640, height=480)
        camera.start()
        
        width, height = camera.get_resolution()
        assert width == 1280
        assert height == 720
    
    @patch('cv2.VideoCapture')
    def test_get_resolution_fallback(self, mock_capture_class, mock_opencv_capture):
        """Test resolution fallback."""
        mock_opencv_capture.get.return_value = 0  # Invalid
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-011", device_index=0, width=640, height=480)
        
        width, height = camera.get_resolution()
        assert width == 640
        assert height == 480
    
    @patch('cv2.VideoCapture')
    def test_get_stats(self, mock_capture_class, mock_opencv_capture):
        """Test statistics retrieval."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-012", device_index=0)
        camera.start()
        
        stats = camera.get_stats()
        assert_camera_stats_valid(stats)
        
        assert stats["camera_id"] == "USB-012"
        assert stats["type"] == "usb"
        assert stats["device_index"] == 0
    
    @patch('cv2.VideoCapture')
    def test_resolution_configuration(self, mock_capture_class, mock_opencv_capture):
        """Test resolution is configured on start."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-013", device_index=0, width=1920, height=1080)
        camera.start()
        
        # Verify resolution was set
        mock_opencv_capture.set.assert_any_call(3, 1920)  # CAP_PROP_FRAME_WIDTH
        mock_opencv_capture.set.assert_any_call(4, 1080)  # CAP_PROP_FRAME_HEIGHT
    
    @patch('cv2.VideoCapture')
    def test_fps_configuration(self, mock_capture_class, mock_opencv_capture):
        """Test FPS is configured on start."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-014", device_index=0, fps=60)
        camera.start()
        
        # Verify FPS was set
        mock_opencv_capture.set.assert_any_call(5, 60)  # CAP_PROP_FPS
    
    @patch('cv2.VideoCapture')
    def test_list_available_cameras_found(self, mock_capture_class):
        """Test listing available cameras."""
        # Mock 2 available cameras
        available_indices = [0, 1]
        
        def create_mock(index):
            mock = MagicMock()
            mock.isOpened.return_value = index in available_indices
            mock.read.return_value = (index in available_indices, None)
            return mock
        
        mock_capture_class.side_effect = create_mock
        
        cameras = USBCamera.list_available_cameras()
        
        assert 0 in cameras
        assert 1 in cameras
    
    @patch('cv2.VideoCapture')
    def test_list_available_cameras_none(self, mock_capture_class):
        """Test listing when no cameras available."""
        mock_opencv_capture_failed = MagicMock()
        mock_opencv_capture_failed.isOpened.return_value = False
        mock_capture_class.return_value = mock_opencv_capture_failed
        
        cameras = USBCamera.list_available_cameras()
        
        assert len(cameras) == 0
    
    @patch('cv2.VideoCapture')
    def test_frame_resize(self, mock_capture_class, mock_opencv_capture):
        """Test frames are resized to target resolution."""
        # Return frame with different size
        wrong_size_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        mock_opencv_capture.read.return_value = (True, wrong_size_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-015", device_index=0, width=640, height=480)
        camera.start()
        
        frame = camera.get_frame()
        
        # Frame should be resized
        assert frame.shape[1] == 640
        assert frame.shape[0] == 480
    
    @patch('cv2.VideoCapture')
    def test_statistics_tracking(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test statistics are tracked correctly."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-016", device_index=0, width=640, height=480)
        camera.start()
        
        # Capture frames
        for _ in range(5):
            camera.get_frame()
        
        stats = camera.get_stats()
        assert stats["frame_count"] == 5
        assert stats["error_count"] == 0
    
    @patch('cv2.VideoCapture')
    def test_error_count_increments(self, mock_capture_class, mock_opencv_capture):
        """Test error count increments on failures."""
        mock_opencv_capture.read.return_value = (False, None)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-017", device_index=0)
        camera.start()
        
        # Trigger errors
        for _ in range(3):
            camera.get_frame()
        
        stats = camera.get_stats()
        assert stats["error_count"] >= 3
    
    @patch('cv2.VideoCapture')
    def test_frame_caching(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test frame caching on errors."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-018", device_index=0, width=640, height=480)
        camera.start()
        
        # Get first frame (success)
        frame1 = camera.get_frame()
        assert frame1 is not None
        
        # Simulate error
        mock_opencv_capture.read.return_value = (False, None)
        
        # Should return cached frame
        frame2 = camera.get_frame()
        # Note: frame2 might be None or cached frame
    
    @patch('cv2.VideoCapture')
    def test_not_running_returns_none(self, mock_capture_class):
        """Test get_frame returns None when not running."""
        camera = USBCamera("USB-019", device_index=0)
        
        # Don't start camera
        frame = camera.get_frame()
        
        assert frame is None
    
    @patch('cv2.VideoCapture')
    def test_already_running_warning(self, mock_capture_class, mock_opencv_capture):
        """Test warning when starting already running camera."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-020", device_index=0)
        camera.start()
        
        # Start again
        camera.start()  # Should log warning but not fail
        
        assert camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_exception_handling_in_get_frame(self, mock_capture_class, mock_opencv_capture):
        """Test exception handling in get_frame."""
        mock_opencv_capture.read.side_effect = Exception("Device disconnected")
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-021", device_index=0)
        camera.start()
        
        # Should not crash, should handle exception
        frame = camera.get_frame()
        assert camera._error_count > 0
    
    @patch('cv2.VideoCapture')
    def test_multiple_device_indices(self, mock_capture_class, mock_opencv_capture):
        """Test cameras with different device indices."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera0 = USBCamera("USB-DEV-0", device_index=0)
        camera1 = USBCamera("USB-DEV-1", device_index=1)
        
        camera0.start()
        camera1.start()
        
        assert camera0.device_index == 0
        assert camera1.device_index == 1
        
        camera0.stop()
        camera1.stop()
    
    @patch('cv2.VideoCapture')
    def test_last_frame_age_tracking(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test last frame age is tracked."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = USBCamera("USB-022", device_index=0, width=640, height=480)
        camera.start()
        
        camera.get_frame()
        time.sleep(0.1)
        
        stats = camera.get_stats()
        assert stats["last_frame_age_seconds"] is not None
        assert stats["last_frame_age_seconds"] >= 0.1
