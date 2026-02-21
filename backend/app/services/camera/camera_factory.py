"""
Camera Factory - Creates camera instances from configuration.

Factory pattern for creating different camera types:
- RTSP cameras from URL
- USB cameras from device index
- Simulated cameras for testing
"""

import logging
from typing import Dict, Any, Optional

from app.services.camera.base import CameraInterface
from app.services.camera.rtsp_camera import RTSPCamera
from app.services.camera.usb_camera import USBCamera
from app.services.camera.simulated_camera import SimulatedCamera


logger = logging.getLogger(__name__)


class CameraFactory:
    """
    Factory for creating camera instances.
    
    Supports multiple camera types with unified configuration interface.
    Validates configuration and handles errors gracefully.
    """
    
    @staticmethod
    def create_camera(config: Dict[str, Any]) -> Optional[CameraInterface]:
        """
        Create camera instance from configuration.
        
        Args:
            config: Camera configuration dictionary
                Required fields:
                    - camera_id (str): Unique identifier
                    - type (str): Camera type ('rtsp', 'usb', 'simulated')
                Type-specific fields:
                    RTSP:
                        - url (str): RTSP stream URL
                    USB:
                        - device_index (int): USB device index
                    Common optional:
                        - fps (int): Target FPS (default: 10)
                        - width (int): Frame width (default: 1920)
                        - height (int): Frame height (default: 1080)
        
        Returns:
            Camera instance or None if creation failed
            
        Raises:
            ValueError: If configuration is invalid
        """
        try:
            # Validate required fields
            camera_id = config.get('camera_id')
            camera_type = config.get('type')
            
            if not camera_id:
                raise ValueError("camera_id is required")
            if not camera_type:
                raise ValueError("type is required")
            
            # Common parameters — type-safe extraction
            fps_raw = config.get('fps', 10)
            try:
                fps = int(fps_raw)
                if fps <= 0:
                    raise ValueError(f"fps must be positive, got: {fps}")
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Invalid fps value: {fps_raw!r}") from exc

            width = config.get('width', 1920)
            height = config.get('height', 1080)
            
            # Create camera based on type
            if camera_type == 'rtsp':
                return CameraFactory._create_rtsp_camera(
                    camera_id, config, fps, width, height
                )
            elif camera_type == 'usb':
                return CameraFactory._create_usb_camera(
                    camera_id, config, fps, width, height
                )
            elif camera_type == 'simulated':
                return CameraFactory._create_simulated_camera(
                    camera_id, config, fps, width, height
                )
            else:
                raise ValueError(f"Unknown camera type: {camera_type}")
        
        except Exception as e:
            logger.error(f"Failed to create camera: {e}")
            return None
    
    @staticmethod
    def _create_rtsp_camera(
        camera_id: str,
        config: Dict[str, Any],
        fps: int,
        width: int,
        height: int,
    ) -> RTSPCamera:
        """Create RTSP camera instance."""
        url = config.get('url')
        if not url:
            raise ValueError("RTSP camera requires 'url' parameter")
        
        return RTSPCamera(
            camera_id=camera_id,
            rtsp_url=url,
            fps=fps,
            width=width,
            height=height,
            reconnect_interval=config.get('reconnect_interval', 5),
            connection_timeout=config.get('connection_timeout', 10),
            buffer_size=config.get('buffer_size', 1),
        )
    
    @staticmethod
    def _create_usb_camera(
        camera_id: str,
        config: Dict[str, Any],
        fps: int,
        width: int,
        height: int,
    ) -> USBCamera:
        """Create USB camera instance."""
        device_index = config.get('device_index')
        if device_index is None:
            raise ValueError("USB camera requires 'device_index' parameter")
        
        return USBCamera(
            camera_id=camera_id,
            device_index=device_index,
            fps=fps,
            width=width,
            height=height,
            auto_reconnect=config.get('auto_reconnect', True),
        )
    
    @staticmethod
    def _create_simulated_camera(
        camera_id: str,
        config: Dict[str, Any],
        fps: int,
        width: int,
        height: int,
    ) -> SimulatedCamera:
        """Create simulated camera instance."""
        return SimulatedCamera(
            camera_id=camera_id,
            fps=fps,
            width=width,
            height=height,
        )
    
    @staticmethod
    def validate_config(config: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate camera configuration.
        
        Args:
            config: Camera configuration dictionary
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check required fields
        if 'camera_id' not in config:
            return False, "camera_id is required"
        
        if 'type' not in config:
            return False, "type is required"
        
        camera_type = config['type']
        
        # Type-specific validation
        if camera_type == 'rtsp':
            if 'url' not in config:
                return False, "RTSP camera requires 'url' parameter"
            
        elif camera_type == 'usb':
            if 'device_index' not in config:
                return False, "USB camera requires 'device_index' parameter"
            
        elif camera_type == 'simulated':
            pass  # No additional requirements
            
        else:
            return False, f"Unknown camera type: {camera_type}"
        
        return True, None