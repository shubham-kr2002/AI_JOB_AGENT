"""
Project JobHunter V3 - Execution Logs
Stores step-level logs and screenshot paths.

Reference: BackendTechnicalDesign.md Section 3A
- execution_logs: id, step_id, log_level, message, screenshot_path
"""

import enum
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Integer, ForeignKey, DateTime, Enum, 
    func, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.task import TaskStep


class LogLevel(str, enum.Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class ExecutionLog(Base):
    """
    Execution log entry for a task step.
    
    Provides detailed tracing of what happened during execution,
    including screenshots for visual debugging.
    """
    __tablename__ = "execution_logs"
    
    # Primary key
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    
    # Parent step
    step_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("task_steps.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Timestamp
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    
    # Log level
    log_level: Mapped[LogLevel] = mapped_column(
        Enum(LogLevel, native_enum=False),
        default=LogLevel.INFO,
        nullable=False
    )
    
    # Log message
    message: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Optional structured data
    data: Mapped[Optional[dict]] = mapped_column(JSONB)
    """
    Additional structured data:
    {
        "selector": ".apply-button",
        "action": "click",
        "element_found": true,
        "wait_time_ms": 234
    }
    """
    
    # Screenshot path (stored in object storage or local filesystem)
    screenshot_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # DOM snapshot path (for debugging selector issues)
    dom_snapshot_path: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Page URL at time of log
    page_url: Mapped[Optional[str]] = mapped_column(String(2000))
    
    # Relationships
    step: Mapped["TaskStep"] = relationship("TaskStep", back_populates="logs")
    
    # Indexes
    __table_args__ = (
        Index("ix_execution_logs_step_timestamp", "step_id", "timestamp"),
        Index("ix_execution_logs_level", "log_level"),
    )
    
    def __repr__(self) -> str:
        return f"<ExecutionLog(id={self.id}, level={self.log_level.value}, msg={self.message[:50]})>"
