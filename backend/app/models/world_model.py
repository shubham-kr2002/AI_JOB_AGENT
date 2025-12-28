"""
Project JobHunter V3 - World Model
Site-specific configurations with CSS selectors and login settings.

Reference: BackendTechnicalDesign.md Section 3B
- sites:
    - domain (Primary Key): e.g., "linkedin.com"
    - login_config: {"requires_2fa": true, "login_url": "/login"}
    - selectors: {"job_card": ".job-search-card", "apply_button": "button[...]"}
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, DateTime, Boolean, Integer, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class SiteConfig(Base, TimestampMixin):
    """
    World Model - Site-specific configuration and learned selectors.
    
    This table grows smarter over time as the agent learns
    which selectors work for each job site.
    """
    __tablename__ = "sites"
    
    # Domain is the primary key (e.g., "linkedin.com", "greenhouse.io")
    domain: Mapped[str] = mapped_column(
        String(255),
        primary_key=True
    )
    
    # Human-readable site name
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Site category for routing
    category: Mapped[str] = mapped_column(
        String(50),
        default="job_board",
        nullable=False
    )
    # Categories: job_board, ats, company_career, aggregator
    
    # =========================================================================
    # Login Configuration
    # =========================================================================
    login_config: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    """
    Login configuration schema:
    {
        "requires_auth": true,
        "login_url": "/login",
        "auth_type": "credentials|oauth|sso",
        "requires_2fa": false,
        "2fa_method": "email|sms|app",
        "session_duration_hours": 24,
        "selectors": {
            "username_field": "#username",
            "password_field": "#password",
            "submit_button": "button[type='submit']",
            "2fa_input": "#otp-input"
        }
    }
    """
    
    # =========================================================================
    # Page Selectors (The Knowledge Library)
    # =========================================================================
    selectors: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    """
    CSS/XPath selectors that work for this site:
    {
        "job_list": {
            "container": ".jobs-search-results",
            "job_card": ".job-search-card",
            "job_title": ".job-search-card__title",
            "company_name": ".job-search-card__subtitle",
            "location": ".job-search-card__location"
        },
        "job_detail": {
            "apply_button": "button[aria-label='Easy Apply']",
            "job_description": ".jobs-description__content",
            "requirements": ".jobs-description__requirements"
        },
        "application_form": {
            "next_button": "button[aria-label='Continue']",
            "submit_button": "button[aria-label='Submit application']",
            "upload_resume": "input[type='file']",
            "field_mappings": {
                "email": "input[name='email']",
                "phone": "input[name='phone']",
                "linkedin": "input[name='linkedin']"
            }
        },
        "pagination": {
            "next_page": ".pagination-next",
            "page_number": ".pagination-current",
            "total_pages": ".pagination-total"
        }
    }
    """
    
    # =========================================================================
    # Behavior Configuration
    # =========================================================================
    behavior: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        nullable=False
    )
    """
    Site-specific behavior settings:
    {
        "rate_limit_ms": 2000,
        "requires_stealth": true,
        "blocked_detection": {
            "indicators": [".captcha-container", "#blocked-message"],
            "recovery": "wait_and_retry"
        },
        "ajax_wait_ms": 1000,
        "scroll_behavior": "lazy_load",
        "human_delays": {
            "typing_ms": [50, 150],
            "click_ms": [200, 500]
        }
    }
    """
    
    # =========================================================================
    # API Configuration (if site has API)
    # =========================================================================
    api_config: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True
    )
    """
    Optional API configuration for sites with APIs:
    {
        "has_api": true,
        "base_url": "https://api.linkedin.com/v2",
        "auth_type": "oauth2",
        "endpoints": {
            "search_jobs": "/jobSearch",
            "apply": "/applications"
        },
        "rate_limits": {
            "requests_per_minute": 60
        }
    }
    """
    
    # =========================================================================
    # Learning Metrics
    # =========================================================================
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, default=0)
    last_successful_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Confidence score (0-1) based on success rate
    @property
    def confidence_score(self) -> float:
        """Calculate confidence based on success/failure ratio."""
        total = self.success_count + self.failure_count
        if total == 0:
            return 0.5  # Neutral for new sites
        return self.success_count / total
    
    # Is this site currently working?
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Notes for debugging
    notes: Mapped[Optional[str]] = mapped_column(Text)
    
    # Indexes
    __table_args__ = (
        Index("ix_sites_category", "category"),
        Index("ix_sites_is_active", "is_active"),
    )
    
    def __repr__(self) -> str:
        return f"<SiteConfig(domain={self.domain}, confidence={self.confidence_score:.2f})>"
    
    def record_success(self) -> None:
        """Record a successful interaction with this site."""
        self.success_count += 1
        self.last_successful_at = datetime.utcnow()
    
    def record_failure(self) -> None:
        """Record a failed interaction with this site."""
        self.failure_count += 1
        self.last_failed_at = datetime.utcnow()
    
    def update_selector(self, path: str, selector: str) -> None:
        """
        Update a specific selector in the selectors JSONB.
        
        Args:
            path: Dot-notation path (e.g., "job_list.job_card")
            selector: New CSS selector value
        """
        keys = path.split(".")
        current = self.selectors
        
        # Navigate to parent
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[keys[-1]] = selector
