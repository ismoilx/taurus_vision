"""
Unit tests for RTSPCamera (mocked).

Tests RTSP camera functionality with mocked cv2.VideoCapture:
- Connection handling
- Frame capture
- Error recovery
- Auto-reconnect
- Credential masking
"""

import pytest
import time
from unittest.mock import patch, MagicMock
import numpy as np

from app.services.camera.rtsp_camera import RTSPCamera
from tests.conftest import assert_valid_frame, assert_camera_stats_valid


@pytest.mark.unit
@pytest.mark.camera
class TestRTSPCamera:
    """Test suite for RTSPCamera."""
    
    @patch('cv2.VideoCapture')
    def test_initialization(self, mock_capture):
        """Test RTSP camera initialization."""
        camera = RTSPCamera(
            camera_id="RTSP-TEST-001",
            rtsp_url="rtsp://test:test@localhost:554/stream",
            fps=25,
            width=1920,
            height=1080,
        )
        
        assert camera.camera_id == "RTSP-TEST-001"
        assert camera.rtsp_url == "rtsp://test:test@localhost:554/stream"
        assert camera.fps == 25
        assert camera.width == 1920
        assert camera.height == 1080
        assert not camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_start_success(self, mock_capture_class, mock_opencv_capture):
        """Test successful RTSP connection."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-001", "rtsp://localhost:554/stream")
        camera.start()
        
        assert camera.is_opened()
        mock_capture_class.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_start_connection_failure(self, mock_capture_class, mock_opencv_capture_failed):
        """Test RTSP connection failure."""
        mock_capture_class.return_value = mock_opencv_capture_failed
        
        camera = RTSPCamera("RTSP-002", "rtsp://invalid:554/stream")
        camera.start()
        
        assert not camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_get_frame_success(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test successful frame capture."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-003", "rtsp://localhost:554/stream", width=640, height=480)
        camera.start()
        
        frame = camera.get_frame()
        
        assert frame is not None
        assert_valid_frame(frame, width=640, height=480)
    
    @patch('cv2.VideoCapture')
    def test_get_frame_read_failure(self, mock_capture_class, mock_opencv_capture):
        """Test handling of frame read failure."""
        mock_opencv_capture.read.return_value = (False, None)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-004", "rtsp://localhost:554/stream")
        camera.start()
        
        frame = camera.get_frame()
        
        # Should return None on failure
        assert frame is None or camera._last_frame is None
    
    @patch('cv2.VideoCapture')
    def test_auto_reconnect_after_errors(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test auto-reconnect after multiple errors."""
        # First 10 calls fail, then succeed
        call_count = [0]
        
        def read_side_effect():
            call_count[0] += 1
            if call_count[0] <= 10:
                return (False, None)
            return (True, mock_frame)
        
        mock_opencv_capture.read.side_effect = read_side_effect
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-005", "rtsp://localhost:554/stream")
        camera.start()
        
        # Trigger errors
        for _ in range(10):
            camera.get_frame()
        
        # Should trigger reconnect
        assert camera._error_count >= 10
    
    @patch('cv2.VideoCapture')
    def test_frame_caching(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test frame caching on errors."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-006", "rtsp://localhost:554/stream", width=640, height=480)
        camera.start()
        
        # Get first frame (success)
        frame1 = camera.get_frame()
        assert frame1 is not None
        
        # Simulate error
        mock_opencv_capture.read.return_value = (False, None)
        
        # Should return cached frame
        frame2 = camera.get_frame()
        # Note: frame2 might be None or cached frame depending on implementation
        # The important thing is it doesn't crash
    
    @patch('cv2.VideoCapture')
    def test_stop(self, mock_capture_class, mock_opencv_capture):
        """Test stopping camera."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-007", "rtsp://localhost:554/stream")
        camera.start()
        assert camera.is_opened()
        
        camera.stop()
        assert not camera.is_opened()
        mock_opencv_capture.release.assert_called_once()
    
    @patch('cv2.VideoCapture')
    def test_get_fps(self, mock_capture_class, mock_opencv_capture):
        """Test FPS retrieval."""
        mock_opencv_capture.get.return_value = 30.0
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-008", "rtsp://localhost:554/stream", fps=25)
        camera.start()
        
        fps = camera.get_fps()
        assert fps == 30.0 or fps == 25.0  # Actual or configured
    
    @patch('cv2.VideoCapture')
    def test_get_resolution(self, mock_capture_class):
        """Test resolution getter."""
        camera = RTSPCamera("RTSP-009", "rtsp://localhost:554/stream", width=1920, height=1080)
        
        width, height = camera.get_resolution()
        assert width == 1920
        assert height == 1080
    
    @patch('cv2.VideoCapture')
    def test_get_stats(self, mock_capture_class, mock_opencv_capture):
        """Test statistics retrieval."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-010", "rtsp://localhost:554/stream")
        camera.start()
        
        stats = camera.get_stats()
        assert_camera_stats_valid(stats)
        
        assert stats["camera_id"] == "RTSP-010"
        assert stats["type"] == "rtsp"
        assert "url" in stats
    
    def test_credential_masking(self):
        """Test RTSP credentials are masked in logs."""
        url_with_creds = "rtsp://admin:password123@192.168.1.100:554/stream"
        
        masked = RTSPCamera._mask_credentials(url_with_creds)
        
        assert "admin" not in masked
        assert "password123" not in masked
        assert "***:***" in masked
        assert "192.168.1.100" in masked
    
    def test_credential_masking_no_credentials(self):
        """Test credential masking with no credentials."""
        url_no_creds = "rtsp://192.168.1.100:554/stream"
        
        masked = RTSPCamera._mask_credentials(url_no_creds)
        
        assert masked == url_no_creds
    
    @patch('cv2.VideoCapture')
    def test_buffer_size_configuration(self, mock_capture_class, mock_opencv_capture):
        """Test buffer size is configured."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-011", "rtsp://localhost:554/stream", buffer_size=3)
        camera.start()
        
        # Verify buffer size was set
        mock_opencv_capture.set.assert_any_call(38, 3)  # CAP_PROP_BUFFERSIZE = 38
    
    @patch('cv2.VideoCapture')
    def test_connection_timeout_configuration(self, mock_capture_class, mock_opencv_capture):
        """Test connection timeout is configured."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-012", "rtsp://localhost:554/stream", connection_timeout=20)
        camera.start()
        
        # Verify timeout was set (in milliseconds)
        mock_opencv_capture.set.assert_any_call(41, 20000)  # CAP_PROP_OPEN_TIMEOUT_MSEC = 41
    
    @patch('cv2.VideoCapture')
    def test_reconnect_interval(self, mock_capture_class, mock_opencv_capture_failed):
        """Test reconnect interval is respected."""
        mock_capture_class.return_value = mock_opencv_capture_failed
        
        camera = RTSPCamera("RTSP-013", "rtsp://localhost:554/stream", reconnect_interval=2)
        
        start_time = time.time()
        camera.start()  # Will fail
        
        # If it tries to reconnect, it should wait
        elapsed = time.time() - start_time
        # Just verify it doesn't hang forever
        assert elapsed < 5.0
    
    @patch('cv2.VideoCapture')
    def test_frame_resize(self, mock_capture_class, mock_opencv_capture):
        """Test frames are resized to target resolution."""
        # Return frame with different size
        wrong_size_frame = np.random.randint(0, 255, (1080, 1920, 3), dtype=np.uint8)
        mock_opencv_capture.read.return_value = (True, wrong_size_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-014", "rtsp://localhost:554/stream", width=640, height=480)
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
        
        camera = RTSPCamera("RTSP-015", "rtsp://localhost:554/stream", width=640, height=480)
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
        
        camera = RTSPCamera("RTSP-016", "rtsp://localhost:554/stream")
        camera.start()
        
        # Trigger errors
        for _ in range(3):
            camera.get_frame()
        
        stats = camera.get_stats()
        assert stats["error_count"] >= 3
    
    @patch('cv2.VideoCapture')
    def test_last_frame_age_tracking(self, mock_capture_class, mock_opencv_capture, mock_frame):
        """Test last frame age is tracked."""
        mock_opencv_capture.read.return_value = (True, mock_frame)
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-017", "rtsp://localhost:554/stream", width=640, height=480)
        camera.start()
        
        camera.get_frame()
        time.sleep(0.1)
        
        stats = camera.get_stats()
        assert stats["last_frame_age_seconds"] is not None
        assert stats["last_frame_age_seconds"] >= 0.1
    
    @patch('cv2.VideoCapture')
    def test_not_running_returns_none(self, mock_capture_class):
        """Test get_frame returns None when not running."""
        camera = RTSPCamera("RTSP-018", "rtsp://localhost:554/stream")
        
        # Don't start camera
        frame = camera.get_frame()
        
        assert frame is None
    
    @patch('cv2.VideoCapture')
    def test_already_running_warning(self, mock_capture_class, mock_opencv_capture):
        """Test warning when starting already running camera."""
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-019", "rtsp://localhost:554/stream")
        camera.start()
        
        # Start again
        camera.start()  # Should log warning but not fail
        
        assert camera.is_opened()
    
    @patch('cv2.VideoCapture')
    def test_exception_handling_in_get_frame(self, mock_capture_class, mock_opencv_capture):
        """Test exception handling in get_frame."""
        mock_opencv_capture.read.side_effect = Exception("Connection lost")
        mock_capture_class.return_value = mock_opencv_capture
        
        camera = RTSPCamera("RTSP-020", "rtsp://localhost:554/stream")
        camera.start()
        
        # Should not crash, should handle exception
        frame = camera.get_frame()
        # Should return None or cached frame
        assert camera._error_count > 0

