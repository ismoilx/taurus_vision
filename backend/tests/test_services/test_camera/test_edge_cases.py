"""
Edge case and stress tests for camera system.

Tests boundary conditions, error scenarios, and stress cases:
- Invalid configurations
- Extreme values
- Resource exhaustion
- Concurrent access
- Memory management
"""

import pytest
import threading
import time
from unittest.mock import patch, MagicMock

from app.services.camera.simulated_camera import SimulatedCamera
from app.services.camera.camera_manager import camera_manager
from app.services.camera.camera_factory import CameraFactory


@pytest.mark.unit
@pytest.mark.camera
class TestCameraEdgeCases:
    """Edge case tests for camera system."""
    
    def test_camera_id_empty_string(self):
        """Test camera with empty string ID."""
        camera = SimulatedCamera("", fps=10)
        
        assert camera.camera_id == ""
        # Should still function
        camera.start()
        frame = camera.get_frame()
        assert frame is not None
        camera.stop()
    
    def test_camera_id_special_characters(self):
        """Test camera ID with special characters."""
        special_ids = [
            "CAM-@#$%",
            "CAM-ñáéíóú",
            "CAM-汉字",
            "CAM-🎥📷",
        ]
        
        for cam_id in special_ids:
            camera = SimulatedCamera(cam_id, fps=10)
            assert camera.camera_id == cam_id
    
    def test_camera_id_very_long(self):
        """Test camera with very long ID."""
        long_id = "CAM-" + "X" * 1000
        camera = SimulatedCamera(long_id, fps=10)
        
        assert camera.camera_id == long_id
    
    def test_fps_zero(self):
        """Test camera with zero FPS."""
        camera = SimulatedCamera("CAM-FPS-0", fps=0)
        camera.start()
        
        # Should not crash
        frame = camera.get_frame()
        assert frame is not None
        
        camera.stop()
    
    def test_fps_negative(self):
        """Test camera with negative FPS."""
        camera = SimulatedCamera("CAM-FPS-NEG", fps=-10)
        camera.start()
        
        # Should handle gracefully
        camera.stop()
    
    def test_fps_extremely_high(self):
        """Test camera with extremely high FPS."""
        camera = SimulatedCamera("CAM-FPS-HIGH", fps=10000)
        camera.start()
        
        frame = camera.get_frame()
        assert frame is not None
        
        camera.stop()
    
    def test_resolution_minimum(self):
        """Test minimum resolution."""
        camera = SimulatedCamera("CAM-RES-MIN", fps=10, width=1, height=1)
        camera.start()
        
        frame = camera.get_frame()
        assert frame is not None
        assert frame.shape == (1, 1, 3)
        
        camera.stop()
    
    def test_resolution_maximum(self):
        """Test extremely large resolution."""
        camera = SimulatedCamera("CAM-RES-MAX", fps=10, width=10000, height=10000)
        camera.start()
        
        # Should handle but might be slow
        frame = camera.get_frame()
        # Just verify it doesn't crash
        
        camera.stop()
    
    def test_resolution_zero(self):
        """Test zero resolution."""
        # This might fail in frame generation, which is expected
        camera = SimulatedCamera("CAM-RES-0", fps=10, width=0, height=0)
        # Just verify initialization doesn't crash
    
    def test_rapid_start_stop_cycles(self):
        """Test rapid start/stop cycling."""
        camera = SimulatedCamera("CAM-CYCLE", fps=10)
        
        for _ in range(50):
            camera.start()
            camera.stop()
        
        # Should not crash or leak resources
    
    def test_many_cameras_registration(self):
        """Test registering many cameras."""
        cameras_to_register = 100
        
        for i in range(cameras_to_register):
            camera = SimulatedCamera(f"CAM-MANY-{i:03d}", fps=10)
            camera_manager.register_camera(f"CAM-MANY-{i:03d}", camera, auto_start=False)
        
        cameras = camera_manager.list_cameras()
        assert len(cameras) == cameras_to_register
    
    def test_get_frame_rapid_succession(self):
        """Test getting frames in rapid succession."""
        camera = SimulatedCamera("CAM-RAPID", fps=10)
        camera.start()
        
        # Get 1000 frames as fast as possible
        for _ in range(1000):
            frame = camera.get_frame()
            assert frame is not None
        
        assert camera._frame_count == 1000
        camera.stop()
    
    def test_concurrent_camera_managers(self):
        """Test concurrent access to camera manager.

        BUG FIX: thread.ident reuse muammosi.
        Linux da Python threadlari tez tugasa, ident qayta ishlatilishi mumkin.
        Shuning uchun uuid4 ishlatamiz — har thread uchun kafolatlangan unique ID.
        """
        import uuid
        results = []
        errors = []

        def register_and_get():
            try:
                camera_id = f"CAM-CONC-{uuid.uuid4().hex[:12]}"
                camera = SimulatedCamera(camera_id, fps=10)
                camera_manager.register_camera(camera_id, camera, auto_start=False)

                cam = camera_manager.get_camera(camera_id)
                results.append(cam is not None)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=register_and_get) for _ in range(20)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0, f"Xatolar: {errors}"
        assert all(results)
    
    def test_camera_without_stop_cleanup(self):
        """Test camera cleanup when stop is not called."""
        camera = SimulatedCamera("CAM-NO-STOP", fps=10)
        camera.start()
        
        # Get some frames
        for _ in range(5):
            camera.get_frame()
        
        # Don't call stop explicitly - let it be garbage collected
        del camera
        
        # Should not cause issues (memory leak test)
    
    def test_invalid_config_combinations(self):
        """Test factory with invalid config combinations."""
        invalid_configs = [
            {},  # Empty
            {"camera_id": "TEST"},  # Missing type
            {"type": "simulated"},  # Missing camera_id
            {"camera_id": "TEST", "type": "invalid"},  # Invalid type
            {"camera_id": "TEST", "type": "rtsp"},  # RTSP without URL
            {"camera_id": "TEST", "type": "usb"},  # USB without device_index
        ]
        
        for config in invalid_configs:
            camera = CameraFactory.create_camera(config)
            # Should return None, not crash
            assert camera is None
    
    def test_manager_operations_on_nonexistent_camera(self):
        """Test manager operations on non-existent camera."""
        # All these should handle gracefully
        assert camera_manager.get_camera("NONEXISTENT") is None
        assert camera_manager.get_camera_stats("NONEXISTENT") is None
        assert camera_manager.start_camera("NONEXISTENT") is False
        assert camera_manager.stop_camera("NONEXISTENT") is False
        assert camera_manager.unregister_camera("NONEXISTENT") is False
    
    def test_stats_with_no_frames_captured(self):
        """Test statistics when no frames captured."""
        camera = SimulatedCamera("CAM-NO-FRAMES", fps=10)
        camera.start()
        
        # Don't capture any frames
        stats = camera.get_stats()
        
        assert stats["frame_count"] == 0
        assert stats["running"] is True
        
        camera.stop()
    
    def test_unicode_in_camera_config(self):
        """Test unicode characters in configuration."""
        config = {
            "camera_id": "相机-001",
            "type": "simulated",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is not None
        assert camera.camera_id == "相机-001"
    
    def test_extremely_large_frame_count(self):
        """Test camera with extremely large frame count."""
        camera = SimulatedCamera("CAM-LARGE-COUNT", fps=10)
        camera.start()
        
        # Manually set large frame count
        camera._frame_count = 2**31 - 1  # Max int32
        
        # Should still work
        frame = camera.get_frame()
        assert frame is not None
        
        camera.stop()
    
    def test_negative_error_count(self):
        """Test handling of negative error count."""
        camera = SimulatedCamera("CAM-NEG-ERR", fps=10)
        camera.start()
        
        # Manually set negative
        camera._error_count = -1
        
        # Should still get stats
        stats = camera.get_stats()
        assert "error_count" in stats
        
        camera.stop()
    
    def test_null_frame_handling(self):
        """Test system handles null frames gracefully."""
        camera = SimulatedCamera("CAM-NULL", fps=10)
        camera.start()
        
        # Manually set null frame
        camera._last_frame = None
        
        # Should not crash
        stats = camera.get_stats()
        assert stats is not None
        
        camera.stop()
    
    @pytest.mark.slow
    def test_memory_usage_stability(self):
        """Test memory doesn't grow over time."""
        import gc
        
        camera = SimulatedCamera("CAM-MEM-STABLE", fps=10)
        camera.start()
        
        gc.collect()
        
        # Generate many frames
        for _ in range(500):
            frame = camera.get_frame()
            del frame
        
        gc.collect()
        
        # Just verify it completes without memory error
        camera.stop()
    
    def test_simultaneous_operations(self):
        """Test simultaneous operations on same camera."""
        camera = SimulatedCamera("CAM-SIMUL", fps=10)
        results = []
        
        def operation():
            camera.start()
            frame = camera.get_frame()
            results.append(frame is not None)
            stats = camera.get_stats()
            results.append(stats is not None)
            camera.stop()
        
        threads = [threading.Thread(target=operation) for _ in range(10)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should handle concurrent access
        assert len(results) > 0
    
    def test_api_rapid_requests(self, test_client):
        """Test API handles rapid requests."""
        config = {
            "camera_id": "API-RAPID",
            "type": "simulated",
            "auto_start": False,
        }
        
        # Register
        response = test_client.post("/api/v1/cameras/", json=config)
        assert response.status_code == 201
        
        # Rapid stats requests
        for _ in range(50):
            response = test_client.get("/api/v1/cameras/API-RAPID/stats")
            assert response.status_code == 200
        
        # Cleanup
        test_client.delete("/api/v1/cameras/API-RAPID")
    
    def test_api_malformed_json(self, test_client):
        """Test API handles malformed JSON gracefully."""
        # This will be caught by FastAPI validation
        response = test_client.post(
            "/api/v1/cameras/",
            data="not json",
            headers={"Content-Type": "application/json"},
        )
        
        # Should return error, not crash
        assert response.status_code in [400, 422, 500]
    
    def test_manager_cleanup_with_running_cameras(self):
        """Test manager cleanup with cameras still running."""
        for i in range(3):
            camera = SimulatedCamera(f"CAM-CLEANUP-{i}", fps=10)
            camera_manager.register_camera(f"CAM-CLEANUP-{i}", camera, auto_start=True)
        
        # All cameras running
        health = camera_manager.get_health_status()
        assert health["running_cameras"] == 3
        
        # Cleanup
        camera_manager.cleanup()
        
        # All should be stopped and removed
        assert len(camera_manager.list_cameras()) == 0