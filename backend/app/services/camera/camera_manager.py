"""
Camera Manager - Multiple camera orchestration.

Manages multiple cameras (RTSP, USB, Simulated):
- Camera registration and lifecycle
- Health monitoring
- Load balancing
- Failover handling
"""

import logging
import threading
from typing import Dict, List, Optional, Any
from datetime import datetime

from app.services.camera.base import CameraInterface


logger = logging.getLogger(__name__)


class CameraManager:
    """
    Manages multiple cameras across the system.
    
    Singleton pattern - only one instance per application.
    Thread-safe operations for concurrent camera access.
    
    Features:
    - Camera registration and lifecycle management
    - Health monitoring and automatic recovery
    - Thread-safe concurrent access
    - Statistics aggregation
    """
    
    _instance: Optional["CameraManager"] = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern implementation."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize camera manager."""
        if not hasattr(self, '_initialized'):
            self._cameras: Dict[str, CameraInterface] = {}
            self._camera_lock = threading.RLock()
            self._initialized = True
            logger.info("Camera manager initialized")
    
    def register_camera(
        self,
        camera_id: str,
        camera: CameraInterface,
        auto_start: bool = True,
    ) -> bool:
        """
        Register a camera with the manager.
        
        Args:
            camera_id: Unique camera identifier
            camera: Camera instance
            auto_start: Automatically start camera after registration
            
        Returns:
            True if registration successful, False otherwise
            
        Raises:
            ValueError: If camera_id already exists
        """
        with self._camera_lock:
            if camera_id in self._cameras:
                raise ValueError(f"Camera {camera_id} already registered")
            
            self._cameras[camera_id] = camera
            logger.info(f"Camera registered: {camera_id}")
            
            if auto_start:
                try:
                    camera.start()
                    logger.info(f"Camera started: {camera_id}")
                except Exception as e:
                    logger.error(f"Failed to start camera {camera_id}: {e}")
                    return False
            
            return True
    
    def unregister_camera(self, camera_id: str) -> bool:
        """
        Unregister and stop a camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if unregistration successful, False otherwise
        """
        with self._camera_lock:
            if camera_id not in self._cameras:
                logger.warning(f"Camera {camera_id} not found")
                return False
            
            camera = self._cameras[camera_id]
            
            try:
                camera.stop()
                del self._cameras[camera_id]
                logger.info(f"Camera unregistered: {camera_id}")
                return True
            except Exception as e:
                logger.error(f"Failed to unregister camera {camera_id}: {e}")
                return False
    
    def get_camera(self, camera_id: str) -> Optional[CameraInterface]:
        """
        Get camera instance by ID.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Camera instance or None if not found
        """
        with self._camera_lock:
            return self._cameras.get(camera_id)
    
    def list_cameras(self) -> List[str]:
        """
        Get list of all registered camera IDs.
        
        Returns:
            List of camera identifiers
        """
        with self._camera_lock:
            return list(self._cameras.keys())
    
    def get_camera_stats(self, camera_id: str) -> Optional[Dict[str, Any]]:
        """
        Get statistics for a specific camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            Camera statistics dictionary or None if not found
        """
        camera = self.get_camera(camera_id)
        if camera is None:
            return None
        
        try:
            return camera.get_stats()
        except Exception as e:
            logger.error(f"Failed to get stats for {camera_id}: {e}")
            return None
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Get statistics for all cameras.
        
        Returns:
            Dictionary mapping camera_id to statistics
        """
        stats = {}
        
        with self._camera_lock:
            for camera_id, camera in self._cameras.items():
                try:
                    stats[camera_id] = camera.get_stats()
                except Exception as e:
                    logger.error(f"Failed to get stats for {camera_id}: {e}")
                    stats[camera_id] = {"error": str(e)}
        
        return stats
    
    def start_camera(self, camera_id: str) -> bool:
        """
        Start a specific camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if started successfully, False otherwise
        """
        camera = self.get_camera(camera_id)
        if camera is None:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        try:
            camera.start()
            logger.info(f"Camera started: {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start camera {camera_id}: {e}")
            return False
    
    def stop_camera(self, camera_id: str) -> bool:
        """
        Stop a specific camera.
        
        Args:
            camera_id: Camera identifier
            
        Returns:
            True if stopped successfully, False otherwise
        """
        camera = self.get_camera(camera_id)
        if camera is None:
            logger.error(f"Camera {camera_id} not found")
            return False
        
        try:
            camera.stop()
            logger.info(f"Camera stopped: {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to stop camera {camera_id}: {e}")
            return False
    
    def start_all(self) -> int:
        """
        Start all registered cameras.
        
        Returns:
            Number of cameras started successfully
        """
        success_count = 0
        
        with self._camera_lock:
            for camera_id in list(self._cameras.keys()):
                if self.start_camera(camera_id):
                    success_count += 1
        
        logger.info(f"Started {success_count}/{len(self._cameras)} cameras")
        return success_count
    
    def stop_all(self) -> int:
        """
        Stop all registered cameras.
        
        Returns:
            Number of cameras stopped successfully
        """
        success_count = 0
        
        with self._camera_lock:
            for camera_id in list(self._cameras.keys()):
                if self.stop_camera(camera_id):
                    success_count += 1
        
        logger.info(f"Stopped {success_count}/{len(self._cameras)} cameras")
        return success_count
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status of camera system.
        
        Returns:
            Health status summary
        """
        with self._camera_lock:
            total = len(self._cameras)
            healthy = 0
            running = 0
            
            for camera in self._cameras.values():
                try:
                    if camera.is_opened():
                        healthy += 1
                    stats = camera.get_stats()
                    if stats.get('running', False):
                        running += 1
                except Exception:
                    pass
            
            return {
                "total_cameras": total,
                "healthy_cameras": healthy,
                "running_cameras": running,
                "health_percentage": (healthy / total * 100) if total > 0 else 0,
                "timestamp": datetime.utcnow().isoformat(),
            }
    
    def cleanup(self) -> None:
        """
        Cleanup all cameras and resources.
        
        Should be called on application shutdown.
        """
        logger.info("Cleaning up camera manager...")
        
        with self._camera_lock:
            for camera_id in list(self._cameras.keys()):
                try:
                    self.unregister_camera(camera_id)
                except Exception as e:
                    logger.error(f"Error cleaning up camera {camera_id}: {e}")
        
        logger.info("Camera manager cleanup complete")


# Global camera manager instance
camera_manager = CameraManager()
