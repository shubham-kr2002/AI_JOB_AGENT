"""
Project JobHunter V3 - User Models
User accounts and profiles (migrated from V1).
"""

import enum
from datetime import datetime
from typing import Optional, List, TYPE_CHECKING

from sqlalchemy import (
    String, Text, Integer, ForeignKey, DateTime, Boolean, Enum, func
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.task import Task
    from app.models.application import JobApplication, LearningHistory


class SubscriptionTier(str, enum.Enum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class User(Base, TimestampMixin):
    """User account model."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    
    # Auth (for future OAuth integration)
    password_hash: Mapped[Optional[str]] = mapped_column(String(255))
    auth_provider: Mapped[Optional[str]] = mapped_column(String(50))  # google, github, etc.
    auth_provider_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, native_enum=False),
        default=SubscriptionTier.FREE,
        nullable=False
    )
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Usage tracking
    tokens_used_this_month: Mapped[int] = mapped_column(Integer, default=0)
    applications_this_hour: Mapped[int] = mapped_column(Integer, default=0)
    
    # Relationships
    profile: Mapped[Optional["Profile"]] = relationship(
        "Profile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan"
    )
    tasks: Mapped[List["Task"]] = relationship(
        "Task",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    applications: Mapped[List["JobApplication"]] = relationship(
        "JobApplication",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    learning_history: Mapped[List["LearningHistory"]] = relationship(
        "LearningHistory",
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email={self.email})>"


class Profile(Base, TimestampMixin):
    """User profile with resume data."""
    __tablename__ = "profiles"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True
    )
    
    # Personal info
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    phone: Mapped[Optional[str]] = mapped_column(String(50))
    location: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Links
    linkedin_url: Mapped[Optional[str]] = mapped_column(String(500))
    portfolio_url: Mapped[Optional[str]] = mapped_column(String(500))
    github_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Resume metadata
    resume_filename: Mapped[Optional[str]] = mapped_column(String(255))
    resume_uploaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    resume_text: Mapped[Optional[str]] = mapped_column(Text)  # Raw extracted text
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="profile")
    
    def __repr__(self) -> str:
        return f"<Profile(user_id={self.user_id}, name={self.full_name})>"
