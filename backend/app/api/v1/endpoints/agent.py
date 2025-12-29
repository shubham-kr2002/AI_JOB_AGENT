"""
Project JobHunter V3 - Agent Endpoints
Implements the autonomous agent control plane.

Endpoints:
- POST /agent/plan: Parse intent and generate execution plan
- POST /agent/tasks: Create and queue an autonomous task
- GET /agent/tasks/{task_id}: Get task status
- WS /agent/tasks/{task_id}/stream: Real-time execution feed (FR-02)
"""

import asyncio
import logging
from typing import Optional
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field

from app.services.intent import compile_intent, Goal
from app.services.planner import generate_task_graph, plan_from_prompt
from app.services.execution import (
    execute_task_async,
    get_task,
    TaskExecution,
    TaskExecutionStatus,
    run_task_background,
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread pool for running browser automation
_executor = ThreadPoolExecutor(max_workers=4)


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
    # Execution mode: 'playwright' (backend opens browser) or 'in_tab' (extension executes in the active tab)
    execution_mode: Optional[str] = Field(
        default="playwright",
        description="Execution mode for the task: 'playwright' or 'in_tab'"
    )
    # Optional metadata for in-tab execution (tab id)
    tab_id: Optional[int] = Field(default=None, description="Optional tab id when using in_tab execution")
    # Optional CDP attach flags (advanced)
    use_cdp: Optional[bool] = Field(default=False, description="Whether to attach to an existing browser via CDP (advanced)")
    cdp_endpoint: Optional[str] = Field(default=None, description="CDP endpoint websocket URL, e.g., ws://127.0.0.1:9222")


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
# Execution control endpoints for extension-based execution
# =============================================================================


class ExecutionClaim(BaseModel):
    """Claim a waiting task for in-tab execution."""
    tab_id: Optional[int] = None
    mode: Optional[str] = "in_tab"


class StepReport(BaseModel):
    """Report a step result from in-tab execution."""
    step_id: str
    step_name: Optional[str] = None
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    meta: Optional[Dict[str, Any]] = None  # e.g., attempt, timestamp, extra diagnostics


@router.post("/tasks/{task_id}/claim")
async def claim_task(task_id: str, claim: ExecutionClaim):
    """Claim a waiting task for execution (used by the extension for in-tab mode)."""
    try:
        # Create or mark task as running in the execution store
        from app.services.execution import create_task_execution, get_task

        # If task exists, update, else create
        task = get_task(task_id)
        if not task:
            create_task_execution(task_id, prompt="[in-tab claimed task]", total_steps=0)
        else:
            # Mark running
            from app.services.execution import update_task
            update_task(task_id, status="running")

        return {"success": True, "task_id": task_id, "status": "running"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tasks/{task_id}/report")
async def report_step(task_id: str, report: StepReport):
    """Report a step result from in-tab execution (extension -> backend)."""
    try:
        from app.services.execution import report_step, get_task

        task = report_step(
            task_id=task_id,
            step_id=report.step_id,
            step_name=report.step_name,
            success=report.success,
            data=report.data,
            error=report.error,
            meta=report.meta,
        )

        if not task:
            raise Exception("Task not found")

        return {"success": True, "task_id": task_id, "status": task.status, "progress": task.progress_percent}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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
        logger.info(f"[Agent API] Received task request: {request.prompt}")
        
        # Step 1: Compile intent
        goal = compile_intent(request.prompt, use_llm=True)
        logger.info(f"[Agent API] Compiled goal: {goal.action} - {goal.role}")
        
        # Step 2: Generate plan
        graph = generate_task_graph(goal)
        logger.info(f"[Agent API] Generated graph with {len(graph.nodes)} nodes")
        
        # Step 3: Create task record
        task_id = str(uuid4())
        
        # Step 4: Queue for execution if auto_start
        if request.auto_start and not request.dry_run:
            if request.execution_mode == "in_tab":
                # In-Tab execution: create task record but do not start backend executor
                from app.services.execution import create_task_execution
                create_task_execution(task_id, request.prompt, total_steps=len(graph.nodes))
                status = "waiting"  # Waiting for extension to claim and execute the task
                message = f"Task created for in-tab execution. Claim this task from the extension to start executing {len(graph.nodes)} steps."
            else:
                # Execute in background thread (browser automation needs its own event loop)
                logger.info(f"[Agent API] Starting background execution for task {task_id}")
                
                # Use background task to run the browser automation
                def run_browser_task():
                    try:
                        result = run_task_background(task_id, request.prompt, graph.to_dict())
                        logger.info(f"[Agent API] Task {task_id} completed: {result.status}")
                    except Exception as e:
                        logger.error(f"[Agent API] Task {task_id} failed: {e}")
                
                _executor.submit(run_browser_task)
                
                status = "running"
                if request.use_cdp:
                    message = f"Task started! Will attach to an existing browser via CDP and execute {len(graph.nodes)} steps."
                else:
                    message = f"Task started! Browser will open and execute {len(graph.nodes)} steps."
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
        logger.error(f"[Agent API] Failed to create task: {e}")
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
    # Fetch from in-memory task store
    task = get_task(task_id)
    
    if task is None:
        # Task not found - could be pending or invalid
        return TaskStatusResponse(
            task_id=task_id,
            status="not_found",
            progress_percent=0.0,
            completed_steps=0,
            total_steps=0,
            current_step="Task not found or still initializing",
            error_message=None,
        )
    
    # Calculate progress
    total = task.total_steps
    completed = task.completed_steps
    progress = (completed / total * 100) if total > 0 else 0.0
    
    # Convert enum to string if needed
    status_str = task.status.value if hasattr(task.status, 'value') else str(task.status)
    
    return TaskStatusResponse(
        task_id=task_id,
        status=status_str,
        progress_percent=progress,
        completed_steps=completed,
        total_steps=total,
        current_step=task.current_step or "Initializing...",
        error_message=task.error_message,
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
