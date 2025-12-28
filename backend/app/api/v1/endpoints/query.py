"""
Query API
Handles semantic search over the vector database.

Endpoint: POST /api/v1/query
"""

from typing import Optional, List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class QueryRequest(BaseModel):
    """Request model for vector search query."""
    question: str = Field(
        ...,
        description="The question or search query",
        min_length=1,
        max_length=1000,
        examples=["What is the candidate's experience with Python?"]
    )
    top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Number of results to return"
    )
    user_id: Optional[str] = Field(
        default=None,
        description="Optional user ID to filter results"
    )


class ChunkResult(BaseModel):
    """A single search result chunk."""
    content: str
    metadata: dict
    relevance_score: float


class QueryResponse(BaseModel):
    """Response model for vector search query."""
    success: bool
    query: str
    results_count: int
    results: List[ChunkResult]
    message: str


class VectorStoreStatsResponse(BaseModel):
    """Response model for vector store statistics."""
    collection_name: str
    document_count: int
    persist_directory: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "",
    response_model=QueryResponse,
    summary="Query Resume Vector Store",
    description="Search the vector database for relevant resume chunks using semantic similarity."
)
async def query_vector_store(request: QueryRequest) -> QueryResponse:
    """
    Perform semantic search over stored resume chunks.
    
    - **question**: The search query (e.g., "Python experience")
    - **top_k**: Number of results to return (1-10, default 3)
    - **user_id**: Optional filter by user ID
    
    Returns the most relevant resume chunks based on semantic similarity.
    """
    try:
        from app.services.vector_store import query_resume
        
        results = query_resume(
            query=request.question,
            k=request.top_k,
            user_id=request.user_id
        )
        
        # Convert to response format
        chunk_results = [
            ChunkResult(
                content=r["content"],
                metadata=r["metadata"],
                relevance_score=r["relevance_score"]
            )
            for r in results
        ]
        
        return QueryResponse(
            success=True,
            query=request.question,
            results_count=len(chunk_results),
            results=chunk_results,
            message=f"Found {len(chunk_results)} relevant chunks"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Query failed: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=VectorStoreStatsResponse,
    summary="Get Vector Store Statistics",
    description="Get information about the vector store collection."
)
async def get_vector_store_stats() -> VectorStoreStatsResponse:
    """
    Get statistics about the vector store.
    
    Returns collection name, document count, and persist directory.
    """
    try:
        from app.services.vector_store import get_vector_store
        
        vs = get_vector_store()
        stats = vs.get_collection_stats()
        
        if "error" in stats:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=stats["error"]
            )
        
        return VectorStoreStatsResponse(
            collection_name=stats["collection_name"],
            document_count=stats["document_count"],
            persist_directory=stats["persist_directory"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )
