"""
Project JobHunter V3 - Application Models
Job applications and learning history.
"""

import enum
import hashlib
from datetime import datetime
from typing import Optional, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Integer, ForeignKey, DateTime, Enum, func, Index
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.user import User


class ApplicationStatus(str, enum.Enum):
    """Job application status."""
    DRAFT = "draft"
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    OFFERED = "offered"
    ACCEPTED = "accepted"
    WITHDRAWN = "withdrawn"


class JobApplication(Base, TimestampMixin):
    """Job application tracking."""
    __tablename__ = "job_applications"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Job details
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    job_title: Mapped[str] = mapped_column(String(255), nullable=False)
    job_url: Mapped[Optional[str]] = mapped_column(String(2000))
    job_id: Mapped[Optional[str]] = mapped_column(String(255))  # External job ID
    
    # Location
    location: Mapped[Optional[str]] = mapped_column(String(255))
    remote_type: Mapped[Optional[str]] = mapped_column(String(50))  # remote, hybrid, onsite
    
    # Salary info
    salary_min: Mapped[Optional[int]] = mapped_column(Integer)
    salary_max: Mapped[Optional[int]] = mapped_column(Integer)
    salary_currency: Mapped[Optional[str]] = mapped_column(String(10), default="USD")
    
    # Application status
    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus, native_enum=False),
        default=ApplicationStatus.DRAFT,
        nullable=False,
        index=True
    )
    
    # Timestamps
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_activity_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Form data (what we filled in)
    form_data: Mapped[Optional[dict]] = mapped_column(JSONB)
    
    # Notes
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Associated task (if applied via automation)
    task_id: Mapped[Optional[str]] = mapped_column(String(36))  # UUID
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="applications")
    
    # Indexes
    __table_args__ = (
        Index("ix_job_applications_user_status", "user_id", "status"),
        Index("ix_job_applications_company", "company_name"),
    )
    
    def __repr__(self) -> str:
        return f"<JobApplication(id={self.id}, company={self.company_name}, status={self.status.value})>"


class LearningHistory(Base, TimestampMixin):
    """
    User corrections for continuous learning.
    
    When a user corrects a generated answer, we store it here
    to improve future predictions.
    """
    __tablename__ = "learning_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    
    # Question identification
    question_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Field context
    field_type: Mapped[Optional[str]] = mapped_column(String(50))  # text, select, radio, etc.
    field_label: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Original generated answer
    original_answer: Mapped[Optional[str]] = mapped_column(Text)
    
    # User's correction
    corrected_answer: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Context
    site_domain: Mapped[Optional[str]] = mapped_column(String(255))
    company_name: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="learning_history")
    
    # Indexes
    __table_args__ = (
        Index("ix_learning_history_user_question", "user_id", "question_hash"),
    )
    
    def __repr__(self) -> str:
        return f"<LearningHistory(id={self.id}, question_hash={self.question_hash[:8]})>"
    
    @staticmethod
    def hash_question(question: str) -> str:
        """Generate a hash for a question for deduplication."""
        normalized = question.lower().strip()
        return hashlib.sha256(normalized.encode()).hexdigest()
