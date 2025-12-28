"""
Project JobHunter V3 - Celery Application
Async task queue for DAG-based job orchestration.
"""

from celery import Celery
from kombu import Queue, Exchange
from .config import get_settings

settings = get_settings()

# ============================================================================
# Celery Application Instance
# ============================================================================
celery_app = Celery(
    "jobhunter",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.planner",      # DAG generation tasks
        "app.tasks.executor",     # Browser automation tasks
        "app.tasks.critic",       # Verification tasks
        "app.tasks.recovery",     # Error recovery tasks
    ]
)

# ============================================================================
# Celery Configuration
# ============================================================================
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task settings
    task_track_started=True,
    task_time_limit=300,           # 5 minutes hard limit
    task_soft_time_limit=240,      # 4 minutes soft limit
    task_acks_late=True,           # Acknowledge after completion
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=3600,           # Results expire after 1 hour
    result_extended=True,          # Include task name in result
    
    # Worker settings
    worker_prefetch_multiplier=1,  # One task at a time (for browser automation)
    worker_concurrency=2,          # 2 workers per process
    
    # Retry policy
    task_default_retry_delay=5,
    task_max_retries=3,
    
    # Task routes - prioritize by queue
    task_routes={
        "app.tasks.planner.*": {"queue": "planner"},
        "app.tasks.executor.*": {"queue": "executor"},
        "app.tasks.critic.*": {"queue": "critic"},
        "app.tasks.recovery.*": {"queue": "recovery"},
    },
    
    # Queue definitions
    task_queues=(
        Queue("default", Exchange("default"), routing_key="default"),
        Queue("planner", Exchange("planner"), routing_key="planner.#"),
        Queue("executor", Exchange("executor"), routing_key="executor.#"),
        Queue("critic", Exchange("critic"), routing_key="critic.#"),
        Queue("recovery", Exchange("recovery"), routing_key="recovery.#"),
    ),
    
    # Default queue
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
)


# ============================================================================
# Test Task (for queue verification)
# ============================================================================
@celery_app.task(name="test_task", bind=True)
def test_task(self, message: str = "Hello from Celery!") -> dict:
    """
    Simple test task to verify Celery worker connection.
    
    Args:
        message: Test message to echo back
        
    Returns:
        Dict with task info and message
    """
    return {
        "status": "success",
        "task_id": self.request.id,
        "message": message,
        "worker": self.request.hostname,
    }


# ============================================================================
# Health Check Task
# ============================================================================
@celery_app.task(name="health_check", bind=True)
def health_check(self) -> dict:
    """
    Health check task for monitoring.
    
    Returns:
        Dict with worker health status
    """
    import platform
    import psutil
    
    return {
        "status": "healthy",
        "task_id": self.request.id,
        "worker": self.request.hostname,
        "system": {
            "platform": platform.system(),
            "python_version": platform.python_version(),
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
        }
    }
