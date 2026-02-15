"""
Unit tests for SimulatedCamera.

Tests all functionality of simulated camera:
- Initialization
- Start/stop
- Frame generation
- Statistics
- Error handling
"""

import pytest
import time
import numpy as np

from app.services.camera.simulated_camera import SimulatedCamera
from tests.conftest import assert_valid_frame, assert_camera_stats_valid


@pytest.mark.unit
@pytest.mark.camera
class TestSimulatedCamera:
    """Test suite for SimulatedCamera."""
    
    def test_initialization(self):
        """Test camera initialization."""
        camera = SimulatedCamera(
            camera_id="TEST-SIM-001",
            fps=10,
            width=640,
            height=480,
        )
        
        assert camera.camera_id == "TEST-SIM-001"
        assert camera.fps == 10
        assert camera.width == 640
        assert camera.height == 480
        assert not camera.is_opened()
        assert camera._frame_count == 0
    
    def test_start_stop(self):
        """Test camera start and stop."""
        camera = SimulatedCamera("TEST-SIM-002", fps=10)
        
        # Initially not running
        assert not camera.is_opened()
        
        # Start camera
        camera.start()
        assert camera.is_opened()
        
        # Stop camera
        camera.stop()
        assert not camera.is_opened()
    
    def test_start_already_running(self):
        """Test starting already running camera."""
        camera = SimulatedCamera("TEST-SIM-003", fps=10)
        
        camera.start()
        assert camera.is_opened()
        
        # Start again (should log warning but not fail)
        camera.start()
        assert camera.is_opened()
        
        camera.stop()
    
    def test_get_frame_not_started(self):
        """Test getting frame from non-started camera."""
        camera = SimulatedCamera("TEST-SIM-004", fps=10)
        
        # Should return None when not started
        frame = camera.get_frame()
        assert frame is None
    
    def test_get_frame_success(self):
        """Test successful frame capture."""
        camera = SimulatedCamera(
            "TEST-SIM-005",
            fps=10,
            width=640,
            height=480,
        )
        
        camera.start()
        frame = camera.get_frame()
        
        # Validate frame
        assert_valid_frame(frame, width=640, height=480)
        assert camera._frame_count == 1
        
        camera.stop()
    
    def test_multiple_frames(self):
        """Test capturing multiple frames."""
        camera = SimulatedCamera("TEST-SIM-006", fps=10)
        camera.start()
        
        frames = []
        for _ in range(5):
            frame = camera.get_frame()
            assert frame is not None
            frames.append(frame)
        
        # All frames should be captured
        assert len(frames) == 5
        assert camera._frame_count == 5
        
        # Frames should be different (random generation)
        assert not np.array_equal(frames[0], frames[1])
        
        camera.stop()
    
    def test_frame_counter_increments(self):
        """Test frame counter increments correctly."""
        camera = SimulatedCamera("TEST-SIM-007", fps=10)
        camera.start()
        
        initial_count = camera._frame_count
        
        for i in range(10):
            camera.get_frame()
            assert camera._frame_count == initial_count + i + 1
        
        camera.stop()
    
    def test_get_fps(self):
        """Test FPS getter."""
        camera = SimulatedCamera("TEST-SIM-008", fps=25)
        
        assert camera.get_fps() == 25.0
        assert isinstance(camera.get_fps(), float)
    
    def test_get_resolution(self):
        """Test resolution getter."""
        camera = SimulatedCamera(
            "TEST-SIM-009",
            fps=10,
            width=1920,
            height=1080,
        )
        
        width, height = camera.get_resolution()
        assert width == 1920
        assert height == 1080
    
    def test_get_stats_not_started(self):
        """Test statistics when camera not started."""
        camera = SimulatedCamera("TEST-SIM-010", fps=10)
        
        stats = camera.get_stats()
        assert_camera_stats_valid(stats)
        
        assert stats["camera_id"] == "TEST-SIM-010"
        assert stats["type"] == "simulated"
        assert stats["connected"] is False
        assert stats["running"] is False
        assert stats["frame_count"] == 0
        assert stats["error_count"] == 0
    
    def test_get_stats_running(self):
        """Test statistics when camera is running."""
        camera = SimulatedCamera("TEST-SIM-011", fps=30)
        camera.start()
        
        # Capture some frames
        for _ in range(5):
            camera.get_frame()
        
        stats = camera.get_stats()
        assert_camera_stats_valid(stats)
        
        assert stats["connected"] is True
        assert stats["running"] is True
        assert stats["frame_count"] == 5
        assert stats["fps"] == 30.0
        
        camera.stop()
    
    def test_stats_after_stop(self):
        """Test statistics persist after stop."""
        camera = SimulatedCamera("TEST-SIM-012", fps=10)
        camera.start()
        
        # Capture frames
        for _ in range(3):
            camera.get_frame()
        
        camera.stop()
        
        stats = camera.get_stats()
        assert stats["running"] is False
        assert stats["frame_count"] == 3  # Count persists
    
    def test_frame_has_text_overlay(self):
        """Test frames have frame counter text."""
        camera = SimulatedCamera("TEST-SIM-013", fps=10)
        camera.start()
        
        frame = camera.get_frame()
        
        # Frame should not be all zeros (has content)
        assert np.any(frame > 0)
        
        camera.stop()
    
    def test_frame_resolution_respected(self):
        """Test frames match requested resolution."""
        test_cases = [
            (320, 240),
            (640, 480),
            (1920, 1080),
            (3840, 2160),
        ]
        
        for width, height in test_cases:
            camera = SimulatedCamera(
                f"TEST-SIM-RES-{width}x{height}",
                fps=10,
                width=width,
                height=height,
            )
            camera.start()
            
            frame = camera.get_frame()
            assert frame.shape[1] == width, f"Width mismatch for {width}x{height}"
            assert frame.shape[0] == height, f"Height mismatch for {width}x{height}"
            
            camera.stop()
    
    def test_error_count_remains_zero(self):
        """Test error count stays zero for simulated camera."""
        camera = SimulatedCamera("TEST-SIM-014", fps=10)
        camera.start()
        
        # Capture many frames
        for _ in range(100):
            frame = camera.get_frame()
            assert frame is not None
        
        stats = camera.get_stats()
        assert stats["error_count"] == 0
        
        camera.stop()
    
    @pytest.mark.slow
    def test_performance_fps(self, performance_monitor):
        """Test frame generation performance."""
        camera = SimulatedCamera("TEST-SIM-PERF", fps=30)
        camera.start()
        
        # Measure frame generation time
        for _ in range(10):
            performance_monitor.measure(camera.get_frame)
        
        avg_time = performance_monitor.average()
        max_time = performance_monitor.max()
        
        # Frame generation should be fast (<10ms)
        assert avg_time < 0.01, f"Avg frame time too slow: {avg_time}s"
        assert max_time < 0.05, f"Max frame time too slow: {max_time}s"
        
        camera.stop()
    
    def test_concurrent_access(self):
        """Test thread-safe operation."""
        import threading
        
        camera = SimulatedCamera("TEST-SIM-THREAD", fps=10)
        camera.start()
        
        results = []
        
        def capture_frames():
            for _ in range(10):
                frame = camera.get_frame()
                results.append(frame is not None)
        
        # Create multiple threads
        threads = [threading.Thread(target=capture_frames) for _ in range(3)]
        
        # Start threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All frames should be captured successfully
        assert all(results)
        assert len(results) == 30
        
        camera.stop()
    
    def test_memory_leak(self):
        """Test no memory leak with many frames."""
        import gc
        import sys
        
        camera = SimulatedCamera("TEST-SIM-MEM", fps=10)
        camera.start()
        
        # Force garbage collection
        gc.collect()
        initial_objects = len(gc.get_objects())
        
        # Generate many frames
        for _ in range(1000):
            frame = camera.get_frame()
            del frame  # Explicit cleanup
        
        # Force garbage collection again
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Object count should not grow significantly
        growth = final_objects - initial_objects
        assert growth < 100, f"Potential memory leak: {growth} new objects"
        
        camera.stop()
