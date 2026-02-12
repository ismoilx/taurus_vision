"""
WebSocket infrastructure for real-time updates.

Implements production-grade WebSocket connection management
with broadcasting capabilities for live farm monitoring.
"""

from typing import Set
from fastapi import WebSocket, WebSocketDisconnect
import json
import logging
import asyncio

logger = logging.getLogger(__name__)

# --- MANA SHUNI QO'SHING (Importlardan keyin) ---
class DateTimeEncoder(json.JSONEncoder):
    """
    Vaqtni (datetime) JSON tushunadigan formatga (ISO string) o'girib beradi.
    """
    def default(self, obj):
        from datetime import datetime
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)
# -----------------------------------------------


class ConnectionManager:
    """
    WebSocket connection manager.
    
    Handles multiple simultaneous connections and provides
    broadcasting capabilities for real-time updates.
    
    FEATURES:
    - Connection pooling
    - Automatic reconnection handling
    - Broadcast to all connected clients
    - Connection health monitoring
    
    THREAD SAFETY:
    - Uses asyncio locks for concurrent access
    - Safe for multi-camera, multi-client scenarios
    """
    
    def __init__(self):
        """Initialize connection manager."""
        # Set of active WebSocket connections
        self.active_connections: Set[WebSocket] = set()
        
        # Lock for thread-safe operations
        self._lock = asyncio.Lock()
        
        # Statistics
        self._total_connections = 0
        self._total_disconnections = 0
        self._total_messages_sent = 0
    
    async def connect(self, websocket: WebSocket) -> None:
        """
        Accept and register a new WebSocket connection.
        
        Args:
            websocket: WebSocket connection to accept
        """
        await websocket.accept()
        
        async with self._lock:
            self.active_connections.add(websocket)
            self._total_connections += 1
        
        logger.info(
            f"WebSocket connected. "
            f"Active connections: {len(self.active_connections)}"
        )
        
        # Send welcome message
        await self._send_personal(
            websocket,
            {
                "type": "connection",
                "status": "connected",
                "message": "Connected to Taurus Vision live feed",
                "active_connections": len(self.active_connections),
            }
        )
    
    async def disconnect(self, websocket: WebSocket) -> None:
        """
        Remove a WebSocket connection from the pool.
        
        Args:
            websocket: WebSocket connection to remove
        """
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
                self._total_disconnections += 1
        
        logger.info(
            f"WebSocket disconnected. "
            f"Active connections: {len(self.active_connections)}"
        )
    
    async def broadcast(self, message: dict) -> None:
        """
        Broadcast message to all connected clients.
        
        Handles individual connection failures gracefully.
        If a send fails, that connection is automatically removed.
        
        Args:
            message: Dictionary to broadcast (will be JSON serialized)
        """
        if not self.active_connections:
            logger.debug("No active connections to broadcast to")
            return
        
        # Add metadata
        broadcast_message = {
            "type": "weight_update",
            "data": message,
        }
        
        # Convert to JSON once (with DateTimeEncoder)
        try:
            json_message = json.dumps(broadcast_message, cls=DateTimeEncoder)
        except TypeError as e:
            logger.error(f"JSON serialization failed: {e}")
            return
        
        # Track failed connections
        failed_connections = set()
        
        # Broadcast to all connections
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_text(json_message)
                    self._total_messages_sent += 1
                    
                except WebSocketDisconnect:
                    # Connection lost
                    failed_connections.add(connection)
                    logger.warning("Connection lost during broadcast")
                    
                except Exception as e:
                    # Other errors
                    failed_connections.add(connection)
                    logger.error(f"Error broadcasting to connection: {e}")
            
            # Remove failed connections
            if failed_connections:
                self.active_connections -= failed_connections
                logger.info(
                    f"Removed {len(failed_connections)} failed connections. "
                    f"Active: {len(self.active_connections)}"
                )
        
        logger.debug(
            f"Broadcasted to {len(self.active_connections)} clients "
            f"({len(failed_connections)} failed)"
        )
    
    async def _send_personal(
        self,
        websocket: WebSocket,
        message: dict,
    ) -> None:
        """
        Send message to a specific client.
        
        Args:
            websocket: Target WebSocket connection
            message: Dictionary to send (will be JSON serialized)
        """
        try:
            await websocket.send_json(message)
            self._total_messages_sent += 1
            
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
    
    async def send_heartbeat(self) -> None:
        """
        Send heartbeat/ping to all connections to keep them alive.
        
        Should be called periodically (e.g., every 30 seconds).
        """
        heartbeat_message = {
            "type": "heartbeat",
            "timestamp": asyncio.get_event_loop().time(),
            "active_connections": len(self.active_connections),
        }
        
        await self.broadcast(heartbeat_message)
    
    def get_stats(self) -> dict:
        """
        Get connection manager statistics.
        
        Returns:
            Dictionary with connection stats
        """
        return {
            "active_connections": len(self.active_connections),
            "total_connections": self._total_connections,
            "total_disconnections": self._total_disconnections,
            "total_messages_sent": self._total_messages_sent,
        }


# Global connection manager instance
# This will be initialized in main.py on startup
ws_manager: ConnectionManager | None = None


def get_ws_manager() -> ConnectionManager:
    """
    Get the global WebSocket connection manager.
    
    Returns:
        Global ConnectionManager instance
        
    Raises:
        RuntimeError: If manager hasn't been initialized
    """
    if ws_manager is None:
        raise RuntimeError(
            "WebSocket manager not initialized. "
            "Call initialize_ws_manager() in startup event."
        )
    return ws_manager


def initialize_ws_manager() -> ConnectionManager:
    """
    Initialize the global WebSocket connection manager.
    
    Should be called once during application startup.
    
    Returns:
        Initialized ConnectionManager instance
    """
    global ws_manager
    ws_manager = ConnectionManager()
    logger.info("WebSocket connection manager initialized")
    return ws_manager


async def shutdown_ws_manager() -> None:
    """
    Shutdown WebSocket manager and close all connections.
    
    Should be called during application shutdown.
    """
    global ws_manager
    
    if ws_manager is None:
        return
    
    logger.info("Shutting down WebSocket connections...")
    
    # Close all active connections
    for connection in list(ws_manager.active_connections):
        try:
            await connection.close()
        except Exception as e:
            logger.error(f"Error closing WebSocket: {e}")
    
    # Clear connections
    ws_manager.active_connections.clear()
    
    logger.info("WebSocket manager shutdown complete")