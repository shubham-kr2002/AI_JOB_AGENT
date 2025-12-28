#!/usr/bin/env python3
"""
Project JobHunter V3 - Database Initialization Script
Creates tables and seeds the World Model with known job sites.

Usage:
    python -m app.scripts.init_db
    
    Or with options:
    python -m app.scripts.init_db --drop   # Drop and recreate
    python -m app.scripts.init_db --seed   # Only seed World Model
"""

import asyncio
import argparse
import sys
from datetime import datetime

# Add parent to path for imports
sys.path.insert(0, ".")


async def create_tables(drop_first: bool = False) -> None:
    """Create all database tables."""
    from app.db.async_database import async_engine, init_async_db, drop_async_db
    from app.models.base import Base
    
    # Import all models to register them
    from app.models import (
        User, Profile, Task, TaskStep,
        SiteConfig, ExecutionLog,
        JobApplication, LearningHistory
    )
    
    if drop_first:
        print("[DB] Dropping existing tables...")
        await drop_async_db()
    
    print("[DB] Creating tables...")
    await init_async_db()
    print("[DB] ✅ Tables created successfully!")


async def seed_world_model() -> None:
    """Seed the World Model with known job site configurations."""
    from sqlalchemy import select
    from app.db.async_database import get_async_session
    from app.models.world_model import SiteConfig
    
    sites = [
        # =====================================================================
        # LinkedIn
        # =====================================================================
        SiteConfig(
            domain="linkedin.com",
            name="LinkedIn",
            category="job_board",
            login_config={
                "requires_auth": True,
                "login_url": "/login",
                "auth_type": "credentials",
                "requires_2fa": False,
                "session_duration_hours": 168,  # 7 days
                "selectors": {
                    "username_field": "#username",
                    "password_field": "#password",
                    "submit_button": "button[type='submit']"
                }
            },
            selectors={
                "job_list": {
                    "container": ".jobs-search-results-list",
                    "job_card": ".job-card-container",
                    "job_title": ".job-card-list__title",
                    "company_name": ".job-card-container__company-name",
                    "location": ".job-card-container__metadata-item"
                },
                "job_detail": {
                    "apply_button": "button[aria-label='Easy Apply']",
                    "external_apply": "a[data-tracking-control-name='public_jobs_apply-link-offsite']",
                    "job_description": ".jobs-description__content",
                    "save_button": "button[aria-label='Save']"
                },
                "easy_apply": {
                    "modal": ".jobs-easy-apply-modal",
                    "next_button": "button[aria-label='Continue to next step']",
                    "review_button": "button[aria-label='Review your application']",
                    "submit_button": "button[aria-label='Submit application']",
                    "upload_resume": "input[type='file']"
                },
                "pagination": {
                    "next_page": "button[aria-label='View next page']",
                    "page_indicator": ".artdeco-pagination__indicator"
                }
            },
            behavior={
                "rate_limit_ms": 3000,
                "requires_stealth": True,
                "ajax_wait_ms": 2000,
                "scroll_behavior": "lazy_load",
                "human_delays": {
                    "typing_ms": [50, 150],
                    "click_ms": [300, 800]
                },
                "blocked_detection": {
                    "indicators": [".challenge-container", "#captcha-challenge"],
                    "recovery": "wait_and_retry"
                }
            },
            is_active=True
        ),
        
        # =====================================================================
        # Greenhouse
        # =====================================================================
        SiteConfig(
            domain="greenhouse.io",
            name="Greenhouse",
            category="ats",
            login_config={
                "requires_auth": False,
                "auth_type": None
            },
            selectors={
                "application_form": {
                    "container": "#application-form",
                    "submit_button": "#submit_app",
                    "upload_resume": "input[type='file'][name='resume']",
                    "field_mappings": {
                        "first_name": "#first_name",
                        "last_name": "#last_name",
                        "email": "#email",
                        "phone": "#phone",
                        "linkedin": "input[name*='linkedin']",
                        "website": "input[name*='website']"
                    }
                },
                "custom_questions": {
                    "container": ".custom-question",
                    "text_input": "input[type='text'], textarea",
                    "select": "select",
                    "radio": "input[type='radio']",
                    "checkbox": "input[type='checkbox']"
                }
            },
            behavior={
                "rate_limit_ms": 1000,
                "requires_stealth": False,
                "ajax_wait_ms": 500
            },
            is_active=True
        ),
        
        # =====================================================================
        # Lever
        # =====================================================================
        SiteConfig(
            domain="lever.co",
            name="Lever",
            category="ats",
            login_config={
                "requires_auth": False,
                "auth_type": None
            },
            selectors={
                "application_form": {
                    "container": ".application-page",
                    "submit_button": "button[type='submit']",
                    "upload_resume": "input[type='file']",
                    "field_mappings": {
                        "name": "input[name='name']",
                        "email": "input[name='email']",
                        "phone": "input[name='phone']",
                        "linkedin": "input[name='urls[LinkedIn]']",
                        "github": "input[name='urls[GitHub]']",
                        "portfolio": "input[name='urls[Portfolio]']"
                    }
                },
                "custom_questions": {
                    "container": ".application-additional",
                    "text_input": "input, textarea",
                    "select": "select"
                }
            },
            behavior={
                "rate_limit_ms": 1000,
                "requires_stealth": False,
                "ajax_wait_ms": 500
            },
            is_active=True
        ),
        
        # =====================================================================
        # Workday
        # =====================================================================
        SiteConfig(
            domain="workday.com",
            name="Workday",
            category="ats",
            login_config={
                "requires_auth": True,
                "auth_type": "credentials",
                "requires_2fa": False,
                "selectors": {
                    "username_field": "input[data-automation-id='email']",
                    "password_field": "input[data-automation-id='password']",
                    "submit_button": "button[data-automation-id='signInSubmit']"
                }
            },
            selectors={
                "job_list": {
                    "container": "[data-automation-id='jobResults']",
                    "job_card": "[data-automation-id='jobItem']",
                    "job_title": "[data-automation-id='jobTitle']"
                },
                "application_form": {
                    "container": "[data-automation-id='applicationForm']",
                    "submit_button": "[data-automation-id='submit']",
                    "next_button": "[data-automation-id='bottom-navigation-next-button']",
                    "upload_resume": "input[type='file']"
                }
            },
            behavior={
                "rate_limit_ms": 2000,
                "requires_stealth": True,
                "ajax_wait_ms": 2000,
                "blocked_detection": {
                    "indicators": [".challenge-error", "[data-automation-id='error']"],
                    "recovery": "retry_with_delay"
                }
            },
            is_active=True
        ),
        
        # =====================================================================
        # Indeed
        # =====================================================================
        SiteConfig(
            domain="indeed.com",
            name="Indeed",
            category="job_board",
            login_config={
                "requires_auth": True,
                "login_url": "/account/login",
                "auth_type": "credentials",
                "selectors": {
                    "username_field": "#ifl-InputFormField-3",
                    "password_field": "#ifl-InputFormField-7",
                    "submit_button": "button[type='submit']"
                }
            },
            selectors={
                "job_list": {
                    "container": "#mosaic-jobResults",
                    "job_card": ".job_seen_beacon",
                    "job_title": ".jobTitle",
                    "company_name": ".companyName",
                    "location": ".companyLocation"
                },
                "job_detail": {
                    "apply_button": "#indeedApplyButton, button[data-indeed-apply-button]",
                    "job_description": "#jobDescriptionText"
                },
                "pagination": {
                    "next_page": "a[data-testid='pagination-page-next']"
                }
            },
            behavior={
                "rate_limit_ms": 2500,
                "requires_stealth": True,
                "ajax_wait_ms": 1500,
                "blocked_detection": {
                    "indicators": ["#challenge-container", ".challenge-form"],
                    "recovery": "wait_and_retry"
                }
            },
            is_active=True
        ),
    ]
    
    async with get_async_session() as session:
        for site in sites:
            # Check if already exists
            result = await session.execute(
                select(SiteConfig).where(SiteConfig.domain == site.domain)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                print(f"  [SKIP] {site.domain} already exists")
            else:
                session.add(site)
                print(f"  [ADD] {site.domain}")
        
        await session.commit()
    
    print("[DB] ✅ World Model seeded successfully!")


async def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    print("=" * 60)
    print("Project JobHunter V3 - Database Initialization")
    print("=" * 60)
    
    if args.seed:
        # Only seed, don't create tables
        await seed_world_model()
    else:
        # Create tables (optionally drop first)
        await create_tables(drop_first=args.drop)
        
        # Seed World Model
        print("\n[DB] Seeding World Model...")
        await seed_world_model()
    
    print("\n" + "=" * 60)
    print("✅ Database initialization complete!")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Initialize JobHunter V3 database"
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop existing tables before creating"
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Only seed World Model (tables must exist)"
    )
    
    args = parser.parse_args()
    asyncio.run(main(args))
