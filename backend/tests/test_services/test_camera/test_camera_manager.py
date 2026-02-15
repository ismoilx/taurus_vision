"""
Unit tests for CameraManager.

Tests camera manager functionality:
- Camera registration
- Camera lifecycle management
- Multiple camera handling
- Health monitoring
- Thread safety
"""

import pytest
import threading

from app.services.camera.camera_manager import CameraManager, camera_manager
from app.services.camera.simulated_camera import SimulatedCamera
from tests.conftest import assert_camera_stats_valid


@pytest.mark.unit
@pytest.mark.camera
class TestCameraManager:
    """Test suite for CameraManager."""
    
    def test_singleton_pattern(self):
        """Test CameraManager is singleton."""
        manager1 = CameraManager()
        manager2 = CameraManager()
        
        assert manager1 is manager2
        assert manager1 is camera_manager
    
    def test_register_camera_success(self):
        """Test successful camera registration."""
        camera = SimulatedCamera("CAM-REG-001", fps=10)
        
        success = camera_manager.register_camera(
            camera_id="CAM-REG-001",
            camera=camera,
            auto_start=False,
        )
        
        assert success is True
        assert "CAM-REG-001" in camera_manager.list_cameras()
    
    def test_register_camera_auto_start(self):
        """Test camera auto-starts on registration."""
        camera = SimulatedCamera("CAM-REG-002", fps=10)
        
        camera_manager.register_camera(
            camera_id="CAM-REG-002",
            camera=camera,
            auto_start=True,
        )
        
        assert camera.is_opened()
    
    def test_register_duplicate_camera_id(self):
        """Test registering camera with duplicate ID fails."""
        camera1 = SimulatedCamera("CAM-DUP-001", fps=10)
        camera2 = SimulatedCamera("CAM-DUP-001", fps=10)
        
        # First registration should succeed
        camera_manager.register_camera("CAM-DUP-001", camera1, auto_start=False)
        
        # Second should raise ValueError
        with pytest.raises(ValueError, match="already registered"):
            camera_manager.register_camera("CAM-DUP-001", camera2, auto_start=False)
    
    def test_unregister_camera_success(self):
        """Test successful camera unregistration."""
        camera = SimulatedCamera("CAM-UNREG-001", fps=10)
        camera_manager.register_camera("CAM-UNREG-001", camera, auto_start=True)
        
        # Camera should be running
        assert camera.is_opened()
        
        # Unregister
        success = camera_manager.unregister_camera("CAM-UNREG-001")
        
        assert success is True
        assert "CAM-UNREG-001" not in camera_manager.list_cameras()
        assert not camera.is_opened()  # Should be stopped
    
    def test_unregister_nonexistent_camera(self):
        """Test unregistering non-existent camera."""
        success = camera_manager.unregister_camera("NONEXISTENT")
        assert success is False
    
    def test_get_camera_success(self):
        """Test retrieving registered camera."""
        camera = SimulatedCamera("CAM-GET-001", fps=10)
        camera_manager.register_camera("CAM-GET-001", camera, auto_start=False)
        
        retrieved = camera_manager.get_camera("CAM-GET-001")
        
        assert retrieved is camera
    
    def test_get_camera_nonexistent(self):
        """Test retrieving non-existent camera returns None."""
        camera = camera_manager.get_camera("NONEXISTENT")
        assert camera is None
    
    def test_list_cameras_empty(self):
        """Test listing cameras when none registered."""
        # Cleanup ensures no cameras
        cameras = camera_manager.list_cameras()
        assert isinstance(cameras, list)
        assert len(cameras) == 0
    
    def test_list_cameras_multiple(self):
        """Test listing multiple cameras."""
        cameras_to_register = ["CAM-LIST-001", "CAM-LIST-002", "CAM-LIST-003"]
        
        for camera_id in cameras_to_register:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=False)
        
        cameras = camera_manager.list_cameras()
        
        assert len(cameras) == 3
        for camera_id in cameras_to_register:
            assert camera_id in cameras
    
    def test_get_camera_stats_success(self):
        """Test getting stats for registered camera."""
        camera = SimulatedCamera("CAM-STATS-001", fps=10)
        camera_manager.register_camera("CAM-STATS-001", camera, auto_start=True)
        
        stats = camera_manager.get_camera_stats("CAM-STATS-001")
        
        assert stats is not None
        assert_camera_stats_valid(stats)
        assert stats["camera_id"] == "CAM-STATS-001"
    
    def test_get_camera_stats_nonexistent(self):
        """Test getting stats for non-existent camera."""
        stats = camera_manager.get_camera_stats("NONEXISTENT")
        assert stats is None
    
    def test_get_all_stats_empty(self):
        """Test getting all stats when no cameras."""
        stats = camera_manager.get_all_stats()
        
        assert isinstance(stats, dict)
        assert len(stats) == 0
    
    def test_get_all_stats_multiple(self):
        """Test getting stats for multiple cameras."""
        camera_ids = ["CAM-ALL-001", "CAM-ALL-002", "CAM-ALL-003"]
        
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=True)
        
        all_stats = camera_manager.get_all_stats()
        
        assert len(all_stats) == 3
        for camera_id in camera_ids:
            assert camera_id in all_stats
            assert_camera_stats_valid(all_stats[camera_id])
    
    def test_start_camera_success(self):
        """Test starting a registered camera."""
        camera = SimulatedCamera("CAM-START-001", fps=10)
        camera_manager.register_camera("CAM-START-001", camera, auto_start=False)
        
        assert not camera.is_opened()
        
        success = camera_manager.start_camera("CAM-START-001")
        
        assert success is True
        assert camera.is_opened()
    
    def test_start_camera_nonexistent(self):
        """Test starting non-existent camera fails."""
        success = camera_manager.start_camera("NONEXISTENT")
        assert success is False
    
    def test_stop_camera_success(self):
        """Test stopping a running camera."""
        camera = SimulatedCamera("CAM-STOP-001", fps=10)
        camera_manager.register_camera("CAM-STOP-001", camera, auto_start=True)
        
        assert camera.is_opened()
        
        success = camera_manager.stop_camera("CAM-STOP-001")
        
        assert success is True
        assert not camera.is_opened()
    
    def test_stop_camera_nonexistent(self):
        """Test stopping non-existent camera fails."""
        success = camera_manager.stop_camera("NONEXISTENT")
        assert success is False
    
    def test_start_all_cameras(self):
        """Test starting all registered cameras."""
        camera_ids = ["CAM-SALL-001", "CAM-SALL-002", "CAM-SALL-003"]
        
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=False)
        
        # All should be stopped
        for camera_id in camera_ids:
            camera = camera_manager.get_camera(camera_id)
            assert not camera.is_opened()
        
        # Start all
        count = camera_manager.start_all()
        
        assert count == 3
        
        # All should be running
        for camera_id in camera_ids:
            camera = camera_manager.get_camera(camera_id)
            assert camera.is_opened()
    
    def test_stop_all_cameras(self):
        """Test stopping all cameras."""
        camera_ids = ["CAM-STALL-001", "CAM-STALL-002"]
        
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=True)
        
        # Stop all
        count = camera_manager.stop_all()
        
        assert count == 2
        
        # All should be stopped
        for camera_id in camera_ids:
            camera = camera_manager.get_camera(camera_id)
            assert not camera.is_opened()
    
    def test_get_health_status_empty(self):
        """Test health status with no cameras."""
        health = camera_manager.get_health_status()
        
        assert health["total_cameras"] == 0
        assert health["healthy_cameras"] == 0
        assert health["running_cameras"] == 0
        assert health["health_percentage"] == 0
        assert "timestamp" in health
    
    def test_get_health_status_all_healthy(self):
        """Test health status with all cameras healthy."""
        camera_ids = ["CAM-HEALTH-001", "CAM-HEALTH-002"]
        
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=True)
        
        health = camera_manager.get_health_status()
        
        assert health["total_cameras"] == 2
        assert health["healthy_cameras"] == 2
        assert health["running_cameras"] == 2
        assert health["health_percentage"] == 100.0
    
    def test_get_health_status_mixed(self):
        """Test health status with mixed camera states."""
        # Running camera
        camera1 = SimulatedCamera("CAM-MIX-001", fps=10)
        camera_manager.register_camera("CAM-MIX-001", camera1, auto_start=True)
        
        # Stopped camera
        camera2 = SimulatedCamera("CAM-MIX-002", fps=10)
        camera_manager.register_camera("CAM-MIX-002", camera2, auto_start=False)
        
        health = camera_manager.get_health_status()
        
        assert health["total_cameras"] == 2
        assert health["healthy_cameras"] == 1
        assert health["running_cameras"] == 1
        assert health["health_percentage"] == 50.0
    
    def test_cleanup(self):
        """Test cleanup removes all cameras."""
        camera_ids = ["CAM-CLEAN-001", "CAM-CLEAN-002"]
        
        for camera_id in camera_ids:
            camera = SimulatedCamera(camera_id, fps=10)
            camera_manager.register_camera(camera_id, camera, auto_start=True)
        
        # Cleanup
        camera_manager.cleanup()
        
        # All cameras should be removed
        assert len(camera_manager.list_cameras()) == 0
    
    def test_thread_safety_registration(self):
        """Test thread-safe camera registration."""
        results = []
        errors = []
        
        def register_camera(camera_id):
            try:
                camera = SimulatedCamera(camera_id, fps=10)
                success = camera_manager.register_camera(camera_id, camera, auto_start=False)
                results.append((camera_id, success))
            except Exception as e:
                errors.append((camera_id, str(e)))
        
        # Create threads
        camera_ids = [f"CAM-THREAD-{i:03d}" for i in range(10)]
        threads = [threading.Thread(target=register_camera, args=(cid,)) for cid in camera_ids]
        
        # Start all threads
        for t in threads:
            t.start()
        
        # Wait for completion
        for t in threads:
            t.join()
        
        # All should succeed
        assert len(results) == 10
        assert len(errors) == 0
        assert len(camera_manager.list_cameras()) == 10
    
    def test_concurrent_stats_access(self):
        """Test thread-safe stats access."""
        camera = SimulatedCamera("CAM-CONCURRENT", fps=10)
        camera_manager.register_camera("CAM-CONCURRENT", camera, auto_start=True)
        
        results = []
        
        def get_stats():
            for _ in range(10):
                stats = camera_manager.get_camera_stats("CAM-CONCURRENT")
                results.append(stats is not None)
        
        # Create multiple threads
        threads = [threading.Thread(target=get_stats) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # All stats access should succeed
        assert all(results)
        assert len(results) == 50
