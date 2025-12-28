"""
API v1 Router - Aggregates all v1 endpoints.
"""

from fastapi import APIRouter

from app.api.v1.endpoints import resume, query, answers, feedback, agent, websocket
from app.services.intervention import router as intervention_router

router = APIRouter()


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "JobHunter API"}


# Include sub-routers
router.include_router(resume.router, prefix="/resume", tags=["Resume"])
router.include_router(query.router, prefix="/query", tags=["Query"])
router.include_router(answers.router, tags=["Answers"])
router.include_router(feedback.router, tags=["Feedback"])

# V3 Agent endpoints
router.include_router(agent.router, prefix="/agent", tags=["Agent"])

# WebSocket real-time feed
router.include_router(websocket.router, tags=["WebSocket"])

# Human-in-the-loop intervention
router.include_router(intervention_router, tags=["Intervention"])
