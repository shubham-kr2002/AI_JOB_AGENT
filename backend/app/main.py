"""
Project JobHunter V3 - FastAPI Backend
Autonomous Agent Platform for job application automation.

Architecture:
- FastAPI: Async HTTP API layer
- Celery: Distributed task queue (DAG orchestration)
- PostgreSQL: Long-term memory & World Model
- Redis: Task queue broker & short-term memory
- Qdrant: Vector memory for semantic recall

Responsibilities:
- Resume ingestion and RAG pipeline
- Multi-agent orchestration (Planner, Executor, Critic, Recovery)
- DAG-based task planning with NetworkX
- Browser automation via Playwright
- Hallucination guardrails
- Learning loop from user corrections
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.celery_app import celery_app, test_task
from app.api.v1.router import router as api_v1_router
from app.db.database import init_db

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - runs on startup and shutdown."""
    # Startup
    print(f"[Startup] {settings.APP_NAME} v{settings.APP_VERSION}")
    print(f"[Startup] Environment: {settings.APP_ENV}")
    
    # Initialize SQLite database (legacy V1 compatibility)
    print("[Startup] Initializing SQLite database...")
    init_db()
    print("[Startup] SQLite database initialized")
    
    # Log V3 service configuration
    print(f"[Startup] PostgreSQL: {settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}")
    print(f"[Startup] Redis: {settings.REDIS_HOST}:{settings.REDIS_PORT}")
    print(f"[Startup] Qdrant: {settings.QDRANT_HOST}:{settings.QDRANT_PORT}")
    print(f"[Startup] Celery Broker: {settings.CELERY_BROKER_URL}")
    
    yield
    
    # Shutdown
    print("[Shutdown] Application shutting down...")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Autonomous AI Agent Platform for auto-filling job applications",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS middleware - Allow extension to communicate with backend
cors_origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)


# ============================================================================
# Root & Health Endpoints
# ============================================================================

@app.get("/")
async def root():
    """Root endpoint - API info."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    """Health check endpoint for orchestration."""
    return {
        "status": "healthy",
        "version": settings.APP_VERSION,
        "services": {
            "api": "up",
            "postgres": f"{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}",
            "redis": f"{settings.REDIS_HOST}:{settings.REDIS_PORT}",
            "qdrant": f"{settings.QDRANT_HOST}:{settings.QDRANT_PORT}",
        }
    }


# ============================================================================
# Celery Test Endpoints
# ============================================================================

@app.post("/test-queue")
async def test_queue(message: str = "Hello from JobHunter!"):
    """
    Test endpoint to verify Celery worker connection.
    
    Pushes a dummy task to the Celery queue and returns the task ID.
    Use GET /task-status/{task_id} to check the result.
    
    Args:
        message: Test message to echo back
        
    Returns:
        Dict with task_id for status polling
    """
    # Push task to Celery queue
    result = test_task.delay(message)
    
    return {
        "status": "queued",
        "task_id": result.id,
        "message": f"Task queued with message: {message}",
        "check_status": f"/task-status/{result.id}",
    }


@app.get("/task-status/{task_id}")
async def get_task_status(task_id: str):
    """
    Get the status of a Celery task.
    
    Args:
        task_id: The Celery task ID
        
    Returns:
        Dict with task status and result (if completed)
    """
    result = celery_app.AsyncResult(task_id)
    
    response = {
        "task_id": task_id,
        "status": result.status,
    }
    
    if result.ready():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    
    return response


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
