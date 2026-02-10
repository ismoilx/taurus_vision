"""
WebSocket endpoint for live weight measurements feed.

Provides real-time updates to connected dashboard clients.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import logging

from app.api.v1.websocket import get_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/live",
    tags=["live"],
)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live weight measurement updates.
    
    PROTOCOL:
    1. Client connects
    2. Server sends welcome message
    3. Server broadcasts weight updates as they occur
    4. Client can receive indefinitely
    
    MESSAGE FORMAT:
    {
        "type": "weight_update",
        "data": {
            "measurement_id": 123,
            "animal_id": 1,
            "animal_tag_id": "JNV-001",
            "estimated_weight_kg": 245.5,
            "confidence_score": 0.92,
            "camera_id": "CAM-001",
            "timestamp": "2026-02-10T10:30:00Z"
        }
    }
    
    USAGE:
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/api/v1/live/ws');
    
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === 'weight_update') {
            console.log('New weight:', msg.data);
            // Update UI
        }
    };
    ```
    """
    manager = get_ws_manager()
    
    # Accept connection
    await manager.connect(websocket)
    
    try:
        # Keep connection alive and handle messages
        while True:
            # Wait for messages from client (optional)
            # In this implementation, client only receives, doesn't send
            data = await websocket.receive_text()
            
            # Handle client messages (future feature: filters, etc.)
            logger.debug(f"Received from client: {data}")
            
            # Echo or handle specific commands
            # For now, we just keep the connection open
            
    except WebSocketDisconnect:
        # Client disconnected normally
        await manager.disconnect(websocket)
        logger.info("Client disconnected")
        
    except Exception as e:
        # Unexpected error
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await manager.disconnect(websocket)


@router.get("/stats")
async def websocket_stats():
    """
    Get WebSocket connection statistics.
    
    Useful for monitoring dashboard health.
    
    Returns:
        Dictionary with connection stats
    """
    manager = get_ws_manager()
    return manager.get_stats()