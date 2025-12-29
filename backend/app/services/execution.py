"""
Project JobHunter V3 - Task Execution Service
Connects the Planner DAG to the Browser Executor

This service:
1. Takes a task graph from the Planner
2. Executes each node using the BrowserAgent
3. Tracks progress and handles errors
4. Supports real-time status updates
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json

from app.agents.executor import BrowserAgent, StepResult, ActionType
from app.services.planner import TaskGraph, DAGNode, NodeStatus
from app.core.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class TaskExecutionStatus(str, Enum):
    """Status of overall task execution."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_INTERVENTION = "waiting_intervention"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskExecution:
    """Tracks the state of a running task."""
    task_id: str
    prompt: str
    status: TaskExecutionStatus = TaskExecutionStatus.PENDING
    progress_percent: float = 0.0
    current_step: str = ""
    completed_steps: int = 0
    total_steps: int = 0
    steps_log: List[Dict[str, Any]] = field(default_factory=list)
    error_message: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    results: Dict[str, Any] = field(default_factory=dict)


# In-memory task store (in production, use Redis or database)
_task_store: Dict[str, TaskExecution] = {}


def get_task(task_id: str) -> Optional[TaskExecution]:
    """Get task execution by ID."""
    return _task_store.get(task_id)


def create_task_execution(task_id: str, prompt: str, total_steps: int = 0) -> TaskExecution:
    """Create a new TaskExecution entry in the in-memory store."""
    task = TaskExecution(
        task_id=task_id,
        prompt=prompt,
        status=TaskExecutionStatus.RUNNING,
        total_steps=total_steps,
        started_at=datetime.now(),
    )
    _task_store[task_id] = task
    logger.info(f"[Execution] Created task execution: {task_id}")
    return task


def update_task(task_id: str, **kwargs) -> Optional[TaskExecution]:
    """Update task execution fields."""
    task = _task_store.get(task_id)
    if task:
        for key, value in kwargs.items():
            if hasattr(task, key):
                setattr(task, key, value)
    return task


