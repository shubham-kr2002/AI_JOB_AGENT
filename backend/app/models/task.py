"""
Project JobHunter V3 - Task Models
Defines Task (Goal, Status) and TaskStep (Action type, Status, JSON Payload).

Reference: BackendTechnicalDesign.md Section 3A
- tasks: id, user_id, raw_prompt, status (queued/running/completed/failed), created_at
- task_steps: id, task_id, step_order, action_type (search/scrape/apply), status, payload (JSON)
"""

import enum
from datetime import datetime
from typing import Optional, List, Any, TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import (
    String, Text, Integer, ForeignKey, DateTime, Enum, 
    func, Index, CheckConstraint
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.logs import ExecutionLog


class TaskStatus(str, enum.Enum):
    """Status of an autonomous task."""
    QUEUED = "queued"           # Waiting to be picked up by worker
    PLANNING = "planning"       # Planner agent generating DAG
    RUNNING = "running"         # Executor agent working
    PAUSED = "paused"           # Waiting for human intervention (2FA, CAPTCHA)
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Failed after retries
    CANCELLED = "cancelled"     # Cancelled by user


class StepStatus(str, enum.Enum):
    """Status of an individual task step."""
    PENDING = "pending"         # Not yet started
    RUNNING = "running"         # Currently executing
    COMPLETED = "completed"     # Successfully finished
    FAILED = "failed"           # Failed
    SKIPPED = "skipped"         # Skipped (conditional branch)
    BLOCKED = "blocked"         # Waiting for dependency


class ActionType(str, enum.Enum):
    """Type of action for a task step."""
    # Navigation actions
    NAVIGATE = "navigate"       # Go to URL
    LOGIN = "login"             # Authenticate
    
    # Search actions
    SEARCH = "search"           # Search for jobs
    FILTER = "filter"           # Apply filters
    PAGINATE = "paginate"       # Go to next page
    
    # Scraping actions
    SCRAPE = "scrape"           # Extract data from page
    PARSE = "parse"             # Parse extracted data
    
    # Application actions
    APPLY = "apply"             # Start application
    FILL_FORM = "fill_form"     # Fill form fields
    UPLOAD = "upload"           # Upload file (resume)
    SUBMIT = "submit"           # Submit application
    
    # Verification actions
    VERIFY = "verify"           # Verify action succeeded
    SCREENSHOT = "screenshot"   # Capture screenshot
    
    # Control flow
    WAIT = "wait"               # Wait for condition
    CONDITION = "condition"     # Conditional branch
    HUMAN_INPUT = "human_input" # Request human help


class Task(Base, TimestampMixin):
    """
    Autonomous task representing a high-level goal.
    
    Example: "Find 5 remote python jobs and apply"
    """
    __tablename__ = "tasks"
    
    # Primary key - UUID for distributed systems
    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid4())
    )
    
    # User who created the task
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # The raw user prompt/goal
    raw_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False
    )
    
    # Compiled intent (LLM-parsed JSON goal)
    compiled_intent: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )
    
    # Task status
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, native_enum=False),
        default=TaskStatus.QUEUED,
        nullable=False,
        index=True
    )
    
    # Progress tracking
    total_steps: Mapped[int] = mapped_column(Integer, default=0)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0)
    
    # Execution metadata
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Error info if failed
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Result summary (e.g., "Applied to 5 jobs successfully")
    result_summary: Mapped[Optional[str]] = mapped_column(Text)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="tasks")
    steps: Mapped[List["TaskStep"]] = relationship(
        "TaskStep",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskStep.step_order"
    )
    
    # Indexes
    __table_args__ = (
        Index("ix_tasks_user_status", "user_id", "status"),
        Index("ix_tasks_created_at", "created_at"),
    )
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id[:8]}, status={self.status.value})>"
    
    @property
    def progress_percent(self) -> float:
        """Calculate progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.completed_steps / self.total_steps) * 100


class TaskStep(Base, TimestampMixin):
    """
    Individual step within a task's execution DAG.
    
    Each step represents a single action (click, fill, submit, etc.)
    """
    __tablename__ = "task_steps"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Parent task
    task_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Step order in the DAG (can have same order for parallel steps)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False)
    
    # DAG node ID (for dependency tracking)
    node_id: Mapped[str] = mapped_column(String(50), nullable=False)
    
    # Dependencies (list of node_ids that must complete first)
    depends_on: Mapped[Optional[list]] = mapped_column(JSONB, default=list)
    
    # Action type
    action_type: Mapped[ActionType] = mapped_column(
        Enum(ActionType, native_enum=False),
        nullable=False
    )
    
    # Step status
    status: Mapped[StepStatus] = mapped_column(
        Enum(StepStatus, native_enum=False),
        default=StepStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Action payload (varies by action_type)
    # Example: {"selector": "#email", "value": "user@example.com"}
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    
    # Execution result
    result: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Retry count
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    
    # Error info
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    task: Mapped["Task"] = relationship("Task", back_populates="steps")
    logs: Mapped[List["ExecutionLog"]] = relationship(
        "ExecutionLog",
        back_populates="step",
        cascade="all, delete-orphan"
    )
    
    # Indexes and constraints
    __table_args__ = (
        Index("ix_task_steps_task_order", "task_id", "step_order"),
        Index("ix_task_steps_status", "status"),
        CheckConstraint("step_order >= 0", name="positive_step_order"),
    )
    
    def __repr__(self) -> str:
        return f"<TaskStep(id={self.id}, node={self.node_id}, action={self.action_type.value})>"
