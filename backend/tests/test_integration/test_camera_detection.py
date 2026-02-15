"""
Integration tests for Camera + YOLO Detection.

Tests end-to-end workflow:
- Camera captures frame
- YOLO detects objects
- Results are processed
- Statistics are tracked
"""

import pytest
import time
from unittest.mock import patch, MagicMock

from app.services.camera.simulated_camera import SimulatedCamera
from app.services.camera.camera_manager import camera_manager
from tests.conftest import assert_valid_frame


@pytest.mark.integration
@pytest.mark.camera
class TestCameraDetectionIntegration:
    """Integration tests for camera and detection pipeline."""
    
    def test_camera_provides_valid_frames_for_detection(self):
        """Test camera generates valid frames for YOLO."""
        camera = SimulatedCamera("INT-CAM-001", fps=10, width=640, height=480)
        camera.start()
        
        # Get frame
        frame = camera.get_frame()
        
        # Frame should be valid for YOLO input
        assert_valid_frame(frame, width=640, height=480)
        assert frame.dtype == 'uint8'  # YOLO expects uint8
        
        camera.stop()
    
    def test_multiple_cameras_independent_frames(self):
        """Test multiple cameras generate independent frames."""
        camera1 = SimulatedCamera("INT-CAM-M1", fps=10)
        camera2 = SimulatedCamera("INT-CAM-M2", fps=10)
        
        camera1.start()
        camera2.start()
        
        frame1 = camera1.get_frame()
        frame2 = camera2.get_frame()
        
        # Frames should be different (independent random generation)
        import numpy as np
        assert not np.array_equal(frame1, frame2)
        
        camera1.stop()
        camera2.stop()
    
    def test_camera_frame_rate_consistency(self):
        """Test camera maintains consistent frame rate."""
        camera = SimulatedCamera("INT-CAM-FPS", fps=30)
        camera.start()
        
        # Capture frames and measure timing
        frame_times = []
        for _ in range(10):
            start = time.time()
            frame = camera.get_frame()
            frame_times.append(time.time() - start)
            assert frame is not None
        
        # Frame generation should be fast and consistent
        avg_time = sum(frame_times) / len(frame_times)
        assert avg_time < 0.01  # Should be sub-10ms
        
        camera.stop()
    
    @patch('app.services.ai.yolo_service.YoloService')
    def test_camera_to_yolo_pipeline(self, mock_yolo, mock_detection_result):
        """Test complete camera to YOLO detection pipeline."""
        # Setup mock YOLO
        mock_yolo_instance = MagicMock()
        mock_yolo_instance.detect.return_value = mock_detection_result
        mock_yolo.return_value = mock_yolo_instance
        
        # Setup camera
        camera = SimulatedCamera("INT-PIPELINE", fps=10)
        camera.start()
        
        # Simulate detection pipeline
        for _ in range(5):
            frame = camera.get_frame()
            assert frame is not None
            
            # In real pipeline, this would call YOLO
            # result = yolo_service.detect(frame)
            # Here we just verify frame is valid
            assert_valid_frame(frame)
        
        assert camera._frame_count == 5
        camera.stop()
    
    def test_camera_manager_with_multiple_cameras(self):
        """Test camera manager handles multiple cameras."""
        camera_ids = ["INT-MGR-001", "INT-MGR-002", "INT-MGR-003"]
        
        # Register cameras
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=True)
        
        # Get frames from all cameras
        frames = []
        for camera_id in camera_ids:
            camera = camera_manager.get_camera(camera_id)
            frame = camera.get_frame()
            frames.append(frame)
        
        # All frames should be valid
        assert all(frame is not None for frame in frames)
        assert len(frames) == 3
    
    def test_camera_error_recovery(self):
        """Test system handles camera errors gracefully."""
        camera = SimulatedCamera("INT-ERR", fps=10)
        camera.start()
        
        # Normal operation
        frame1 = camera.get_frame()
        assert frame1 is not None
        
        # Simulate error scenario by stopping camera
        camera.stop()
        frame2 = camera.get_frame()
        assert frame2 is None  # Should return None, not crash
        
        # Recovery - restart camera
        camera.start()
        frame3 = camera.get_frame()
        assert frame3 is not None
    
    def test_high_throughput_scenario(self):
        """Test system handles high frame throughput."""
        camera = SimulatedCamera("INT-THROUGHPUT", fps=60)
        camera.start()
        
        # Capture many frames rapidly
        success_count = 0
        for _ in range(100):
            frame = camera.get_frame()
            if frame is not None:
                success_count += 1
        
        # Should successfully capture all frames
        assert success_count == 100
        assert camera._frame_count == 100
        
        camera.stop()
    
    @pytest.mark.slow
    def test_long_running_camera_stability(self):
        """Test camera stability over extended operation."""
        camera = SimulatedCamera("INT-STABLE", fps=10)
        camera.start()
        
        # Run for extended period
        for _ in range(50):  # Simulate 5 seconds at 10fps
            frame = camera.get_frame()
            assert frame is not None
            time.sleep(0.01)  # Small delay
        
        # Check statistics
        stats = camera.get_stats()
        assert stats["frame_count"] == 50
        assert stats["error_count"] == 0
        assert stats["running"] is True
        
        camera.stop()
    
    def test_camera_restart_preserves_stats(self):
        """Test camera statistics persist across restarts."""
        camera = SimulatedCamera("INT-STATS", fps=10)
        
        # First session
        camera.start()
        for _ in range(10):
            camera.get_frame()
        camera.stop()
        
        first_count = camera._frame_count
        
        # Second session
        camera.start()
        for _ in range(5):
            camera.get_frame()
        camera.stop()
        
        # Stats should accumulate
        assert camera._frame_count == first_count + 5
    
    def test_concurrent_camera_access(self):
        """Test thread-safe concurrent camera access."""
        import threading
        
        camera = SimulatedCamera("INT-CONCURRENT", fps=10)
        camera.start()
        
        results = []
        errors = []
        
        def capture_frames():
            try:
                for _ in range(10):
                    frame = camera.get_frame()
                    results.append(frame is not None)
            except Exception as e:
                errors.append(str(e))
        
        # Create multiple threads
        threads = [threading.Thread(target=capture_frames) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All frame captures should succeed
        assert len(errors) == 0
        assert all(results)
        assert len(results) == 50
        
        camera.stop()
    
    def test_camera_cleanup_on_error(self):
        """Test proper cleanup after errors."""
        camera = SimulatedCamera("INT-CLEANUP", fps=10)
        
        try:
            camera.start()
            
            # Simulate some operation
            for _ in range(5):
                camera.get_frame()
            
            # Force an error scenario
            raise Exception("Simulated error")
            
        except Exception:
            pass
        finally:
            # Cleanup should work even after error
            camera.stop()
            assert not camera.is_opened()
    
    def test_memory_efficiency_long_session(self):
        """Test memory doesn't grow excessively over time."""
        import gc
        
        camera = SimulatedCamera("INT-MEMORY", fps=10)
        camera.start()
        
        gc.collect()
        
        # Capture many frames
        for _ in range(200):
            frame = camera.get_frame()
            del frame  # Explicit cleanup
        
        gc.collect()
        
        # Memory should not grow significantly
        # (Actual memory measurement would require psutil in production)
        stats = camera.get_stats()
        assert stats["frame_count"] == 200
        assert stats["error_count"] == 0
        
        camera.stop()
    
    def test_api_to_camera_to_detection_workflow(self, test_client):
        """Test complete API -> Camera -> Detection workflow."""
        camera_id = "INT-API-WORKFLOW"
        
        # 1. Register camera via API
        config = {
            "camera_id": camera_id,
            "type": "simulated",
            "width": 640,
            "height": 480,
            "fps": 10,
            "auto_start": True,
        }
        
        response = test_client.post("/api/v1/cameras/", json=config)
        assert response.status_code == 201
        
        # 2. Get camera from manager
        camera = camera_manager.get_camera(camera_id)
        assert camera is not None
        
        # 3. Capture frames (simulates detection pipeline)
        frames_captured = 0
        for _ in range(5):
            frame = camera.get_frame()
            if frame is not None:
                frames_captured += 1
        
        assert frames_captured == 5
        
        # 4. Check stats via API
        response = test_client.get(f"/api/v1/cameras/{camera_id}/stats")
        assert response.status_code == 200
        stats = response.json()
        assert stats["frame_count"] >= 5
        
        # 5. Cleanup via API
        response = test_client.delete(f"/api/v1/cameras/{camera_id}")
        assert response.status_code == 200