def report_step(
    task_id: str,
    step_id: str,
    step_name: str | None,
    success: bool,
    data: Optional[Dict[str, Any]] = None,
    error: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Optional[TaskExecution]:
    """Report a step result for an in-tab executed task.

    This updates progress, logs the step, and completes the task if all steps are done.
    """
    task = _task_store.get(task_id)
    if not task:
        return None

    # Append step log
    step_log = {
        "node_id": step_id,
        "name": step_name,
        "success": success,
        "error": error,
        "data": data,        "meta": meta,        "timestamp": datetime.now().isoformat(),
    }
    task.steps_log.append(step_log)

    if success:
        task.completed_steps += 1

    task.current_step = step_name or task.current_step

    # Update progress
    if task.total_steps > 0:
        task.progress_percent = min(100.0, (task.completed_steps / task.total_steps) * 100.0)

    # If completed
    if task.total_steps > 0 and task.completed_steps >= task.total_steps:
        task.status = TaskExecutionStatus.COMPLETED
        task.completed_at = datetime.now()
        task.progress_percent = 100.0

    if error:
        task.error_message = error
        task.status = TaskExecutionStatus.FAILED

    return task


class TaskExecutor:
    """
    Executes task graphs using the BrowserAgent.
    
    This is the orchestration layer that:
    1. Traverses the DAG in dependency order
    2. Calls BrowserAgent for each step
    3. Handles failures and retries
    4. Reports progress in real-time
    """
    
    def __init__(
        self,
        headless: bool = False,  # Default to headed for visibility
        on_progress: Optional[Callable[[str, float, str], None]] = None,
    ):
        """
        Initialize the executor.
        
        Args:
            headless: Whether to run browser in headless mode
            on_progress: Callback for progress updates (task_id, percent, message)
        """
        self.headless = headless
        self.on_progress = on_progress
        self.browser_agent: Optional[BrowserAgent] = None
        self._cancelled = False
    
    async def execute_task(
        self,
        task_id: str,
        prompt: str,
        graph: TaskGraph,
    ) -> TaskExecution:
        """
        Execute a complete task graph.
        
        Args:
            task_id: Unique task identifier
            prompt: Original user prompt
            graph: Task graph from planner
            
        Returns:
            TaskExecution with results and status
        """
        # Initialize task tracking
        task = TaskExecution(
            task_id=task_id,
            prompt=prompt,
            status=TaskExecutionStatus.RUNNING,
            total_steps=len(graph.nodes),
            started_at=datetime.now(),
        )
        _task_store[task_id] = task
        
        logger.info(f"[Executor] Starting task {task_id}: {prompt}")
        logger.info(f"[Executor] {len(graph.nodes)} steps to execute")
        
        try:
            # Launch browser
            self.browser_agent = BrowserAgent(headless=self.headless)
            page = await self.browser_agent.launch_browser()
            
            self._update_progress(task, 5, "Browser launched")
            
            # Build dependency map for topological execution
            node_map = {node.id: node for node in graph.nodes}
            completed_nodes: set = set()
            
            # Execute nodes in dependency order
            while len(completed_nodes) < len(graph.nodes) and not self._cancelled:
                # Find ready nodes (all dependencies complete)
                ready_nodes = [
                    node for node in graph.nodes
                    if node.id not in completed_nodes
                    and all(dep in completed_nodes for dep in node.depends_on)
                ]
                
                if not ready_nodes:
                    if len(completed_nodes) < len(graph.nodes):
                        logger.error("[Executor] Deadlock: no ready nodes but task incomplete")
                        raise Exception("Execution deadlock - circular dependencies?")
                    break
                
                # Execute ready nodes (could parallelize, but sequential is safer)
                for node in ready_nodes:
                    if self._cancelled:
                        break
                    
                    task.current_step = node.name
                    self._update_progress(
                        task,
                        10 + (len(completed_nodes) / len(graph.nodes)) * 85,
                        f"Executing: {node.name}"
                    )
                    
                    # Convert node to step data for BrowserAgent
                    step_data = self._node_to_step(node)
                    
                    logger.info(f"[Executor] Step {node.id}: {node.name} - {node.action}")
                    
                    # Handle special non-browser actions
                    if node.action in ("aggregate", "rank", "loop", "summarize", "generate", "parse", "filter", "analyze"):
                        result = await self._handle_special_action(node, task)
                    else:
                        # Execute browser step
                        result = await self.browser_agent.execute_step(step_data)
                    
                    # Log result
                    step_log = {
                        "node_id": node.id,
                        "name": node.name,
                        "action": node.action,
                        "success": result.success,
                        "error": result.error,
                        "duration_ms": result.duration_ms,
                        "timestamp": datetime.now().isoformat(),
                    }
                    task.steps_log.append(step_log)
                    
                    if result.success:
                        completed_nodes.add(node.id)
                        task.completed_steps = len(completed_nodes)
                        node.status = NodeStatus.COMPLETED
                        
                        # Store any extracted data
                        if result.data:
                            task.results[node.id] = result.data
                    else:
                        # Handle failure
                        node.retry_count += 1
                        if node.retry_count >= node.max_retries:
                            node.status = NodeStatus.FAILED
                            raise Exception(f"Step '{node.name}' failed after {node.max_retries} retries: {result.error}")
                        else:
                            logger.warning(f"[Executor] Retry {node.retry_count}/{node.max_retries} for {node.name}")
                            # Add small delay before retry
                            await asyncio.sleep(2)
            
            # Success!
            if self._cancelled:
                task.status = TaskExecutionStatus.CANCELLED
                task.error_message = "Task was cancelled by user"
            else:
                task.status = TaskExecutionStatus.COMPLETED
                self._update_progress(task, 100, "Task completed successfully!")
            
        except Exception as e:
            logger.error(f"[Executor] Task {task_id} failed: {e}")
            task.status = TaskExecutionStatus.FAILED
            task.error_message = str(e)
            self._update_progress(task, task.progress_percent, f"Error: {e}")
        
        finally:
            # Clean up browser
            if self.browser_agent:
                await self.browser_agent.close()
            
            task.completed_at = datetime.now()
        
        return task
    
    async def _handle_special_action(self, node: DAGNode, task: TaskExecution) -> StepResult:
        """
        Handle special non-browser actions like aggregate, rank, loop, summarize.
        
        These are orchestration-level actions that don't need browser automation.
        """
        import time
        start_time = time.time()
        
        try:
            if node.action == "aggregate":
                # Combine results from dependency nodes
                combined_data = {}
                for dep_id in node.depends_on:
                    if dep_id in task.results:
                        combined_data[dep_id] = task.results[dep_id]
                
                return StepResult(
                    success=True,
                    action="aggregate",
                    data={"aggregated": combined_data, "source_count": len(combined_data)},
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "rank":
                # Rank/score the aggregated results
                # In a real implementation, this would use an LLM to rank jobs
                data = {
                    "ranked": True,
                    "criteria": node.payload.get("criteria", ["relevance"]),
                    "note": "Ranking placeholder - would use LLM scoring",
                }
                
                return StepResult(
                    success=True,
                    action="rank",
                    data=data,
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "loop":
                # Loop control - handled at executor level
                # This is a placeholder; real implementation would iterate
                return StepResult(
                    success=True,
                    action="loop",
                    data={
                        "iterations": node.payload.get("limit", 0),
                        "note": "Loop control - would spawn sub-tasks",
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "summarize":
                # Generate a summary report
                return StepResult(
                    success=True,
                    action="summarize",
                    data={
                        "summary": f"Task completed: {task.prompt}",
                        "steps_executed": task.completed_steps,
                        "results_count": len(task.results),
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "generate":
                # LLM generation (e.g., tailored resume)
                return StepResult(
                    success=True,
                    action="generate",
                    data={
                        "generated": True,
                        "type": node.payload.get("type", "unknown"),
                        "note": "Generation placeholder - would use LLM",
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "parse":
                # Parse search results into structured data
                return StepResult(
                    success=True,
                    action="parse",
                    data={
                        "parsed": True,
                        "operation": node.payload.get("operation", "extract_job_list"),
                        "note": "Parsing search results",
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "filter":
                # Filter results based on criteria
                return StepResult(
                    success=True,
                    action="filter",
                    data={
                        "filtered": True,
                        "blacklist_applied": True,
                        "min_score": node.payload.get("min_score", 0.7),
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            elif node.action == "analyze":
                # Analyze and rank results
                return StepResult(
                    success=True,
                    action="analyze",
                    data={
                        "analyzed": True,
                        "criteria": node.payload.get("criteria", []),
                        "note": "Analysis placeholder - would use LLM scoring",
                    },
                    duration_ms=int((time.time() - start_time) * 1000)
                )
            
            else:
                return StepResult(
                    success=False,
                    action=node.action,
                    error=f"Unknown special action: {node.action}",
                    duration_ms=int((time.time() - start_time) * 1000)
                )
                
        except Exception as e:
            return StepResult(
                success=False,
                action=node.action,
                error=str(e),
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _node_to_step(self, node: DAGNode) -> Dict[str, Any]:
        """Convert a DAG node to a step dictionary for BrowserAgent."""
        step = {
            "action": node.action,
            **node.payload,
        }
        return step
    
    def _update_progress(self, task: TaskExecution, percent: float, message: str):
        """Update task progress and notify via callback."""
        task.progress_percent = percent
        task.current_step = message
        
        if self.on_progress:
            self.on_progress(task.task_id, percent, message)
        
        logger.info(f"[Executor] Progress {percent:.1f}%: {message}")
    
    def cancel(self):
        """Cancel the running task."""
        self._cancelled = True


async def execute_task_async(
    task_id: str,
    prompt: str,
    graph: TaskGraph,
    headless: bool = False,
) -> TaskExecution:
    """
    Execute a task graph asynchronously.
    
    This is the main entry point for task execution.
    """
    executor = TaskExecutor(headless=headless)
    return await executor.execute_task(task_id, prompt, graph)


def run_task_background(task_id: str, prompt: str, graph_dict: Dict[str, Any]):
    """
    Run a task in the background using asyncio.
    
    This can be called from a sync context (like FastAPI endpoint).
    """
    from app.services.planner import TaskGraph
    
    # Reconstruct graph from dict
    graph = TaskGraph.from_dict(graph_dict)
    
    # Run in new event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(
            execute_task_async(task_id, prompt, graph, headless=False)
        )
        return result
    finally:
        loop.close()
