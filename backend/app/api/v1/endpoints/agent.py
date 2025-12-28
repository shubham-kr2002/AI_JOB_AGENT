"""
Project JobHunter V3 - Agent Endpoints
Implements the autonomous agent control plane.

Endpoints:
- POST /agent/plan: Parse intent and generate execution plan
- POST /agent/tasks: Create and queue an autonomous task
- GET /agent/tasks/{task_id}: Get task status
- WS /agent/tasks/{task_id}/stream: Real-time execution feed (FR-02)
"""

from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.intent import compile_intent, Goal
from app.services.planner import generate_task_graph, plan_from_prompt

router = APIRouter()


# =============================================================================
# Request/Response Models
# =============================================================================

class PlanRequest(BaseModel):
    """Request body for generating an execution plan."""
    prompt: str = Field(
        ...,
        description="Natural language prompt describing the goal",
        min_length=10,
        max_length=1000,
        examples=[
            "Apply to 10 Product Manager roles in NYC",
            "Find 5 remote Python developer jobs at YCombinator startups. Avoid crypto.",
            "Search for Senior Software Engineer positions paying over $150k",
        ]
    )
    use_llm: bool = Field(
        default=True,
        description="Whether to use LLM for enhanced intent parsing"
    )


class GoalResponse(BaseModel):
    """Structured goal extracted from the prompt."""
    action: str
    role: str
    role_keywords: list[str]
    target_count: int
    platforms: list[str]
    raw_prompt: str
    constraints: dict


class PlanNodeResponse(BaseModel):
    """A single node in the execution plan."""
    id: str
    name: str
    action: str
    depends_on: list[str]
    payload: dict
    outputs: list[str]
    status: str
    estimated_duration_seconds: int


class TaskGraphResponse(BaseModel):
    """The complete execution plan."""
    goal_summary: str
    total_nodes: int
    total_estimated_seconds: int
    nodes: list[PlanNodeResponse]


class PlanResponse(BaseModel):
    """Response containing the parsed goal and execution plan."""
    success: bool = True
    goal: GoalResponse
    plan: TaskGraphResponse


class TaskCreateRequest(BaseModel):
    """Request to create and queue an autonomous task."""
    prompt: str = Field(
        ...,
        description="Natural language prompt describing the goal",
        min_length=10,
    )
    auto_start: bool = Field(
        default=True,
        description="Whether to start execution immediately"
    )
    dry_run: bool = Field(
        default=False,
        description="If true, generate plan but don't execute"
    )


class TaskCreateResponse(BaseModel):
    """Response after creating a task."""
    success: bool = True
    task_id: str
    status: str
    plan_summary: str
    total_steps: int
    estimated_duration_seconds: int
    message: str


class TaskStatusResponse(BaseModel):
    """Current status of a task."""
    task_id: str
    status: str
    progress_percent: float
    completed_steps: int
    total_steps: int
    current_step: Optional[str] = None
    error_message: Optional[str] = None


# =============================================================================
# Endpoints
# =============================================================================

@router.post("/plan", response_model=PlanResponse)
async def create_plan(request: PlanRequest):
    """
    Parse a natural language prompt and generate an execution plan.
    
    This endpoint does NOT execute the plan - it only generates it for preview.
    Use POST /agent/tasks to actually execute a plan.
    
    **FR-01**: Intent-Based Input
    **FR-04**: DAG Generation
    
    Example prompts:
    - "Apply to 10 Product Manager roles in NYC"
    - "Find 5 remote Python developer jobs at YCombinator startups. Avoid crypto."
    - "Search for Senior Software Engineer positions paying over $150k"
    """
    try:
        # Step 1: Compile intent from prompt
        goal = compile_intent(request.prompt, use_llm=request.use_llm)
        
        # Step 2: Generate task graph
        graph = generate_task_graph(goal)
        
        return PlanResponse(
            success=True,
            goal=GoalResponse(
                action=goal.action.value,
                role=goal.role,
                role_keywords=goal.role_keywords,
                target_count=goal.target_count,
                platforms=goal.platforms,
                raw_prompt=goal.raw_prompt,
                constraints=goal.constraints.to_dict(),
            ),
            plan=TaskGraphResponse(
                goal_summary=graph.goal_summary,
                total_nodes=len(graph.nodes),
                total_estimated_seconds=graph.total_estimated_seconds,
                nodes=[
                    PlanNodeResponse(
                        id=node.id,
                        name=node.name,
                        action=node.action,
                        depends_on=node.depends_on,
                        payload=node.payload,
                        outputs=node.outputs,
                        status=node.status.value,
                        estimated_duration_seconds=node.estimated_duration_seconds,
                    )
                    for node in graph.nodes
                ],
            ),
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate plan: {str(e)}"
        )


