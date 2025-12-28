"""
Project JobHunter V3 - WebSocket Real-Time Feed
Streams task execution status to frontend in real-time.

Features:
- Real-time task step updates
- Live terminal output streaming  
- Intervention requests/responses
- Browser screenshot streams

Reference: BTD.md FR-02 - Real-Time Status Updates
"""

import asyncio
import json
from typing import Dict, Any, Optional, Set
from datetime import datetime
from enum import Enum
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.orm import Session
import redis.asyncio as aioredis

from app.core.config import get_settings
from app.db.database import get_db

settings = get_settings()
router = APIRouter()


class MessageType(str, Enum):
    """Types of WebSocket messages."""
    # Task lifecycle
    TASK_STARTED = "task_started"
    TASK_PROGRESS = "task_progress"
    TASK_STEP_STARTED = "task_step_started"
    TASK_STEP_COMPLETED = "task_step_completed"
    TASK_STEP_FAILED = "task_step_failed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_PAUSED = "task_paused"
    TASK_RESUMED = "task_resumed"
    TASK_CANCELLED = "task_cancelled"
    
    # Terminal output
    TERMINAL_OUTPUT = "terminal_output"
    TERMINAL_COMMAND = "terminal_command"
    
    # Intervention
    INTERVENTION_REQUIRED = "intervention_required"
    INTERVENTION_RESPONSE = "intervention_response"
    
    # Browser state
    SCREENSHOT = "screenshot"
    PAGE_NAVIGATED = "page_navigated"
    ELEMENT_HIGHLIGHTED = "element_highlighted"
    
    # System
    PING = "ping"
    PONG = "pong"
    ERROR = "error"
    CONNECTED = "connected"
    SUBSCRIBED = "subscribed"


