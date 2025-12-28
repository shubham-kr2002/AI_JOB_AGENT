"""
Project JobHunter V3 - Human-in-the-Loop Intervention Service
Handles 2FA, CAPTCHA, and other situations requiring human input.

Features:
1. Task pause/resume workflow
2. Intervention request creation
3. Human response handling
4. Timeout and escalation

Reference: BTD.md FR-03 - Human-in-the-Loop Integration
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import uuid
import json

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
import redis

from app.core.config import get_settings
from app.core.celery_app import celery_app
from app.db.database import get_db

settings = get_settings()
router = APIRouter()


class InterventionType(str, Enum):
    """Types of human intervention."""
    TWO_FACTOR_AUTH = "two_factor_auth"
    CAPTCHA = "captcha"
    LOGIN_REQUIRED = "login_required"
    MANUAL_REVIEW = "manual_review"
    FIELD_CONFIRMATION = "field_confirmation"
    ERROR_DECISION = "error_decision"
    CUSTOM_QUESTION = "custom_question"
    UPLOAD_FILE = "upload_file"


class InterventionStatus(str, Enum):
    """Status of an intervention request."""
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class InterventionPriority(str, Enum):
    """Priority levels for intervention requests."""
    CRITICAL = "critical"  # Blocks task completely
    HIGH = "high"         # Should respond soon
    NORMAL = "normal"     # Can wait
    LOW = "low"           # Optional


@dataclass
class InterventionRequest:
    """A request for human intervention."""
    id: str
    task_id: str
    intervention_type: InterventionType
    title: str
    message: str
    priority: InterventionPriority
    status: InterventionStatus
    screenshot_base64: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    options: List[str] = field(default_factory=list)
    input_fields: List[Dict[str, Any]] = field(default_factory=list)
    timeout_seconds: int = 300  # 5 minutes default
    created_at: datetime = field(default_factory=datetime.utcnow)
    acknowledged_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    response: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "task_id": self.task_id,
            "intervention_type": self.intervention_type.value,
            "title": self.title,
            "message": self.message,
            "priority": self.priority.value,
            "status": self.status.value,
            "screenshot": self.screenshot_base64 is not None,
            "context": self.context,
            "options": self.options,
            "input_fields": self.input_fields,
            "timeout_seconds": self.timeout_seconds,
            "created_at": self.created_at.isoformat(),
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "response": self.response,
        }
    
    def is_expired(self) -> bool:
        """Check if intervention request has timed out."""
        if self.status in [InterventionStatus.COMPLETED, InterventionStatus.CANCELLED]:
            return False
        
        expiry_time = self.created_at + timedelta(seconds=self.timeout_seconds)
        return datetime.utcnow() > expiry_time


class InterventionManager:
    """
    Manages human intervention workflow.
    
    Uses Redis for:
    - Storing intervention requests
    - Pub/sub for real-time notifications
    - Blocking wait for responses
    """
    
    REDIS_PREFIX = "intervention:"
    REDIS_QUEUE = "intervention:queue"
    
    def __init__(self):
        self._redis = None
    
    def get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if self._redis is None:
            self._redis = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True
            )
        return self._redis
    
    def create_intervention(
        self,
        task_id: str,
        intervention_type: InterventionType,
        title: str,
        message: str,
        priority: InterventionPriority = InterventionPriority.NORMAL,
        screenshot_base64: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        options: Optional[List[str]] = None,
        input_fields: Optional[List[Dict[str, Any]]] = None,
        timeout_seconds: int = 300
    ) -> InterventionRequest:
        """
        Create a new intervention request.
        
        Args:
            task_id: The task requiring intervention
            intervention_type: Type of intervention needed
            title: Short title for the request
            message: Detailed message for the user
            priority: Priority level
            screenshot_base64: Optional screenshot
            context: Additional context data
            options: Available action options (for choice-based interventions)
            input_fields: Fields for user input
            timeout_seconds: How long to wait for response
            
        Returns:
            Created InterventionRequest
        """
        intervention_id = str(uuid.uuid4())
        
        # Default input fields based on type
        if input_fields is None:
            if intervention_type == InterventionType.TWO_FACTOR_AUTH:
                input_fields = [
                    {"name": "code", "type": "text", "label": "Verification Code", "required": True},
                ]
            elif intervention_type == InterventionType.CAPTCHA:
                input_fields = [
                    {"name": "solved", "type": "boolean", "label": "I solved the CAPTCHA", "required": True},
                ]
            elif intervention_type == InterventionType.LOGIN_REQUIRED:
                input_fields = [
                    {"name": "completed", "type": "boolean", "label": "I completed login", "required": True},
                ]
        
        request = InterventionRequest(
            id=intervention_id,
            task_id=task_id,
            intervention_type=intervention_type,
            title=title,
            message=message,
            priority=priority,
            status=InterventionStatus.PENDING,
            screenshot_base64=screenshot_base64,
            context=context or {},
            options=options or [],
            input_fields=input_fields or [],
            timeout_seconds=timeout_seconds,
        )
        
        # Store in Redis
        r = self.get_redis()
        key = f"{self.REDIS_PREFIX}{intervention_id}"
        r.setex(key, timeout_seconds + 60, json.dumps(request.to_dict()))
        
        # Add to queue for dashboard polling
        r.lpush(self.REDIS_QUEUE, intervention_id)
        r.ltrim(self.REDIS_QUEUE, 0, 99)  # Keep last 100
        
        # Publish notification
        r.publish(f"task:{task_id}", json.dumps({
            "type": "intervention_required",
            "intervention": request.to_dict(),
        }))
        
        return request
    
    def get_intervention(self, intervention_id: str) -> Optional[InterventionRequest]:
        """Get an intervention request by ID."""
        r = self.get_redis()
        key = f"{self.REDIS_PREFIX}{intervention_id}"
        data = r.get(key)
        
        if not data:
            return None
        
        return self._parse_intervention(json.loads(data))
    
    def get_pending_interventions(self, task_id: Optional[str] = None) -> List[InterventionRequest]:
        """Get all pending intervention requests."""
        r = self.get_redis()
        
        # Get intervention IDs from queue
        intervention_ids = r.lrange(self.REDIS_QUEUE, 0, -1)
        
        interventions = []
        for iid in intervention_ids:
            intervention = self.get_intervention(iid)
            if intervention and intervention.status == InterventionStatus.PENDING:
                if task_id is None or intervention.task_id == task_id:
                    interventions.append(intervention)
        
        return interventions
    
    def acknowledge_intervention(self, intervention_id: str) -> Optional[InterventionRequest]:
        """Mark an intervention as acknowledged (user has seen it)."""
        intervention = self.get_intervention(intervention_id)
        if not intervention:
            return None
        
        intervention.status = InterventionStatus.ACKNOWLEDGED
        intervention.acknowledged_at = datetime.utcnow()
        
        self._save_intervention(intervention)
        return intervention
    
    def complete_intervention(
        self,
        intervention_id: str,
        response: Dict[str, Any]
    ) -> Optional[InterventionRequest]:
        """
        Complete an intervention with user response.
        
        Args:
            intervention_id: The intervention to complete
            response: User's response data
            
        Returns:
            Updated InterventionRequest
        """
        intervention = self.get_intervention(intervention_id)
        if not intervention:
            return None
        
        intervention.status = InterventionStatus.COMPLETED
        intervention.completed_at = datetime.utcnow()
        intervention.response = response
        
        self._save_intervention(intervention)
        
        # Notify task that intervention is complete
        r = self.get_redis()
        r.publish(f"intervention:{intervention_id}", json.dumps({
            "status": "completed",
            "response": response,
        }))
        
        # Also publish to task channel
        r.publish(f"task:{intervention.task_id}", json.dumps({
            "type": "intervention_response",
            "intervention_id": intervention_id,
            "response": response,
        }))
        
        return intervention
    
    def cancel_intervention(self, intervention_id: str) -> Optional[InterventionRequest]:
        """Cancel an intervention request."""
        intervention = self.get_intervention(intervention_id)
        if not intervention:
            return None
        
        intervention.status = InterventionStatus.CANCELLED
        intervention.completed_at = datetime.utcnow()
        
        self._save_intervention(intervention)
        
        # Notify task
        r = self.get_redis()
        r.publish(f"intervention:{intervention_id}", json.dumps({
            "status": "cancelled",
        }))
        
        return intervention
    
    def wait_for_response(
        self,
        intervention_id: str,
        timeout_seconds: int = 300
    ) -> Optional[Dict[str, Any]]:
        """
        Block until intervention is completed or times out.
        
        Args:
            intervention_id: The intervention to wait for
            timeout_seconds: How long to wait
            
        Returns:
            Response data if completed, None if timeout
        """
        r = self.get_redis()
        pubsub = r.pubsub()
        pubsub.subscribe(f"intervention:{intervention_id}")
        
        deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        
        for message in pubsub.listen():
            if datetime.utcnow() > deadline:
                break
            
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    if data.get("status") == "completed":
                        return data.get("response")
                    elif data.get("status") == "cancelled":
                        return None
                except:
                    pass
        
        # Timeout
        intervention = self.get_intervention(intervention_id)
        if intervention:
            intervention.status = InterventionStatus.TIMEOUT
            self._save_intervention(intervention)
        
        return None
    
    def _save_intervention(self, intervention: InterventionRequest):
        """Save intervention to Redis."""
        r = self.get_redis()
        key = f"{self.REDIS_PREFIX}{intervention.id}"
        ttl = r.ttl(key)
        if ttl < 0:
            ttl = 3600  # 1 hour fallback
        r.setex(key, ttl, json.dumps(intervention.to_dict()))
    
    def _parse_intervention(self, data: Dict[str, Any]) -> InterventionRequest:
        """Parse intervention from dict."""
        return InterventionRequest(
            id=data["id"],
            task_id=data["task_id"],
            intervention_type=InterventionType(data["intervention_type"]),
            title=data["title"],
            message=data["message"],
            priority=InterventionPriority(data["priority"]),
            status=InterventionStatus(data["status"]),
            screenshot_base64=data.get("screenshot_base64"),
            context=data.get("context", {}),
            options=data.get("options", []),
            input_fields=data.get("input_fields", []),
            timeout_seconds=data.get("timeout_seconds", 300),
            created_at=datetime.fromisoformat(data["created_at"]),
            acknowledged_at=datetime.fromisoformat(data["acknowledged_at"]) if data.get("acknowledged_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            response=data.get("response"),
        )


# Global manager instance
intervention_manager = InterventionManager()


# =============================================================================
# API Endpoints
# =============================================================================

class InterventionCreateRequest(BaseModel):
    """Request to create an intervention."""
    task_id: str
    intervention_type: str
    title: str
    message: str
    priority: str = "normal"
    screenshot_base64: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    options: Optional[List[str]] = None
    input_fields: Optional[List[Dict[str, Any]]] = None
    timeout_seconds: int = 300


class InterventionResponse(BaseModel):
    """Response from user for an intervention."""
    response: Dict[str, Any]


@router.post("/interventions", response_model=Dict[str, Any])
def create_intervention(
    request: InterventionCreateRequest,
    db: Session = Depends(get_db)
):
    """Create a new intervention request."""
    try:
        intervention_type = InterventionType(request.intervention_type)
        priority = InterventionPriority(request.priority)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    intervention = intervention_manager.create_intervention(
        task_id=request.task_id,
        intervention_type=intervention_type,
        title=request.title,
        message=request.message,
        priority=priority,
        screenshot_base64=request.screenshot_base64,
        context=request.context,
        options=request.options,
        input_fields=request.input_fields,
        timeout_seconds=request.timeout_seconds,
    )
    
    return intervention.to_dict()


@router.get("/interventions", response_model=List[Dict[str, Any]])
def list_pending_interventions(
    task_id: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """List all pending intervention requests."""
    interventions = intervention_manager.get_pending_interventions(task_id)
    return [i.to_dict() for i in interventions]


@router.get("/interventions/{intervention_id}", response_model=Dict[str, Any])
def get_intervention(
    intervention_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific intervention request."""
    intervention = intervention_manager.get_intervention(intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return intervention.to_dict()


@router.post("/interventions/{intervention_id}/acknowledge", response_model=Dict[str, Any])
def acknowledge_intervention(
    intervention_id: str,
    db: Session = Depends(get_db)
):
    """Acknowledge an intervention (user has seen it)."""
    intervention = intervention_manager.acknowledge_intervention(intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return intervention.to_dict()


@router.post("/interventions/{intervention_id}/respond", response_model=Dict[str, Any])
def respond_to_intervention(
    intervention_id: str,
    request: InterventionResponse,
    db: Session = Depends(get_db)
):
    """Submit a response to an intervention."""
    intervention = intervention_manager.complete_intervention(
        intervention_id,
        request.response
    )
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return intervention.to_dict()


@router.post("/interventions/{intervention_id}/cancel", response_model=Dict[str, Any])
def cancel_intervention(
    intervention_id: str,
    db: Session = Depends(get_db)
):
    """Cancel an intervention request."""
    intervention = intervention_manager.cancel_intervention(intervention_id)
    if not intervention:
        raise HTTPException(status_code=404, detail="Intervention not found")
    return intervention.to_dict()


# =============================================================================
# Celery Tasks
# =============================================================================

@celery_app.task(name="intervention.request_2fa", bind=True)
def request_2fa(
    self,
    task_id: str,
    screenshot_base64: Optional[str] = None,
    message: str = "Please enter the 2FA verification code"
) -> dict:
    """
    Request 2FA code from user.
    
    Args:
        task_id: The task needing 2FA
        screenshot_base64: Optional screenshot showing the 2FA prompt
        message: Message to display
        
    Returns:
        Intervention result
    """
    intervention = intervention_manager.create_intervention(
        task_id=task_id,
        intervention_type=InterventionType.TWO_FACTOR_AUTH,
        title="Two-Factor Authentication Required",
        message=message,
        priority=InterventionPriority.CRITICAL,
        screenshot_base64=screenshot_base64,
        input_fields=[
            {"name": "code", "type": "text", "label": "Verification Code", "required": True}
        ],
        timeout_seconds=300,
    )
    
    # Wait for response
    response = intervention_manager.wait_for_response(intervention.id, timeout_seconds=300)
    
    if response:
        return {
            "status": "completed",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "code": response.get("code"),
        }
    else:
        return {
            "status": "timeout",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "error": "2FA request timed out",
        }


@celery_app.task(name="intervention.request_captcha", bind=True)
def request_captcha_solve(
    self,
    task_id: str,
    screenshot_base64: Optional[str] = None,
    message: str = "Please solve the CAPTCHA"
) -> dict:
    """
    Request user to solve CAPTCHA.
    
    Args:
        task_id: The task needing CAPTCHA solved
        screenshot_base64: Screenshot showing the CAPTCHA
        message: Message to display
        
    Returns:
        Intervention result
    """
    intervention = intervention_manager.create_intervention(
        task_id=task_id,
        intervention_type=InterventionType.CAPTCHA,
        title="CAPTCHA Verification Required",
        message=message,
        priority=InterventionPriority.CRITICAL,
        screenshot_base64=screenshot_base64,
        input_fields=[
            {"name": "solved", "type": "boolean", "label": "I solved the CAPTCHA", "required": True}
        ],
        timeout_seconds=300,
    )
    
    # Wait for response
    response = intervention_manager.wait_for_response(intervention.id, timeout_seconds=300)
    
    if response and response.get("solved"):
        return {
            "status": "completed",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "solved": True,
        }
    else:
        return {
            "status": "timeout" if not response else "not_solved",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "solved": False,
        }


@celery_app.task(name="intervention.request_login", bind=True)
def request_login(
    self,
    task_id: str,
    site_name: str,
    screenshot_base64: Optional[str] = None
) -> dict:
    """
    Request user to login to a site.
    
    Args:
        task_id: The task needing login
        site_name: Name of the site requiring login
        screenshot_base64: Screenshot of login page
        
    Returns:
        Intervention result
    """
    intervention = intervention_manager.create_intervention(
        task_id=task_id,
        intervention_type=InterventionType.LOGIN_REQUIRED,
        title=f"Login Required: {site_name}",
        message=f"Please log in to {site_name} and click 'Done' when complete.",
        priority=InterventionPriority.CRITICAL,
        screenshot_base64=screenshot_base64,
        input_fields=[
            {"name": "completed", "type": "boolean", "label": "Login completed", "required": True}
        ],
        timeout_seconds=600,  # 10 minutes for login
    )
    
    # Wait for response
    response = intervention_manager.wait_for_response(intervention.id, timeout_seconds=600)
    
    if response and response.get("completed"):
        return {
            "status": "completed",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "logged_in": True,
        }
    else:
        return {
            "status": "timeout" if not response else "not_completed",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "logged_in": False,
        }


@celery_app.task(name="intervention.request_review", bind=True)
def request_manual_review(
    self,
    task_id: str,
    title: str,
    message: str,
    options: List[str],
    context: Optional[Dict[str, Any]] = None,
    screenshot_base64: Optional[str] = None
) -> dict:
    """
    Request manual review/decision from user.
    
    Args:
        task_id: The task needing review
        title: Title for the review request
        message: Detailed message
        options: Available choices
        context: Additional context
        screenshot_base64: Optional screenshot
        
    Returns:
        Intervention result with user's choice
    """
    intervention = intervention_manager.create_intervention(
        task_id=task_id,
        intervention_type=InterventionType.MANUAL_REVIEW,
        title=title,
        message=message,
        priority=InterventionPriority.HIGH,
        screenshot_base64=screenshot_base64,
        context=context or {},
        options=options,
        input_fields=[
            {"name": "choice", "type": "select", "label": "Select action", "options": options, "required": True},
            {"name": "notes", "type": "textarea", "label": "Additional notes", "required": False},
        ],
        timeout_seconds=600,
    )
    
    # Wait for response
    response = intervention_manager.wait_for_response(intervention.id, timeout_seconds=600)
    
    if response:
        return {
            "status": "completed",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "choice": response.get("choice"),
            "notes": response.get("notes"),
        }
    else:
        return {
            "status": "timeout",
            "task_id": self.request.id,
            "intervention_id": intervention.id,
            "error": "Review request timed out",
        }
