"""
Project JobHunter V3 - Site Selectors Seed Data
Seeds the World Model with job board configurations.

Supported Sites:
- LinkedIn Jobs
- Greenhouse (ATS)
- Lever (ATS)  
- Workday (ATS)
- Indeed
- Glassdoor

Reference: BTD.md FR-05 - Site-Specific Configurations
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.models.site_config import SiteConfig


# =============================================================================
# Site Selector Configurations
# =============================================================================

SITE_CONFIGS = [
    # =========================================================================
    # LINKEDIN
    # =========================================================================
    {
        "site_name": "linkedin",
        "domain": "linkedin.com",
        "base_url": "https://www.linkedin.com",
        "login_url": "https://www.linkedin.com/login",
        "search_url_template": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}",
        "selectors": {
            # Login
            "login": {
                "username_field": "#username",
                "password_field": "#password",
                "submit_button": "button[type='submit']",
                "logged_in_indicator": ".global-nav__me-photo",
            },
            # Job Search
            "search": {
                "search_input": "input[aria-label='Search by title, skill, or company']",
                "location_input": "input[aria-label='City, state, or zip code']",
                "search_button": "button.jobs-search-box__submit-button",
                "job_card": ".jobs-search-results__list-item",
                "job_title": ".job-card-list__title",
                "company_name": ".job-card-container__company-name",
                "location": ".job-card-container__metadata-item",
                "posted_date": ".job-card-container__listed-time",
            },
            # Job Details
            "job_detail": {
                "apply_button": ".jobs-apply-button",
                "easy_apply_button": ".jobs-apply-button--top-card",
                "save_button": ".jobs-save-button",
                "job_description": ".jobs-description__content",
                "company_link": ".job-details-jobs-unified-top-card__company-name a",
            },
            # Easy Apply Modal
            "easy_apply": {
                "modal": ".jobs-easy-apply-modal",
                "next_button": "button[aria-label='Continue to next step']",
                "review_button": "button[aria-label='Review your application']",
                "submit_button": "button[aria-label='Submit application']",
                "close_button": "button[aria-label='Dismiss']",
                # Form fields
                "phone_input": "input[name='phoneNumber']",
                "email_input": "input[name='email']",
                "resume_upload": "input[type='file']",
                "experience_years": "input[name='years-experience-']",
                "work_auth": "select[name='workAuthorization']",
            },
            # Filters
            "filters": {
                "date_posted": "button[aria-label*='Date posted']",
                "experience_level": "button[aria-label*='Experience level']",
                "job_type": "button[aria-label*='Job type']",
                "remote": "button[aria-label*='Remote']",
                "easy_apply_filter": "button[aria-label*='Easy Apply']",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (80, 180),
            "click_delay_ms": (100, 300),
            "page_load_wait_ms": 2000,
            "human_pause_probability": 0.3,
        },
        "rate_limits": {
            "requests_per_minute": 30,
            "applications_per_day": 100,
            "search_delay_seconds": 3,
        },
        "is_active": True,
    },
    
    # =========================================================================
    # GREENHOUSE
    # =========================================================================
    {
        "site_name": "greenhouse",
        "domain": "greenhouse.io",
        "base_url": "https://boards.greenhouse.io",
        "selectors": {
            # Job Board
            "job_board": {
                "job_list": ".opening",
                "job_title": ".opening a",
                "department": ".department",
                "location": ".location",
            },
            # Application Form
            "application": {
                "form": "#application_form",
                "first_name": "#first_name",
                "last_name": "#last_name",
                "email": "#email",
                "phone": "#phone",
                "resume_upload": "#resume",
                "cover_letter_upload": "#cover_letter",
                "linkedin_url": "input[name*='linkedin']",
                "portfolio_url": "input[name*='portfolio']",
                "submit_button": "#submit_app",
                # Custom questions
                "custom_question": ".field",
                "text_input": "input[type='text']",
                "textarea": "textarea",
                "select": "select",
                "radio": "input[type='radio']",
                "checkbox": "input[type='checkbox']",
            },
            # EEOC (voluntary demographic)
            "eeoc": {
                "gender": "#job_application_gender",
                "race": "#job_application_race",
                "veteran_status": "#job_application_veteran_status",
                "disability_status": "#job_application_disability_status",
            },
            # Success indicators
            "success": {
                "confirmation": ".confirmation-page",
                "thank_you": "h1:has-text('Thank you')",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (60, 150),
            "click_delay_ms": (80, 200),
            "page_load_wait_ms": 1500,
        },
        "rate_limits": {
            "requests_per_minute": 60,
        },
        "is_active": True,
    },
    
    # =========================================================================
    # LEVER
    # =========================================================================
    {
        "site_name": "lever",
        "domain": "lever.co",
        "base_url": "https://jobs.lever.co",
        "selectors": {
            # Job Board
            "job_board": {
                "job_list": ".posting",
                "job_title": ".posting-title h5",
                "location": ".posting-categories .location",
                "team": ".posting-categories .team",
                "commitment": ".posting-categories .commitment",
                "apply_link": ".posting-apply",
            },
            # Job Detail
            "job_detail": {
                "job_title": ".posting-headline h2",
                "description": ".posting-page-content",
                "requirements": ".posting-requirements",
                "apply_button": "a.postings-btn",
            },
            # Application Form
            "application": {
                "form": ".application-form",
                "name": "input[name='name']",
                "email": "input[name='email']",
                "phone": "input[name='phone']",
                "current_company": "input[name='org']",
                "linkedin_url": "input[name='urls[LinkedIn]']",
                "twitter_url": "input[name='urls[Twitter]']",
                "github_url": "input[name='urls[GitHub]']",
                "portfolio_url": "input[name='urls[Portfolio]']",
                "other_url": "input[name='urls[Other]']",
                "resume_upload": "input[name='resume']",
                "cover_letter": "textarea[name='comments']",
                "submit_button": "button[type='submit']",
                # Additional info
                "additional_info": ".additional-information textarea",
            },
            # Custom questions
            "questions": {
                "container": ".custom-questions",
                "text_input": ".text-input input",
                "textarea": ".textarea-input textarea",
                "dropdown": ".dropdown-input select",
                "checkbox": ".checkbox-input input",
            },
            # Success
            "success": {
                "confirmation": ".application-confirmation",
                "message": "h1:has-text('Thanks')",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (70, 160),
            "click_delay_ms": (90, 220),
            "page_load_wait_ms": 1800,
        },
        "rate_limits": {
            "requests_per_minute": 50,
        },
        "is_active": True,
    },
    
    # =========================================================================
    # WORKDAY
    # =========================================================================
    {
        "site_name": "workday",
        "domain": "myworkdayjobs.com",
        "base_url": "https://www.myworkdayjobs.com",
        "selectors": {
            # Search
            "search": {
                "search_input": "input[data-automation-id='searchBox']",
                "search_button": "button[data-automation-id='searchButton']",
                "job_list": "[data-automation-id='jobResults']",
                "job_card": "[data-automation-id='jobItem']",
            },
            # Job Detail
            "job_detail": {
                "title": "[data-automation-id='jobPostingTitle']",
                "description": "[data-automation-id='jobPostingDescription']",
                "apply_button": "button[data-automation-id='applyButton']",
            },
            # Application - Multi Step
            "application": {
                # Account/Sign In
                "create_account_link": "button:has-text('Create Account')",
                "sign_in_link": "button:has-text('Sign In')",
                "email_input": "input[data-automation-id='email']",
                "password_input": "input[data-automation-id='password']",
                "create_password": "input[data-automation-id='createPassword']",
                "verify_password": "input[data-automation-id='verifyPassword']",
                
                # Resume upload
                "resume_section": "[data-automation-id='resumeSection']",
                "resume_upload": "input[data-automation-id='file-upload-input-ref']",
                "parse_resume": "button:has-text('Autofill')",
                
                # Personal Info
                "first_name": "input[data-automation-id='legalNameSection_firstName']",
                "last_name": "input[data-automation-id='legalNameSection_lastName']",
                "address_line1": "input[data-automation-id='addressSection_addressLine1']",
                "city": "input[data-automation-id='addressSection_city']",
                "state": "select[data-automation-id='addressSection_countryRegion']",
                "postal_code": "input[data-automation-id='addressSection_postalCode']",
                "phone_type": "select[data-automation-id='phone-device-type']",
                "phone_number": "input[data-automation-id='phone-number']",
                
                # Experience
                "add_experience": "button:has-text('Add Work Experience')",
                "job_title": "input[data-automation-id='jobTitle']",
                "company": "input[data-automation-id='company']",
                "start_date": "input[data-automation-id='startDate']",
                "end_date": "input[data-automation-id='endDate']",
                "current_job": "input[data-automation-id='currentlyWorkHere']",
                
                # Education
                "add_education": "button:has-text('Add Education')",
                "school": "input[data-automation-id='school']",
                "degree": "select[data-automation-id='degree']",
                "field_of_study": "input[data-automation-id='fieldOfStudy']",
                "gpa": "input[data-automation-id='gpa']",
                
                # Navigation
                "continue_button": "button[data-automation-id='bottom-navigation-next-button']",
                "previous_button": "button[data-automation-id='bottom-navigation-previous-button']",
                "submit_button": "button[data-automation-id='bottom-navigation-next-button']:has-text('Submit')",
            },
            # Custom questions
            "questions": {
                "radio_yes": "input[data-automation-id='radio'][value='1']",
                "radio_no": "input[data-automation-id='radio'][value='0']",
                "text_input": "input[data-automation-id='textInput']",
                "dropdown": "select[data-automation-id='select']",
            },
            # Success
            "success": {
                "confirmation": "[data-automation-id='confirmationMessage']",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (100, 200),
            "click_delay_ms": (150, 350),
            "page_load_wait_ms": 3000,
            "form_field_delay_ms": 500,
        },
        "rate_limits": {
            "requests_per_minute": 20,
        },
        "is_active": True,
    },
    
    # =========================================================================
    # INDEED
    # =========================================================================
    {
        "site_name": "indeed",
        "domain": "indeed.com",
        "base_url": "https://www.indeed.com",
        "login_url": "https://secure.indeed.com/auth",
        "search_url_template": "https://www.indeed.com/jobs?q={query}&l={location}",
        "selectors": {
            # Search
            "search": {
                "what_input": "#text-input-what",
                "where_input": "#text-input-where",
                "search_button": "button.yosegi-InlineWhatWhere-primaryButton",
                "job_card": ".job_seen_beacon",
                "job_title": ".jobTitle span",
                "company_name": ".companyName",
                "location": ".companyLocation",
                "salary": ".salary-snippet-container",
            },
            # Job Detail
            "job_detail": {
                "apply_button": "#indeedApplyButton",
                "apply_now_button": ".jobsearch-IndeedApplyButton-newDesign",
                "description": "#jobDescriptionText",
            },
            # Application
            "application": {
                "name": "input[name='applicant.name']",
                "email": "input[name='applicant.email']",
                "phone": "input[name='applicant.phoneNumber']",
                "resume_upload": "input[type='file']",
                "continue_button": "button:has-text('Continue')",
                "submit_button": "button:has-text('Submit')",
            },
            # Filters
            "filters": {
                "date_posted": "#filter-dateposted",
                "job_type": "#filter-jobtype",
                "salary": "#filter-salary",
                "remote": "#filter-remotejob",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (70, 160),
            "click_delay_ms": (100, 250),
            "page_load_wait_ms": 2500,
        },
        "rate_limits": {
            "requests_per_minute": 25,
            "applications_per_day": 50,
        },
        "is_active": True,
    },
    
    # =========================================================================
    # GLASSDOOR
    # =========================================================================
    {
        "site_name": "glassdoor",
        "domain": "glassdoor.com",
        "base_url": "https://www.glassdoor.com",
        "search_url_template": "https://www.glassdoor.com/Job/jobs.htm?sc.keyword={query}&locT=C&locId={location_id}",
        "selectors": {
            # Search
            "search": {
                "keyword_input": "#sc.keyword",
                "location_input": "#sc.location",
                "search_button": "button.SearchStyles__searchButton",
                "job_card": ".react-job-listing",
                "job_title": ".jobLink span",
                "company_name": ".job-search-key-l2wrz0",
                "location": ".job-search-key-iii3vg",
                "salary": ".salary-estimate",
            },
            # Job Detail
            "job_detail": {
                "apply_button": "button[data-test='applyButton']",
                "save_button": "button[data-test='saveButton']",
                "description": ".jobDescriptionContent",
                "company_rating": ".job-search-key-1cn0py",
            },
            # Modal handling
            "modals": {
                "close_button": "button.modal-close",
                "sign_up_modal": "[data-test='modal']",
                "dismiss": "button:has-text('✕')",
            },
        },
        "stealth_settings": {
            "typing_speed_ms": (80, 170),
            "click_delay_ms": (120, 280),
            "page_load_wait_ms": 2000,
        },
        "rate_limits": {
            "requests_per_minute": 20,
        },
        "is_active": True,
    },
]


def seed_sites(db: Session) -> None:
    """Seed site configurations into database."""
    for config in SITE_CONFIGS:
        existing = db.query(SiteConfig).filter(
            SiteConfig.site_name == config["site_name"]
        ).first()
        
        if existing:
            # Update existing
            for key, value in config.items():
                setattr(existing, key, value)
            print(f"Updated: {config['site_name']}")
        else:
            # Create new
            site_config = SiteConfig(**config)
            db.add(site_config)
            print(f"Created: {config['site_name']}")
    
    db.commit()
    print(f"\nSeeded {len(SITE_CONFIGS)} site configurations.")


def main():
    """Run the seed script."""
    print("=" * 60)
    print("Project JobHunter V3 - Site Configuration Seeder")
    print("=" * 60)
    
    db = SessionLocal()
    try:
        seed_sites(db)
    finally:
        db.close()
    
    print("\nDone!")


if __name__ == "__main__":
    main()