class ConnectionManager:
    """
    Manages WebSocket connections and message broadcasting.
    
    Features:
    - Multiple clients per task
    - Redis pub/sub for distributed events
    - Automatic cleanup on disconnect
    """
    
    def __init__(self):
        # Map: task_id -> Set[WebSocket]
        self.active_connections: Dict[str, Set[WebSocket]] = {}
        # Map: WebSocket -> connection metadata
        self.connection_metadata: Dict[WebSocket, Dict[str, Any]] = {}
        # Redis connection
        self._redis: Optional[aioredis.Redis] = None
        # Background task for Redis subscription
        self._subscription_task: Optional[asyncio.Task] = None
    
    async def get_redis(self) -> aioredis.Redis:
        """Get or create Redis connection."""
        if self._redis is None:
            self._redis = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._redis
    
    async def start_subscription(self):
        """Start Redis subscription for cross-process messaging."""
        if self._subscription_task is not None:
            return
        
        self._subscription_task = asyncio.create_task(self._subscribe_loop())
    
    async def _subscribe_loop(self):
        """Listen for messages from Redis pub/sub."""
        try:
            redis = await self.get_redis()
            pubsub = redis.pubsub()
            await pubsub.psubscribe("task:*")
            
            async for message in pubsub.listen():
                if message["type"] == "pmessage":
                    channel = message["channel"]
                    data = message["data"]
                    
                    # Extract task_id from channel (e.g., "task:abc123")
                    task_id = channel.split(":", 1)[1] if ":" in channel else None
                    
                    if task_id:
                        try:
                            payload = json.loads(data)
                            await self._broadcast_to_task(task_id, payload)
                        except json.JSONDecodeError:
                            pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Redis subscription error: {e}")
    
    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        
        if client_id is None:
            client_id = str(uuid.uuid4())
        
        self.connection_metadata[websocket] = {
            "client_id": client_id,
            "connected_at": datetime.utcnow().isoformat(),
            "subscriptions": set(),
        }
        
        # Send connection confirmation
        await self._send(websocket, {
            "type": MessageType.CONNECTED,
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        # Ensure subscription loop is running
        await self.start_subscription()
    
    async def subscribe_to_task(self, websocket: WebSocket, task_id: str):
        """Subscribe a connection to a task's updates."""
        if task_id not in self.active_connections:
            self.active_connections[task_id] = set()
        
        self.active_connections[task_id].add(websocket)
        
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["subscriptions"].add(task_id)
        
        await self._send(websocket, {
            "type": MessageType.SUBSCRIBED,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
        })
    
    async def unsubscribe_from_task(self, websocket: WebSocket, task_id: str):
        """Unsubscribe a connection from a task."""
        if task_id in self.active_connections:
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        
        if websocket in self.connection_metadata:
            self.connection_metadata[websocket]["subscriptions"].discard(task_id)
    
    def disconnect(self, websocket: WebSocket):
        """Handle WebSocket disconnection."""
        # Remove from all subscriptions
        for task_id in list(self.active_connections.keys()):
            self.active_connections[task_id].discard(websocket)
            if not self.active_connections[task_id]:
                del self.active_connections[task_id]
        
        # Remove metadata
        if websocket in self.connection_metadata:
            del self.connection_metadata[websocket]
    
    async def broadcast_to_task(self, task_id: str, message: Dict[str, Any]):
        """
        Broadcast a message to all subscribers of a task.
        Also publishes to Redis for cross-process delivery.
        """
        # Add metadata
        message["task_id"] = task_id
        message["timestamp"] = datetime.utcnow().isoformat()
        
        # Publish to Redis for other processes
        try:
            redis = await self.get_redis()
            await redis.publish(f"task:{task_id}", json.dumps(message))
        except Exception as e:
            print(f"Redis publish error: {e}")
        
        # Also broadcast directly to local connections
        await self._broadcast_to_task(task_id, message)
    
    async def _broadcast_to_task(self, task_id: str, message: Dict[str, Any]):
        """Broadcast to local WebSocket connections."""
        if task_id not in self.active_connections:
            return
        
        disconnected = set()
        for websocket in self.active_connections[task_id]:
            try:
                await self._send(websocket, message)
            except Exception:
                disconnected.add(websocket)
        
        # Clean up disconnected
        for ws in disconnected:
            self.disconnect(ws)
    
    async def _send(self, websocket: WebSocket, message: Dict[str, Any]):
        """Send a message to a specific WebSocket."""
        await websocket.send_json(message)


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    client_id: Optional[str] = Query(None),
):
    """
    Main WebSocket endpoint for real-time updates.
    
    Connect to: ws://localhost:8000/api/v1/ws?client_id=<optional>
    
    After connecting, send subscription messages:
    {"action": "subscribe", "task_id": "abc123"}
    {"action": "unsubscribe", "task_id": "abc123"}
    """
    await manager.connect(websocket, client_id)
    
    try:
        while True:
            # Receive and handle client messages
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "subscribe":
                task_id = data.get("task_id")
                if task_id:
                    await manager.subscribe_to_task(websocket, task_id)
            
            elif action == "unsubscribe":
                task_id = data.get("task_id")
                if task_id:
                    await manager.unsubscribe_from_task(websocket, task_id)
            
            elif action == "ping":
                await websocket.send_json({
                    "type": MessageType.PONG,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            elif action == "intervention_response":
                # Handle human intervention response
                task_id = data.get("task_id")
                response = data.get("response")
                if task_id and response:
                    await manager.broadcast_to_task(task_id, {
                        "type": MessageType.INTERVENTION_RESPONSE,
                        "response": response,
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/task/{task_id}")
async def task_websocket(
    websocket: WebSocket,
    task_id: str,
    client_id: Optional[str] = Query(None),
):
    """
    Dedicated WebSocket endpoint for a specific task.
    
    Connect to: ws://localhost:8000/api/v1/ws/task/{task_id}
    
    Automatically subscribes to the task's updates.
    """
    await manager.connect(websocket, client_id)
    await manager.subscribe_to_task(websocket, task_id)
    
    try:
        while True:
            data = await websocket.receive_json()
            
            action = data.get("action")
            
            if action == "ping":
                await websocket.send_json({
                    "type": MessageType.PONG,
                    "timestamp": datetime.utcnow().isoformat(),
                })
            
            elif action == "intervention_response":
                response = data.get("response")
                if response:
                    await manager.broadcast_to_task(task_id, {
                        "type": MessageType.INTERVENTION_RESPONSE,
                        "response": response,
                    })
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# =============================================================================
# Helper functions for broadcasting from Celery tasks
# =============================================================================

async def emit_task_started(task_id: str, task_data: Dict[str, Any]):
    """Emit task started event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_STARTED,
        "data": task_data,
    })


async def emit_task_progress(task_id: str, progress: float, message: str = ""):
    """Emit task progress update."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_PROGRESS,
        "progress": progress,
        "message": message,
    })


async def emit_step_started(task_id: str, step_id: str, step_data: Dict[str, Any]):
    """Emit step started event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_STEP_STARTED,
        "step_id": step_id,
        "data": step_data,
    })


async def emit_step_completed(task_id: str, step_id: str, result: Dict[str, Any] = None):
    """Emit step completed event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_STEP_COMPLETED,
        "step_id": step_id,
        "result": result or {},
    })


async def emit_step_failed(task_id: str, step_id: str, error: str):
    """Emit step failed event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_STEP_FAILED,
        "step_id": step_id,
        "error": error,
    })


async def emit_task_completed(task_id: str, result: Dict[str, Any] = None):
    """Emit task completed event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_COMPLETED,
        "result": result or {},
    })


async def emit_task_failed(task_id: str, error: str):
    """Emit task failed event."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TASK_FAILED,
        "error": error,
    })


async def emit_terminal_output(task_id: str, output: str, stream: str = "stdout"):
    """Emit terminal output."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.TERMINAL_OUTPUT,
        "output": output,
        "stream": stream,
    })


async def emit_screenshot(task_id: str, screenshot_base64: str, url: str = ""):
    """Emit screenshot update."""
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.SCREENSHOT,
        "screenshot": screenshot_base64,
        "url": url,
    })


async def emit_intervention_required(
    task_id: str,
    intervention_type: str,
    message: str,
    options: Dict[str, Any] = None
):
    """
    Emit intervention required event.
    
    Args:
        task_id: Task requiring intervention
        intervention_type: Type of intervention (2fa, captcha, login, etc.)
        message: Human-readable message
        options: Available actions for the user
    """
    await manager.broadcast_to_task(task_id, {
        "type": MessageType.INTERVENTION_REQUIRED,
        "intervention_type": intervention_type,
        "message": message,
        "options": options or {},
    })


# =============================================================================
# Synchronous wrappers for Celery tasks
# =============================================================================

def sync_emit(task_id: str, message_type: MessageType, data: Dict[str, Any]):
    """
    Synchronous emit for use in Celery tasks.
    Publishes directly to Redis.
    """
    import redis
    
    r = redis.from_url(settings.REDIS_URL)
    
    message = {
        "type": message_type.value,
        "task_id": task_id,
        "timestamp": datetime.utcnow().isoformat(),
        **data,
    }
    
    r.publish(f"task:{task_id}", json.dumps(message))
