"""
API endpoint tests for camera management.

Tests all camera API endpoints:
- Registration
- Unregistration
- List cameras
- Get stats
- Start/stop
- Health check
"""

import pytest
from fastapi.testclient import TestClient

from app.services.camera.camera_manager import camera_manager


@pytest.mark.api
@pytest.mark.camera
class TestCamerasAPI:
    """Test suite for camera API endpoints."""
    
    def test_register_simulated_camera_success(self, test_client, sample_camera_config):
        """Test registering simulated camera via API."""
        response = test_client.post(
            "/api/v1/cameras/",
            json=sample_camera_config,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["camera_id"] == "TEST-CAM-001"
        assert "registered successfully" in data["message"]
        assert data["data"] is not None
        assert data["data"]["type"] == "simulated"
    
    def test_register_rtsp_camera_success(self, test_client, sample_rtsp_config):
        """Test registering RTSP camera via API."""
        response = test_client.post(
            "/api/v1/cameras/",
            json=sample_rtsp_config,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["camera_id"] == "RTSP-TEST-001"
    
    def test_register_usb_camera_success(self, test_client, sample_usb_config):
        """Test registering USB camera via API."""
        response = test_client.post(
            "/api/v1/cameras/",
            json=sample_usb_config,
        )
        
        assert response.status_code == 201
        data = response.json()
        
        assert data["success"] is True
        assert data["camera_id"] == "USB-TEST-001"
    
    def test_register_camera_invalid_config(self, test_client):
        """Test registering camera with invalid config."""
        config = {
            "camera_id": "INVALID-001",
            # Missing 'type'
        }
        
        response = test_client.post(
            "/api/v1/cameras/",
            json=config,
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_register_camera_missing_required_field_rtsp(self, test_client):
        """Test RTSP registration without URL."""
        config = {
            "camera_id": "RTSP-NO-URL",
            "type": "rtsp",
            # Missing 'url'
        }
        
        response = test_client.post(
            "/api/v1/cameras/",
            json=config,
        )
        
        assert response.status_code == 400
    
    def test_register_duplicate_camera_id(self, test_client, sample_camera_config):
        """Test registering duplicate camera ID."""
        # First registration
        response1 = test_client.post(
            "/api/v1/cameras/",
            json=sample_camera_config,
        )
        assert response1.status_code == 201
        
        # Second registration with same ID
        response2 = test_client.post(
            "/api/v1/cameras/",
            json=sample_camera_config,
        )
        assert response2.status_code == 500
    
    def test_list_cameras_empty(self, test_client):
        """Test listing cameras when none registered."""
        response = test_client.get("/api/v1/cameras/")
        
        assert response.status_code == 200
        cameras = response.json()
        
        assert isinstance(cameras, list)
        assert len(cameras) == 0
    
    def test_list_cameras_multiple(self, test_client):
        """Test listing multiple cameras."""
        # Register 3 cameras
        configs = [
            {"camera_id": f"CAM-{i:03d}", "type": "simulated", "auto_start": False}
            for i in range(3)
        ]
        
        for config in configs:
            test_client.post("/api/v1/cameras/", json=config)
        
        # List cameras
        response = test_client.get("/api/v1/cameras/")
        
        assert response.status_code == 200
        cameras = response.json()
        
        assert len(cameras) == 3
        assert all(f"CAM-{i:03d}" in cameras for i in range(3))
    
    def test_get_camera_stats_success(self, test_client, sample_camera_config):
        """Test getting stats for registered camera."""
        # Register camera
        test_client.post("/api/v1/cameras/", json=sample_camera_config)
        
        # Get stats
        response = test_client.get(f"/api/v1/cameras/{sample_camera_config['camera_id']}/stats")
        
        assert response.status_code == 200
        stats = response.json()
        
        assert stats["camera_id"] == sample_camera_config["camera_id"]
        assert "frame_count" in stats
        assert "fps" in stats
    
    def test_get_camera_stats_nonexistent(self, test_client):
        """Test getting stats for non-existent camera."""
        response = test_client.get("/api/v1/cameras/NONEXISTENT/stats")
        
        assert response.status_code == 404
    
    def test_get_all_camera_stats_empty(self, test_client):
        """Test getting all stats when no cameras."""
        response = test_client.get("/api/v1/cameras/stats/all")
        
        assert response.status_code == 200
        stats = response.json()
        
        assert isinstance(stats, dict)
        assert len(stats) == 0
    
    def test_get_all_camera_stats_multiple(self, test_client):
        """Test getting stats for all cameras."""
        # Register cameras
        camera_ids = ["CAM-ALL-001", "CAM-ALL-002"]
        for camera_id in camera_ids:
            config = {"camera_id": camera_id, "type": "simulated", "auto_start": True}
            test_client.post("/api/v1/cameras/", json=config)
        
        # Get all stats
        response = test_client.get("/api/v1/cameras/stats/all")
        
        assert response.status_code == 200
        all_stats = response.json()
        
        assert len(all_stats) == 2
        for camera_id in camera_ids:
            assert camera_id in all_stats
    
    def test_start_camera_success(self, test_client):
        """Test starting a camera."""
        # Register camera without auto-start
        config = {"camera_id": "CAM-START", "type": "simulated", "auto_start": False}
        test_client.post("/api/v1/cameras/", json=config)
        
        # Start camera
        response = test_client.post("/api/v1/cameras/CAM-START/start")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "started successfully" in data["message"]
    
    def test_start_camera_nonexistent(self, test_client):
        """Test starting non-existent camera."""
        response = test_client.post("/api/v1/cameras/NONEXISTENT/start")
        
        assert response.status_code == 500
    
    def test_stop_camera_success(self, test_client):
        """Test stopping a camera."""
        # Register camera with auto-start
        config = {"camera_id": "CAM-STOP", "type": "simulated", "auto_start": True}
        test_client.post("/api/v1/cameras/", json=config)
        
        # Stop camera
        response = test_client.post("/api/v1/cameras/CAM-STOP/stop")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "stopped successfully" in data["message"]
    
    def test_stop_camera_nonexistent(self, test_client):
        """Test stopping non-existent camera."""
        response = test_client.post("/api/v1/cameras/NONEXISTENT/stop")
        
        assert response.status_code == 500
    
    def test_start_stop_cycle(self, test_client):
        """Test start-stop-start cycle."""
        config = {"camera_id": "CAM-CYCLE", "type": "simulated", "auto_start": False}
        test_client.post("/api/v1/cameras/", json=config)
        
        # Start
        response1 = test_client.post("/api/v1/cameras/CAM-CYCLE/start")
        assert response1.status_code == 200
        
        # Stop
        response2 = test_client.post("/api/v1/cameras/CAM-CYCLE/stop")
        assert response2.status_code == 200
        
        # Start again
        response3 = test_client.post("/api/v1/cameras/CAM-CYCLE/start")
        assert response3.status_code == 200
    
    def test_unregister_camera_success(self, test_client, sample_camera_config):
        """Test unregistering a camera."""
        # Register camera
        test_client.post("/api/v1/cameras/", json=sample_camera_config)
        
        # Unregister
        response = test_client.delete(f"/api/v1/cameras/{sample_camera_config['camera_id']}")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert "unregistered successfully" in data["message"]
    
    def test_unregister_camera_nonexistent(self, test_client):
        """Test unregistering non-existent camera."""
        response = test_client.delete("/api/v1/cameras/NONEXISTENT")
        
        assert response.status_code == 404
    
    def test_unregister_removes_from_list(self, test_client, sample_camera_config):
        """Test camera is removed from list after unregister."""
        # Register
        test_client.post("/api/v1/cameras/", json=sample_camera_config)
        
        # Verify in list
        response1 = test_client.get("/api/v1/cameras/")
        assert sample_camera_config["camera_id"] in response1.json()
        
        # Unregister
        test_client.delete(f"/api/v1/cameras/{sample_camera_config['camera_id']}")
        
        # Verify removed from list
        response2 = test_client.get("/api/v1/cameras/")
        assert sample_camera_config["camera_id"] not in response2.json()
    
    def test_start_all_cameras_success(self, test_client):
        """Test starting all cameras."""
        # Register 3 cameras without auto-start
        for i in range(3):
            config = {"camera_id": f"CAM-SALL-{i}", "type": "simulated", "auto_start": False}
            test_client.post("/api/v1/cameras/", json=config)
        
        # Start all
        response = test_client.post("/api/v1/cameras/start-all")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["started"] == 3
        assert data["data"]["total"] == 3
    
    def test_start_all_cameras_empty(self, test_client):
        """Test starting all when no cameras."""
        response = test_client.post("/api/v1/cameras/start-all")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["data"]["started"] == 0
        assert data["data"]["total"] == 0
    
    def test_stop_all_cameras_success(self, test_client):
        """Test stopping all cameras."""
        # Register cameras with auto-start
        for i in range(2):
            config = {"camera_id": f"CAM-STOPALL-{i}", "type": "simulated", "auto_start": True}
            test_client.post("/api/v1/cameras/", json=config)
        
        # Stop all
        response = test_client.post("/api/v1/cameras/stop-all")
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["success"] is True
        assert data["data"]["stopped"] == 2
    
    def test_camera_health_check_no_cameras(self, test_client):
        """Test health check with no cameras."""
        response = test_client.get("/api/v1/cameras/health")
        
        assert response.status_code == 200
        health = response.json()
        
        assert health["total_cameras"] == 0
        assert health["healthy_cameras"] == 0
        assert health["health_percentage"] == 0
        assert "timestamp" in health
    
    def test_camera_health_check_all_healthy(self, test_client):
        """Test health check with all cameras healthy."""
        # Register 2 cameras with auto-start
        for i in range(2):
            config = {"camera_id": f"CAM-HEALTH-{i}", "type": "simulated", "auto_start": True}
            test_client.post("/api/v1/cameras/", json=config)
        
        response = test_client.get("/api/v1/cameras/health")
        
        assert response.status_code == 200
        health = response.json()
        
        assert health["total_cameras"] == 2
        assert health["healthy_cameras"] == 2
        assert health["health_percentage"] == 100.0
    
    def test_camera_health_check_mixed_states(self, test_client):
        """Test health check with mixed camera states."""
        # Running camera
        config1 = {"camera_id": "CAM-H1", "type": "simulated", "auto_start": True}
        test_client.post("/api/v1/cameras/", json=config1)
        
        # Stopped camera
        config2 = {"camera_id": "CAM-H2", "type": "simulated", "auto_start": False}
        test_client.post("/api/v1/cameras/", json=config2)
        
        response = test_client.get("/api/v1/cameras/health")
        
        assert response.status_code == 200
        health = response.json()
        
        assert health["total_cameras"] == 2
        assert health["healthy_cameras"] == 1
        assert health["health_percentage"] == 50.0
    
    def test_complete_workflow(self, test_client):
        """Test complete camera management workflow."""
        camera_id = "CAM-WORKFLOW"
        config = {"camera_id": camera_id, "type": "simulated", "auto_start": False}
        
        # 1. Register
        response = test_client.post("/api/v1/cameras/", json=config)
        assert response.status_code == 201
        
        # 2. Verify in list
        response = test_client.get("/api/v1/cameras/")
        assert camera_id in response.json()
        
        # 3. Start
        response = test_client.post(f"/api/v1/cameras/{camera_id}/start")
        assert response.status_code == 200
        
        # 4. Get stats
        response = test_client.get(f"/api/v1/cameras/{camera_id}/stats")
        assert response.status_code == 200
        assert response.json()["running"] is True
        
        # 5. Stop
        response = test_client.post(f"/api/v1/cameras/{camera_id}/stop")
        assert response.status_code == 200
        
        # 6. Verify stopped
        response = test_client.get(f"/api/v1/cameras/{camera_id}/stats")
        assert response.json()["running"] is False
        
        # 7. Unregister
        response = test_client.delete(f"/api/v1/cameras/{camera_id}")
        assert response.status_code == 200
        
        # 8. Verify removed
        response = test_client.get("/api/v1/cameras/")
        assert camera_id not in response.json()


# ============================================================================
# SPRINT 9-10: Qo'shimcha testlar
# ============================================================================

class TestSystemMetricsEndpoint:
    """GET /pipeline/system-metrics — Sprint 9-10 yangi endpoint."""

    async def test_system_metrics_structure(
        self, client: AsyncClient, admin_token: str
    ):
        """system-metrics to'g'ri kalit larni qaytaradi."""
        r = await client.get(
            "/api/v1/pipeline/system-metrics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()

        required = [
            "cpu_percent", "ram_percent", "ram_available_mb",
            "active_pipelines", "max_pipelines",
            "current_skip_frames", "can_start_new",
        ]
        for key in required:
            assert key in data, f"Missing key in system-metrics: {key}"

    async def test_system_metrics_values_in_range(
        self, client: AsyncClient, viewer_token: str
    ):
        """VIEWER ham system-metrics ko'ra oladi, qiymatlar mantiqiy."""
        r = await client.get(
            "/api/v1/pipeline/system-metrics",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert r.status_code == 200
        data = r.json()

        assert 0 <= data["cpu_percent"] <= 100
        assert 0 <= data["ram_percent"] <= 100
        assert data["ram_available_mb"] >= 0
        assert data["active_pipelines"] >= 0
        assert data["max_pipelines"] >= 1
        assert data["current_skip_frames"] in (2, 4, 8)
        assert isinstance(data["can_start_new"], bool)


class TestPipelineStatusEndpoint:
    """GET /pipeline/status — barcha pipelinelar holati."""

    async def test_all_status_format(
        self, client: AsyncClient, admin_token: str
    ):
        """Pipeline status to'g'ri format."""
        r = await client.get(
            "/api/v1/pipeline/status",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert r.status_code == 200
        data = r.json()

        assert "total_running" in data
        assert "running_cameras" in data
        assert isinstance(data["total_running"], int)
        assert isinstance(data["running_cameras"], list)

    async def test_unauthenticated_denied(self, client: AsyncClient):
        """Token yo'q bo'lganda 401."""
        r = await client.get("/api/v1/pipeline/status")
        assert r.status_code in (401, 403)
