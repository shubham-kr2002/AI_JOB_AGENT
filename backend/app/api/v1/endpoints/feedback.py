"""
Feedback API - Learning Loop from BTD.md Section 4C.

Endpoint: POST /api/v1/feedback
Purpose: Store user corrections to improve future answer accuracy.

When a user edits an AI-generated answer, the extension captures this
and sends it here. We store the (question, corrected_answer) pair
so future similar questions can retrieve the user's preferred answer.
"""

from typing import Optional
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import LearningHistory, User

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class FeedbackRequest(BaseModel):
    """Feedback submission from the extension."""
    question: str = Field(
        ..., 
        description="The form field label/question",
        min_length=1
    )
    original_answer: Optional[str] = Field(
        default=None,
        description="The AI-generated answer (before user correction)"
    )
    corrected_answer: str = Field(
        ..., 
        description="The user's corrected answer",
        min_length=1
    )
    field_type: Optional[str] = Field(
        default="text",
        description="Type of form field (text, textarea, select, etc.)"
    )
    job_context: Optional[str] = Field(
        default=None,
        description="Context about the job/company (for better retrieval)"
    )
    user_id: Optional[int] = Field(
        default=None,
        description="User ID (optional, for multi-user support)"
    )


class FeedbackResponse(BaseModel):
    """Response after storing feedback."""
    success: bool
    message: str
    feedback_id: int
    question_hash: str


class SimilarCorrectionResponse(BaseModel):
    """Response containing similar past corrections."""
    found: bool
    question: Optional[str] = None
    corrected_answer: Optional[str] = None
    similarity_score: Optional[float] = None
    times_used: Optional[int] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Store user feedback to improve future answers.
    
    This is the Learning Loop from the design:
    - User corrects an AI answer
    - Extension captures the correction
    - We store it for future retrieval
    
    Next time a similar question appears, we query this table
    BEFORE calling the LLM, to give consistent answers.
    """
    try:
        # Generate question hash for matching
        question_hash = LearningHistory.hash_question(feedback.question)
        
        # Check if we already have a correction for this exact question
        existing = db.query(LearningHistory).filter(
            LearningHistory.question_hash == question_hash
        ).first()
        
        if existing:
            # Update existing record with new correction
            existing.corrected_answer = feedback.corrected_answer
            existing.original_answer = feedback.original_answer
            existing.job_context = feedback.job_context
            existing.updated_at = datetime.utcnow()
            db.commit()
            
            return FeedbackResponse(
                success=True,
                message="Updated existing correction",
                feedback_id=existing.id,
                question_hash=question_hash
            )
        
        # Create new learning history record
        learning_record = LearningHistory(
            user_id=feedback.user_id or 1,  # Default user for now
            question_hash=question_hash,
            question_text=feedback.question,
            field_type=feedback.field_type,
            original_answer=feedback.original_answer,
            corrected_answer=feedback.corrected_answer,
            job_context=feedback.job_context
        )
        
        db.add(learning_record)
        db.commit()
        db.refresh(learning_record)
        
        return FeedbackResponse(
            success=True,
            message="Feedback stored successfully",
            feedback_id=learning_record.id,
            question_hash=question_hash
        )
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store feedback: {str(e)}"
        )


@router.get("/feedback/search", response_model=SimilarCorrectionResponse)
async def search_corrections(
    question: str,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Search for past corrections matching a question.
    
    Used by the answer generation endpoint to check if we have
    a user-corrected answer before calling the LLM.
    """
    question_hash = LearningHistory.hash_question(question)
    
    # First try exact match
    correction = db.query(LearningHistory).filter(
        LearningHistory.question_hash == question_hash
    ).first()
    
    if correction:
        # Increment usage counter
        correction.times_used += 1
        db.commit()
        
        return SimilarCorrectionResponse(
            found=True,
            question=correction.question_text,
            corrected_answer=correction.corrected_answer,
            similarity_score=1.0,
            times_used=correction.times_used
        )
    
    # TODO: Add fuzzy matching using embeddings for similar questions
    # For now, return not found
    return SimilarCorrectionResponse(found=False)


@router.get("/feedback/stats")
async def get_feedback_stats(
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get statistics about stored corrections."""
    total = db.query(LearningHistory).count()
    
    # Get most used corrections
    top_corrections = db.query(LearningHistory).order_by(
        LearningHistory.times_used.desc()
    ).limit(5).all()
    
    return {
        "total_corrections": total,
        "top_corrections": [
            {
                "question": c.question_text[:100],
                "times_used": c.times_used
            }
            for c in top_corrections
        ]
    }
