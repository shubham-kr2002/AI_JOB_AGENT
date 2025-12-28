"""
Project JobHunter V3 - World Model Service
Provides access to learned site configurations and selectors.

Reference: BackendTechnicalDesign.md Section 3B (The World Model)

The World Model stores:
- Domain-specific CSS selectors that have worked before
- Login configurations and authentication flows
- Rate limiting and anti-detection settings
"""

from typing import Optional, Dict, Any
from urllib.parse import urlparse
import json


class WorldModelService:
    """
    Service for accessing and updating the World Model.
    
    The World Model is a growing knowledge base of what works
    for each job site. It gets smarter with every successful interaction.
    
    Currently stubbed - will integrate with PostgreSQL in production.
    """
    
    # In-memory cache of site configurations (stub)
    _site_cache: Dict[str, Dict[str, Any]] = {}
    
    # Default selectors for common job sites (bootstrap data)
    DEFAULT_CONFIGS = {
        "linkedin.com": {
            "name": "LinkedIn",
            "login_config": {
                "requires_auth": True,
                "login_url": "https://www.linkedin.com/login",
                "selectors": {
                    "username_field": "#username",
                    "password_field": "#password",
                    "submit_button": "button[type='submit']",
                }
            },
            "selectors": {
                "job_list": {
                    "container": ".jobs-search-results-list",
                    "job_card": ".job-card-container",
                    "job_title": ".job-card-list__title",
                    "company_name": ".job-card-container__company-name",
                },
                "job_detail": {
                    "apply_button": "button[aria-label='Easy Apply']",
                    "external_apply": ".jobs-apply-button--top-card",
                    "job_description": ".jobs-description__content",
                },
                "easy_apply": {
                    "modal": ".jobs-easy-apply-modal",
                    "next_button": "button[aria-label='Continue to next step']",
                    "submit_button": "button[aria-label='Submit application']",
                    "upload_resume": "input[type='file']",
                },
            },
            "behavior": {
                "rate_limit_ms": 3000,
                "requires_stealth": True,
                "human_delays": {"min": 500, "max": 2000},
            }
        },
        "greenhouse.io": {
            "name": "Greenhouse",
            "login_config": {
                "requires_auth": False,
            },
            "selectors": {
                "application_form": {
                    "container": "#application-form",
                    "submit_button": "#submit_app",
                    "first_name": "#first_name",
                    "last_name": "#last_name",
                    "email": "#email",
                    "phone": "#phone",
                    "resume_upload": "input[type='file'][name='resume']",
                },
            },
            "behavior": {
                "rate_limit_ms": 1000,
                "requires_stealth": False,
            }
        },
        "lever.co": {
            "name": "Lever",
            "login_config": {
                "requires_auth": False,
            },
            "selectors": {
                "application_form": {
                    "container": ".application-page",
                    "submit_button": "button[type='submit']",
                    "name": "input[name='name']",
                    "email": "input[name='email']",
                    "phone": "input[name='phone']",
                    "resume_upload": "input[type='file']",
                    "linkedin": "input[name='urls[LinkedIn]']",
                },
            },
            "behavior": {
                "rate_limit_ms": 1000,
                "requires_stealth": False,
            }
        },
        "workday.com": {
            "name": "Workday",
            "login_config": {
                "requires_auth": True,
                "selectors": {
                    "username_field": "input[data-automation-id='email']",
                    "password_field": "input[data-automation-id='password']",
                    "submit_button": "button[data-automation-id='signInSubmit']",
                }
            },
            "selectors": {
                "job_detail": {
                    "apply_button": "[data-automation-id='jobPostingApplyButton']",
                },
                "application_form": {
                    "next_button": "[data-automation-id='bottom-navigation-next-button']",
                    "submit_button": "[data-automation-id='submit']",
                },
            },
            "behavior": {
                "rate_limit_ms": 2000,
                "requires_stealth": True,
            }
        },
    }
    
    def __init__(self):
        """Initialize the World Model service."""
        # Load default configs into cache
        self._site_cache = dict(self.DEFAULT_CONFIGS)
    
    def get_domain_from_url(self, url: str) -> str:
        """Extract the root domain from a URL."""
        parsed = urlparse(url)
        hostname = parsed.hostname or ""
        
        # Handle subdomains (e.g., jobs.lever.co -> lever.co)
        parts = hostname.split(".")
        if len(parts) >= 2:
            return ".".join(parts[-2:])
        return hostname
    
    def get_site_config(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get the full configuration for a site.
        
        Args:
            url: The current page URL
            
        Returns:
            Site configuration dict or None if unknown
        """
        domain = self.get_domain_from_url(url)
        return self._site_cache.get(domain)
    
    def get_selector(self, url: str, selector_path: str) -> Optional[str]:
        """
        Get a specific selector for a site using dot notation.
        
        Args:
            url: The current page URL
            selector_path: Dot-notation path (e.g., "job_detail.apply_button")
            
        Returns:
            CSS selector string or None if not found
        """
        config = self.get_site_config(url)
        if not config:
            return None
        
        selectors = config.get("selectors", {})
        
        # Navigate the path
        keys = selector_path.split(".")
        current = selectors
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None
        
        return current if isinstance(current, str) else None
    
    def get_behavior(self, url: str) -> Dict[str, Any]:
        """
        Get behavior settings for a site.
        
        Args:
            url: The current page URL
            
        Returns:
            Behavior dict with rate limits, stealth settings, etc.
        """
        config = self.get_site_config(url)
        if config:
            return config.get("behavior", {})
        
        # Default behavior for unknown sites
        return {
            "rate_limit_ms": 2000,
            "requires_stealth": True,
            "human_delays": {"min": 300, "max": 1500},
        }
    
    def requires_stealth(self, url: str) -> bool:
        """Check if a site requires stealth mode."""
        behavior = self.get_behavior(url)
        return behavior.get("requires_stealth", True)
    
    def get_login_config(self, url: str) -> Optional[Dict[str, Any]]:
        """Get login configuration for a site."""
        config = self.get_site_config(url)
        if config:
            return config.get("login_config")
        return None
    
    def update_selector(self, url: str, selector_path: str, new_selector: str) -> None:
        """
        Update a selector in the World Model after successful use.
        
        This is how the system learns - when a new selector works,
        we save it for future use.
        
        Args:
            url: The current page URL
            selector_path: Dot-notation path
            new_selector: The working CSS selector
        """
        domain = self.get_domain_from_url(url)
        
        if domain not in self._site_cache:
            self._site_cache[domain] = {
                "name": domain,
                "selectors": {},
                "behavior": {"rate_limit_ms": 2000, "requires_stealth": True},
            }
        
        # Navigate and update
        keys = selector_path.split(".")
        selectors = self._site_cache[domain].setdefault("selectors", {})
        
        # Build nested structure if needed
        current = selectors
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        
        # Set the value
        current[keys[-1]] = new_selector
        
        print(f"[WorldModel] Updated {domain} selector: {selector_path} = {new_selector}")
    
    def record_success(self, url: str) -> None:
        """Record a successful interaction with a site."""
        domain = self.get_domain_from_url(url)
        # TODO: Persist to PostgreSQL
        print(f"[WorldModel] Recorded success for {domain}")
    
    def record_failure(self, url: str, error: str) -> None:
        """Record a failed interaction with a site."""
        domain = self.get_domain_from_url(url)
        # TODO: Persist to PostgreSQL
        print(f"[WorldModel] Recorded failure for {domain}: {error}")
