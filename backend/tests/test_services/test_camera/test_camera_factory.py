"""
Unit tests for CameraFactory.

Tests factory pattern implementation:
- Camera creation from config
- Config validation
- Error handling
- Support for all camera types
"""

import pytest
from unittest.mock import patch, MagicMock

from app.services.camera.camera_factory import CameraFactory
from app.services.camera.simulated_camera import SimulatedCamera
from app.services.camera.rtsp_camera import RTSPCamera
from app.services.camera.usb_camera import USBCamera


@pytest.mark.unit
@pytest.mark.camera
class TestCameraFactory:
    """Test suite for CameraFactory."""
    
    def test_create_simulated_camera_success(self, sample_camera_config):
        """Test creating simulated camera."""
        camera = CameraFactory.create_camera(sample_camera_config)
        
        assert camera is not None
        assert isinstance(camera, SimulatedCamera)
        assert camera.camera_id == "TEST-CAM-001"
        assert camera.fps == 10
        assert camera.width == 640
        assert camera.height == 480
    
    def test_create_rtsp_camera_success(self, sample_rtsp_config):
        """Test creating RTSP camera."""
        camera = CameraFactory.create_camera(sample_rtsp_config)
        
        assert camera is not None
        assert isinstance(camera, RTSPCamera)
        assert camera.camera_id == "RTSP-TEST-001"
        assert camera.rtsp_url == "rtsp://test:test@localhost:554/stream"
        assert camera.fps == 25
        assert camera.width == 1920
        assert camera.height == 1080
    
    def test_create_usb_camera_success(self, sample_usb_config):
        """Test creating USB camera."""
        camera = CameraFactory.create_camera(sample_usb_config)
        
        assert camera is not None
        assert isinstance(camera, USBCamera)
        assert camera.camera_id == "USB-TEST-001"
        assert camera.device_index == 0
        assert camera.fps == 30
    
    def test_create_camera_missing_camera_id(self):
        """Test creation fails without camera_id."""
        config = {
            "type": "simulated",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_create_camera_missing_type(self):
        """Test creation fails without type."""
        config = {
            "camera_id": "TEST-001",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_create_camera_invalid_type(self):
        """Test creation fails with invalid type."""
        config = {
            "camera_id": "TEST-001",
            "type": "invalid_type",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_create_rtsp_camera_missing_url(self):
        """Test RTSP creation fails without URL."""
        config = {
            "camera_id": "RTSP-001",
            "type": "rtsp",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_create_usb_camera_missing_device_index(self):
        """Test USB creation fails without device_index."""
        config = {
            "camera_id": "USB-001",
            "type": "usb",
            "fps": 10,
        }
        
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_create_camera_default_fps(self):
        """Test default FPS is used."""
        config = {
            "camera_id": "TEST-001",
            "type": "simulated",
        }
        
        camera = CameraFactory.create_camera(config)
        
        assert camera is not None
        assert camera.fps == 10  # Default value
    
    def test_create_camera_default_resolution(self):
        """Test default resolution is used."""
        config = {
            "camera_id": "TEST-001",
            "type": "simulated",
        }
        
        camera = CameraFactory.create_camera(config)
        
        assert camera is not None
        assert camera.width == 1920  # Default
        assert camera.height == 1080  # Default
    
    def test_create_camera_custom_parameters(self):
        """Test custom parameters are applied."""
        config = {
            "camera_id": "TEST-CUSTOM",
            "type": "simulated",
            "fps": 60,
            "width": 3840,
            "height": 2160,
        }
        
        camera = CameraFactory.create_camera(config)
        
        assert camera.fps == 60
        assert camera.width == 3840
        assert camera.height == 2160
    
    def test_create_rtsp_camera_with_optional_params(self):
        """Test RTSP camera with optional parameters."""
        config = {
            "camera_id": "RTSP-OPT",
            "type": "rtsp",
            "url": "rtsp://localhost:554/stream",
            "fps": 30,
            "reconnect_interval": 10,
            "connection_timeout": 15,
            "buffer_size": 2,
        }
        
        camera = CameraFactory.create_camera(config)
        
        assert camera is not None
        assert camera.reconnect_interval == 10
        assert camera.connection_timeout == 15
        assert camera.buffer_size == 2
    
    def test_create_usb_camera_with_auto_reconnect(self):
        """Test USB camera with auto_reconnect option."""
        config = {
            "camera_id": "USB-AUTO",
            "type": "usb",
            "device_index": 0,
            "auto_reconnect": False,
        }
        
        camera = CameraFactory.create_camera(config)
        
        assert camera is not None
        assert camera.auto_reconnect is False
    
    def test_validate_config_valid_simulated(self, sample_camera_config):
        """Test validating valid simulated config."""
        is_valid, error = CameraFactory.validate_config(sample_camera_config)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_config_valid_rtsp(self, sample_rtsp_config):
        """Test validating valid RTSP config."""
        is_valid, error = CameraFactory.validate_config(sample_rtsp_config)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_config_valid_usb(self, sample_usb_config):
        """Test validating valid USB config."""
        is_valid, error = CameraFactory.validate_config(sample_usb_config)
        
        assert is_valid is True
        assert error is None
    
    def test_validate_config_missing_camera_id(self):
        """Test validation fails without camera_id."""
        config = {"type": "simulated"}
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is False
        assert "camera_id" in error
    
    def test_validate_config_missing_type(self):
        """Test validation fails without type."""
        config = {"camera_id": "TEST-001"}
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is False
        assert "type" in error
    
    def test_validate_config_invalid_type(self):
        """Test validation fails with invalid type."""
        config = {
            "camera_id": "TEST-001",
            "type": "unknown",
        }
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is False
        assert "Unknown camera type" in error
    
    def test_validate_config_rtsp_missing_url(self):
        """Test RTSP validation fails without URL."""
        config = {
            "camera_id": "RTSP-001",
            "type": "rtsp",
        }
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is False
        assert "url" in error
    
    def test_validate_config_usb_missing_device_index(self):
        """Test USB validation fails without device_index."""
        config = {
            "camera_id": "USB-001",
            "type": "usb",
        }
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is False
        assert "device_index" in error
    
    def test_validate_config_simulated_no_extra_requirements(self):
        """Test simulated camera has no extra requirements."""
        config = {
            "camera_id": "SIM-001",
            "type": "simulated",
        }
        
        is_valid, error = CameraFactory.validate_config(config)
        
        assert is_valid is True
        assert error is None
    
    def test_create_multiple_cameras_different_types(self):
        """Test creating multiple cameras of different types."""
        configs = [
            {"camera_id": "SIM-001", "type": "simulated", "fps": 10},
            {"camera_id": "RTSP-001", "type": "rtsp", "url": "rtsp://localhost:554/stream"},
            {"camera_id": "USB-001", "type": "usb", "device_index": 0},
        ]
        
        cameras = [CameraFactory.create_camera(config) for config in configs]
        
        assert all(cam is not None for cam in cameras)
        assert isinstance(cameras[0], SimulatedCamera)
        assert isinstance(cameras[1], RTSPCamera)
        assert isinstance(cameras[2], USBCamera)
    
    def test_create_camera_exception_handling(self):
        """Test factory handles exceptions gracefully."""
        # Invalid config that might raise exception
        config = {
            "camera_id": "TEST-ERR",
            "type": "simulated",
            "fps": "invalid",  # Should be int
        }
        
        # Should not raise, should return None
        camera = CameraFactory.create_camera(config)
        assert camera is None
    
    def test_factory_isolation(self):
        """Test factory creates independent instances."""
        config1 = {"camera_id": "CAM-001", "type": "simulated", "fps": 10}
        config2 = {"camera_id": "CAM-002", "type": "simulated", "fps": 20}
        
        camera1 = CameraFactory.create_camera(config1)
        camera2 = CameraFactory.create_camera(config2)
        
        assert camera1 is not camera2
        assert camera1.camera_id != camera2.camera_id
        assert camera1.fps != camera2.fps