@router.post("/tasks", response_model=TaskCreateResponse)
async def create_task(request: TaskCreateRequest, background_tasks: BackgroundTasks):
    """
    Create and optionally start an autonomous task.
    
    This endpoint:
    1. Parses the prompt into a Goal
    2. Generates an execution DAG
    3. Creates a Task record in the database
    4. Queues the task for execution (if auto_start=true)
    
    Use the returned task_id to:
    - Check status: GET /agent/tasks/{task_id}
    - Stream updates: WS /agent/tasks/{task_id}/stream
    - Intervene: POST /agent/tasks/{task_id}/intervene
    """
    try:
        # Step 1: Compile intent
        goal = compile_intent(request.prompt, use_llm=True)
        
        # Step 2: Generate plan
        graph = generate_task_graph(goal)
        
        # Step 3: Create task record (TODO: Save to database)
        task_id = str(uuid4())
        
        # Step 4: Queue for execution if auto_start
        if request.auto_start and not request.dry_run:
            # TODO: Push to Celery queue
            # from app.core.celery_app import execute_task_graph
            # background_tasks.add_task(execute_task_graph.delay, task_id, graph.to_dict())
            status = "queued"
            message = f"Task queued for execution. {len(graph.nodes)} steps to complete."
        elif request.dry_run:
            status = "dry_run"
            message = "Dry run completed. Plan generated but not executed."
        else:
            status = "created"
            message = "Task created. Call POST /agent/tasks/{task_id}/start to begin execution."
        
        return TaskCreateResponse(
            success=True,
            task_id=task_id,
            status=status,
            plan_summary=graph.goal_summary,
            total_steps=len(graph.nodes),
            estimated_duration_seconds=graph.total_estimated_seconds,
            message=message,
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create task: {str(e)}"
        )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the current status of an autonomous task.
    
    Returns progress information and current step being executed.
    """
    # TODO: Fetch from database
    # For now, return a mock response
    return TaskStatusResponse(
        task_id=task_id,
        status="running",
        progress_percent=35.0,
        completed_steps=3,
        total_steps=8,
        current_step="Searching LinkedIn",
        error_message=None,
    )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """
    Cancel a running task.
    
    The task will stop at the next checkpoint and clean up resources.
    """
    # TODO: Implement cancellation via Celery
    return {
        "success": True,
        "task_id": task_id,
        "status": "cancelling",
        "message": "Task cancellation requested. Will stop at next checkpoint.",
    }


@router.post("/tasks/{task_id}/intervene")
async def intervene_task(
    task_id: str,
    step_id: Optional[str] = None,
    action: str = "retry",
    human_input: Optional[str] = None,
):
    """
    Manually intervene in a paused task.
    
    **FR-03**: Human-in-the-Loop Interventions
    
    Use this endpoint when:
    - 2FA is required
    - CAPTCHA needs solving
    - Agent needs clarification
    
    Args:
        task_id: The task ID
        step_id: Optional specific step to intervene on
        action: "retry", "skip", "abort", or "provide_input"
        human_input: Input from the human (e.g., 2FA code)
    """
    # TODO: Implement intervention handling
    return {
        "success": True,
        "task_id": task_id,
        "step_id": step_id,
        "action": action,
        "message": f"Intervention '{action}' applied. Task resuming.",
    }
