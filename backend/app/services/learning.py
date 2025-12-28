"""
Project JobHunter V3 - Learning Service (The Self-Improvement Engine)
Implements Section 4 of agentflow.md: The Learning Loop

This service captures successful interactions and updates the World Model
so the agent becomes smarter over time.

Key Responsibilities:
1. Capture successful CSS selectors during execution
2. UPSERT selector data into SiteConfig (Postgres)
3. Track workflow patterns for future recall
4. Build the competitive "Moat" through accumulated knowledge
"""

import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse
from dataclasses import dataclass, field

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.async_database import get_async_session
from app.models.world_model import SiteConfig
from app.core.config import get_settings

settings = get_settings()


@dataclass
class SelectorCapture:
    """Represents a successfully used selector."""
    selector_path: str  # e.g., "job_search.apply_button"
    css_selector: str   # e.g., "button.jobs-apply-button"
    action: str         # e.g., "click", "type"
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class WorkflowCapture:
    """Represents a successful workflow sequence."""
    domain: str
    steps: List[Dict[str, Any]]
    total_duration_ms: int
    success: bool = True
    timestamp: datetime = field(default_factory=datetime.utcnow)


class LearningService:
    """
    The Learning Engine - Captures and persists successful patterns.
    
    This is the core of the "Moat" building strategy:
    - Every successful selector gets saved
    - Every successful workflow gets embedded
    - Next time we encounter the same site, we're faster
    
    Reference: agentflow.md Section 4
    """
    
    def __init__(self):
        self._pending_selectors: Dict[str, List[SelectorCapture]] = {}
        self._pending_workflows: List[WorkflowCapture] = []
    
    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract root domain from URL."""
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            # Remove 'www.' prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return url
    
    def capture_selector(
        self,
        url: str,
        selector_path: str,
        css_selector: str,
        action: str,
    ) -> None:
        """
        Capture a successful selector for later persistence.
        
        Called by BrowserAgent after each successful action.
        
        Args:
            url: The URL where the selector worked
            selector_path: Dot-notation path (e.g., "job_search.apply_button")
            css_selector: The actual CSS selector that worked
            action: The action type (click, type, etc.)
        """
        domain = self.extract_domain(url)
        
        if domain not in self._pending_selectors:
            self._pending_selectors[domain] = []
        
        capture = SelectorCapture(
            selector_path=selector_path,
            css_selector=css_selector,
            action=action,
        )
        
        self._pending_selectors[domain].append(capture)
        print(f"[LearningService] Captured selector: {domain} -> {selector_path} = {css_selector}")
    
    def capture_workflow(
        self,
        url: str,
        steps: List[Dict[str, Any]],
        total_duration_ms: int,
    ) -> None:
        """
        Capture a successful workflow for later embedding.
        
        Args:
            url: The starting URL of the workflow
            steps: List of step data that was executed
            total_duration_ms: Total time taken
        """
        domain = self.extract_domain(url)
        
        workflow = WorkflowCapture(
            domain=domain,
            steps=steps,
            total_duration_ms=total_duration_ms,
        )
        
        self._pending_workflows.append(workflow)
        print(f"[LearningService] Captured workflow: {domain} ({len(steps)} steps)")
    
    async def flush_to_database(self) -> Dict[str, int]:
        """
        Persist all pending captures to the database.
        
        Returns:
            Dict with counts of persisted items
        """
        selectors_updated = 0
        workflows_saved = 0
        
        # Persist selectors
        for domain, captures in self._pending_selectors.items():
            if captures:
                successful_selectors = {
                    c.selector_path: c.css_selector
                    for c in captures
                    if c.success
                }
                if successful_selectors:
                    await update_world_model(domain, successful_selectors)
                    selectors_updated += len(successful_selectors)
        
        # Clear pending
        self._pending_selectors.clear()
        
        # TODO: Persist workflows to vector memory
        workflows_saved = len(self._pending_workflows)
        self._pending_workflows.clear()
        
        return {
            "selectors_updated": selectors_updated,
            "workflows_saved": workflows_saved,
        }
    
    def get_pending_count(self) -> Dict[str, int]:
        """Get count of pending items."""
        selector_count = sum(len(v) for v in self._pending_selectors.values())
        return {
            "pending_selectors": selector_count,
            "pending_workflows": len(self._pending_workflows),
        }


async def update_world_model(
    domain: str,
    successful_selectors: Dict[str, str],
    login_config: Optional[Dict[str, Any]] = None,
    behavior_config: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    UPSERT site configuration into the World Model.
    
    This is the core learning function that makes the agent smarter:
    - If domain exists: Merge new selectors with existing ones
    - If domain is new: Create new SiteConfig entry
    
    Args:
        domain: The site domain (e.g., "linkedin.com")
        successful_selectors: Dict of selector_path -> css_selector
            e.g., {"job_search.apply_button": "button.jobs-apply-button"}
        login_config: Optional login configuration to update
        behavior_config: Optional behavior settings to update
    
    Returns:
        True if update was successful
    
    Reference: agentflow.md Section 4 - World Model Update
    """
    async with get_async_session() as session:
        try:
            # Check if domain exists
            result = await session.execute(
                select(SiteConfig).where(SiteConfig.domain == domain)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # ===============================================================
                # UPDATE: Merge new selectors with existing
                # ===============================================================
                current_selectors = existing.selectors or {}
                
                # Deep merge selectors using dot notation
                updated_selectors = _deep_merge_selectors(
                    current_selectors,
                    successful_selectors
                )
                
                # Build update dict
                update_data = {
                    "selectors": updated_selectors,
                    "updated_at": datetime.utcnow(),
                }
                
                # Optionally update login config
                if login_config:
                    current_login = existing.login_config or {}
                    current_login.update(login_config)
                    update_data["login_config"] = current_login
                
                # Optionally update behavior
                if behavior_config:
                    current_behavior = existing.behavior or {}
                    current_behavior.update(behavior_config)
                    update_data["behavior"] = current_behavior
                
                # Increment success count
                update_data["success_count"] = (existing.success_count or 0) + 1
                update_data["last_successful_at"] = datetime.utcnow()
                
                # Execute update
                await session.execute(
                    update(SiteConfig)
                    .where(SiteConfig.domain == domain)
                    .values(**update_data)
                )
                
                print(f"[LearningService] Updated {domain}: +{len(successful_selectors)} selectors")
                
            else:
                # ===============================================================
                # INSERT: Create new site config
                # ===============================================================
                new_config = SiteConfig(
                    domain=domain,
                    name=_generate_site_name(domain),
                    category=_infer_category(domain),
                    login_config=login_config or {},
                    selectors=_expand_selectors(successful_selectors),
                    behavior=behavior_config or _default_behavior(),
                    is_active=True,
                    success_count=1,
                    failure_count=0,
                    last_successful_at=datetime.utcnow(),
                )
                
                session.add(new_config)
                print(f"[LearningService] Created {domain}: {len(successful_selectors)} selectors")
            
            await session.commit()
            return True
            
        except Exception as e:
            print(f"[LearningService] Error updating {domain}: {e}")
            await session.rollback()
            return False


def _deep_merge_selectors(
    existing: Dict[str, Any],
    new_selectors: Dict[str, str],
) -> Dict[str, Any]:
    """
    Deep merge new selectors into existing structure.
    
    Handles dot-notation paths like "job_search.apply_button"
    and merges them into nested dicts.
    
    Args:
        existing: Current selectors dict (possibly nested)
        new_selectors: New selectors with dot-notation paths
    
    Returns:
        Merged selectors dict
    """
    result = dict(existing)  # Shallow copy
    
    for path, selector in new_selectors.items():
        parts = path.split(".")
        
        if len(parts) == 1:
            # Simple key
            result[path] = selector
        else:
            # Nested path - navigate and set
            current = result
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                elif not isinstance(current[part], dict):
                    current[part] = {"_value": current[part]}
                current = current[part]
            
            # Set the final value
            current[parts[-1]] = selector
    
    return result


def _expand_selectors(selectors: Dict[str, str]) -> Dict[str, Any]:
    """
    Expand flat dot-notation selectors into nested structure.
    
    Args:
        selectors: {"job_search.apply_button": "..."}
    
    Returns:
        {"job_search": {"apply_button": "..."}}
    """
    return _deep_merge_selectors({}, selectors)


def _generate_site_name(domain: str) -> str:
    """Generate a human-readable name from domain."""
    # Remove TLD and capitalize
    name = domain.split(".")[0]
    return name.replace("-", " ").replace("_", " ").title()


def _infer_category(domain: str) -> str:
    """Infer site category from domain name."""
    domain_lower = domain.lower()
    
    # ATS providers
    ats_domains = ["greenhouse.io", "lever.co", "workday.com", "icims.com", 
                   "taleo.net", "smartrecruiters.com", "ashbyhq.com"]
    if any(ats in domain_lower for ats in ats_domains):
        return "ats"
    
    # Job boards
    job_boards = ["linkedin.com", "indeed.com", "glassdoor.com", "monster.com",
                  "ziprecruiter.com", "dice.com", "angel.co", "wellfound.com"]
    if any(jb in domain_lower for jb in job_boards):
        return "job_board"
    
    # Aggregators
    aggregators = ["jobs.google.com", "ycombinator.com"]
    if any(agg in domain_lower for agg in aggregators):
        return "aggregator"
    
    # Default to company career page
    return "company_career"


def _default_behavior() -> Dict[str, Any]:
    """Generate default behavior configuration."""
    return {
        "requires_stealth": True,
        "rate_limit": {
            "requests_per_minute": 10,
            "delay_between_actions_ms": {"min": 500, "max": 2000}
        },
        "human_delays": {
            "min": 300,
            "max": 1500
        },
        "scroll_behavior": "human_like",
        "click_behavior": "natural"
    }


async def record_failure(
    domain: str,
    error_message: str,
    selector_path: Optional[str] = None,
) -> None:
    """
    Record a failure for a domain.
    
    This helps identify problematic sites and selectors.
    
    Args:
        domain: The site domain
        error_message: What went wrong
        selector_path: Which selector failed (if applicable)
    """
    async with get_async_session() as session:
        try:
            result = await session.execute(
                select(SiteConfig).where(SiteConfig.domain == domain)
            )
            existing = result.scalar_one_or_none()
            
            if existing:
                # Increment failure count
                await session.execute(
                    update(SiteConfig)
                    .where(SiteConfig.domain == domain)
                    .values(
                        failure_count=(existing.failure_count or 0) + 1,
                        last_failed_at=datetime.utcnow(),
                        notes=error_message[:500],  # Store error in notes
                        updated_at=datetime.utcnow(),
                    )
                )
                await session.commit()
                
        except Exception as e:
            print(f"[LearningService] Error recording failure: {e}")


async def get_site_stats(domain: str) -> Optional[Dict[str, Any]]:
    """
    Get learning statistics for a domain.
    
    Returns:
        Dict with success/failure counts and selector info
    """
    async with get_async_session() as session:
        result = await session.execute(
            select(SiteConfig).where(SiteConfig.domain == domain)
        )
        config = result.scalar_one_or_none()
        
        if not config:
            return None
        
        return {
            "domain": config.domain,
            "name": config.name,
            "category": config.category,
            "selector_count": _count_selectors(config.selectors),
            "success_count": config.success_count or 0,
            "failure_count": config.failure_count or 0,
            "success_rate": _calculate_success_rate(
                config.success_count or 0,
                config.failure_count or 0
            ),
            "last_successful_at": config.last_successful_at,
            "last_failed_at": config.last_failed_at,
            "notes": config.notes,
        }


def _count_selectors(selectors: Dict[str, Any], count: int = 0) -> int:
    """Recursively count selectors in nested dict."""
    if not isinstance(selectors, dict):
        return count
    
    for key, value in selectors.items():
        if isinstance(value, dict):
            count = _count_selectors(value, count)
        else:
            count += 1
    
    return count


def _calculate_success_rate(successes: int, failures: int) -> float:
    """Calculate success rate as percentage."""
    total = successes + failures
    if total == 0:
        return 0.0
    return round((successes / total) * 100, 2)


# =============================================================================
# Singleton Instance (for convenience)
# =============================================================================
_learning_service: Optional[LearningService] = None


def get_learning_service() -> LearningService:
    """Get or create the singleton LearningService instance."""
    global _learning_service
    if _learning_service is None:
        _learning_service = LearningService()
    return _learning_service
