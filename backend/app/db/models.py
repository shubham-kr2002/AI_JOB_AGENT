"""
Database Models - SQLAlchemy ORM Models.

Schema from BTD.md:
- users: id, email, subscription_tier, created_at
- profiles: user_id, full_name, linkedin_url, portfolio_url, phone
- job_applications: id, user_id, company_name, job_title, status, timestamp
- learning_history: id, user_id, question_hash, question_text, user_corrected_answer
"""

import hashlib
from datetime import datetime
from typing import Optional

from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
import enum

from app.db.database import Base


class SubscriptionTier(enum.Enum):
    """User subscription tiers."""
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class ApplicationStatus(enum.Enum):
    """Job application status."""
    DRAFT = "draft"
    APPLIED = "applied"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    OFFERED = "offered"
    ACCEPTED = "accepted"


class User(Base):
    """User account model."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    subscription_tier = Column(
        Enum(SubscriptionTier), 
        default=SubscriptionTier.FREE
    )
    created_at = Column(DateTime, default=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    profile = relationship("Profile", back_populates="user", uselist=False)
    applications = relationship("JobApplication", back_populates="user")
    learning_history = relationship("LearningHistory", back_populates="user")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email})>"


class Profile(Base):
    """User profile with resume data."""
    __tablename__ = "profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # Personal info
    full_name = Column(String(255))
    phone = Column(String(50))
    location = Column(String(255))
    
    # Links
    linkedin_url = Column(String(500))
    portfolio_url = Column(String(500))
    github_url = Column(String(500))
    
    # Resume metadata
    resume_filename = Column(String(255))
    resume_uploaded_at = Column(DateTime)
    resume_text = Column(Text)  # Raw extracted text
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="profile")
    
    def __repr__(self):
        return f"<Profile(user_id={self.user_id}, name={self.full_name})>"


class JobApplication(Base):
    """Job application tracking."""
    __tablename__ = "job_applications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Job details
    company_name = Column(String(255), nullable=False)
    job_title = Column(String(255), nullable=False)
    job_url = Column(String(1000))
    job_description = Column(Text)  # Store scraped JD
    
    # Application status
    status = Column(
        Enum(ApplicationStatus),
        default=ApplicationStatus.DRAFT
    )
    
    # Timestamps
    applied_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="applications")
    
    def __repr__(self):
        return f"<JobApplication(company={self.company_name}, title={self.job_title})>"


class LearningHistory(Base):
    """
    Learning loop storage - stores user corrections to improve future answers.
    
    This is the "secret sauce" from BTD.md:
    When a user corrects an AI answer, we store it to improve future accuracy.
    """
    __tablename__ = "learning_history"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Question identification
    question_hash = Column(String(64), index=True, nullable=False)  # SHA256 of normalized question
    question_text = Column(Text, nullable=False)  # Original question text
    field_type = Column(String(50))  # input, textarea, select, etc.
    
    # Answers
    original_answer = Column(Text)  # What the AI generated
    corrected_answer = Column(Text, nullable=False)  # What the user changed it to
    
    # Context (for better retrieval)
    job_context = Column(Text)  # Company/role context when correction was made
    
    # Metadata
    times_used = Column(Integer, default=0)  # How many times this correction was retrieved
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="learning_history")
    
    @staticmethod
    def hash_question(question: str) -> str:
        """
        Create a normalized hash of a question for matching similar questions.
        
        Normalization:
        - Lowercase
        - Remove extra whitespace
        - Remove punctuation
        """
        import re
        normalized = question.lower().strip()
        normalized = re.sub(r'\s+', ' ', normalized)
        normalized = re.sub(r'[^\w\s]', '', normalized)
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def __repr__(self):
        return f"<LearningHistory(question={self.question_text[:50]}...)>"
