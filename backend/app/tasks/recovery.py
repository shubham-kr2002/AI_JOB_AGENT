"""
Project JobHunter V3 - Recovery Agent (The Healer)
Implements error handling, retry strategies, and recovery patterns.

The Recovery Agent handles runtime failures by:
1. Analyzing failure causes and context
2. Selecting appropriate recovery strategies
3. Executing fixes (close popups, wait, retry)
4. Escalating to human when automated recovery fails

Reference: 
- Architecture.md: "The Immune System (Recovery & Validation)"
- agentflow.md: Step C (Recovery)
"""

import asyncio
import random
from typing import Dict, Any, List, Optional, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta

from playwright.async_api import Page, TimeoutError as PlaywrightTimeout

from app.core.celery_app import celery_app
from app.core.config import get_settings

settings = get_settings()


class FailureType(str, Enum):
    """Types of failures the Recovery Agent can handle."""
    ELEMENT_NOT_FOUND = "element_not_found"
    CLICK_INTERCEPTED = "click_intercepted"
    TIMEOUT = "timeout"
    NAVIGATION_ERROR = "navigation_error"
    CAPTCHA_DETECTED = "captcha_detected"
    LOGIN_REQUIRED = "login_required"
    RATE_LIMITED = "rate_limited"
    NETWORK_ERROR = "network_error"
    PAGE_CRASH = "page_crash"
    POPUP_BLOCKING = "popup_blocking"
    MODAL_BLOCKING = "modal_blocking"
    IFRAME_CONTEXT = "iframe_context"
    STALE_ELEMENT = "stale_element"
    FORM_VALIDATION = "form_validation"
    TWO_FACTOR_AUTH = "two_factor_auth"
    SESSION_EXPIRED = "session_expired"
    UNKNOWN = "unknown"


class RecoveryAction(str, Enum):
    """Actions the Recovery Agent can take."""
    RETRY = "retry"
    RETRY_WITH_WAIT = "retry_with_wait"
    CLOSE_POPUP = "close_popup"
    CLOSE_MODAL = "close_modal"
    SWITCH_IFRAME = "switch_iframe"
    REFRESH_PAGE = "refresh_page"
    CLEAR_COOKIES = "clear_cookies"
    SCROLL_TO_ELEMENT = "scroll_to_element"
    WAIT_FOR_NETWORK = "wait_for_network"
    HUMAN_INTERVENTION = "human_intervention"
    SKIP_STEP = "skip_step"
    ABORT_TASK = "abort_task"
    ALTERNATIVE_SELECTOR = "alternative_selector"
    SWITCH_TO_VISIBLE = "switch_to_visible"
    EXPONENTIAL_BACKOFF = "exponential_backoff"


@dataclass
class FailureContext:
    """Context information about a failure."""
    failure_type: FailureType
    error_message: str
    selector: Optional[str] = None
    url: Optional[str] = None
    step_name: Optional[str] = None
    attempt_number: int = 1
    max_attempts: int = 3
    timestamp: datetime = field(default_factory=datetime.utcnow)
    page_html_snippet: Optional[str] = None
    screenshot_path: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "failure_type": self.failure_type.value,
            "error_message": self.error_message,
            "selector": self.selector,
            "url": self.url,
            "step_name": self.step_name,
            "attempt_number": self.attempt_number,
            "max_attempts": self.max_attempts,
            "timestamp": self.timestamp.isoformat(),
        }


@dataclass
class RecoveryStrategy:
    """A recovery strategy with actions and parameters."""
    actions: List[RecoveryAction]
    wait_seconds: float = 0
    alternative_selector: Optional[str] = None
    message: str = ""
    requires_human: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "actions": [a.value for a in self.actions],
            "wait_seconds": self.wait_seconds,
            "alternative_selector": self.alternative_selector,
            "message": self.message,
            "requires_human": self.requires_human,
        }


@dataclass
class RecoveryResult:
    """Result of a recovery attempt."""
    success: bool
    action_taken: RecoveryAction
    message: str
    should_retry: bool = True
    new_context: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "action_taken": self.action_taken.value,
            "message": self.message,
            "should_retry": self.should_retry,
            "new_context": self.new_context,
        }


class RecoveryAgent:
    """
    The Recovery Agent - Handles runtime errors and implements recovery strategies.
    
    Uses a strategy pattern to select appropriate recovery actions based on:
    1. Error type classification
    2. Attempt history
    3. Page context
    """
    
    # Popup/Modal close button patterns
    CLOSE_BUTTON_SELECTORS = [
        "button[aria-label*='close' i]",
        "button[aria-label*='dismiss' i]",
        "[class*='close']",
        "[class*='dismiss']",
        ".modal-close",
        ".popup-close",
        "button.close",
        "[data-dismiss='modal']",
        "button[type='button']:has(svg)",
        ".overlay-close",
        "[aria-label='Close']",
        "button:has-text('×')",
        "button:has-text('Close')",
        "button:has-text('No thanks')",
        "button:has-text('Not now')",
        "button:has-text('Maybe later')",
        "button:has-text('Skip')",
    ]
    
    # Cookie consent patterns
    COOKIE_CONSENT_SELECTORS = [
        "button:has-text('Accept')",
        "button:has-text('Accept all')",
        "button:has-text('Accept cookies')",
        "button:has-text('Allow')",
        "button:has-text('Got it')",
        "button:has-text('I agree')",
        "[id*='cookie'] button",
        "[class*='cookie'] button",
        "[id*='consent'] button",
        "[class*='consent'] button",
    ]
    
    # Rate limit indicators
    RATE_LIMIT_PATTERNS = [
        "rate limit",
        "too many requests",
        "slow down",
        "try again later",
        "temporarily blocked",
        "unusual activity",
    ]
    
    # CAPTCHA indicators
    CAPTCHA_PATTERNS = [
        "captcha",
        "recaptcha",
        "hcaptcha",
        "verify you're human",
        "robot",
        "security check",
    ]
    
    # 2FA indicators
    TWO_FACTOR_PATTERNS = [
        "two-factor",
        "2fa",
        "verification code",
        "authentication code",
        "sms code",
        "enter code",
        "we sent a code",
    ]

    def __init__(self, max_retries: int = 3):
        self.max_retries = max_retries
        self.attempt_history: List[FailureContext] = []
    
    def classify_error(self, error: Exception, context: Dict[str, Any] = None) -> FailureType:
        """
        Classify an error into a FailureType.
        
        Args:
            error: The exception that occurred
            context: Optional context (page HTML, URL, etc.)
            
        Returns:
            Classified FailureType
        """
        error_str = str(error).lower()
        error_name = type(error).__name__.lower()
        
        # Check for specific Playwright errors
        if "timeout" in error_str or "timeout" in error_name:
            return FailureType.TIMEOUT
        
        if "click intercepted" in error_str or "element click intercepted" in error_str:
            return FailureType.CLICK_INTERCEPTED
        
        if "element not found" in error_str or "no element" in error_str:
            return FailureType.ELEMENT_NOT_FOUND
        
        if "navigation" in error_str or "net::" in error_str:
            return FailureType.NAVIGATION_ERROR
        
        if "stale" in error_str:
            return FailureType.STALE_ELEMENT
        
        if "network" in error_str or "connection" in error_str:
            return FailureType.NETWORK_ERROR
        
        if "crash" in error_str or "target closed" in error_str:
            return FailureType.PAGE_CRASH
        
        # Check page content for specific issues
        if context:
            html_lower = context.get("html", "").lower()
            
            if any(p in html_lower for p in self.CAPTCHA_PATTERNS):
                return FailureType.CAPTCHA_DETECTED
            
            if any(p in html_lower for p in self.RATE_LIMIT_PATTERNS):
                return FailureType.RATE_LIMITED
            
            if any(p in html_lower for p in self.TWO_FACTOR_PATTERNS):
                return FailureType.TWO_FACTOR_AUTH
            
            if "login" in html_lower and "sign in" in html_lower:
                return FailureType.LOGIN_REQUIRED
        
        return FailureType.UNKNOWN
    
    def select_strategy(self, context: FailureContext) -> RecoveryStrategy:
        """
        Select a recovery strategy based on failure context.
        
        Args:
            context: Information about the failure
            
        Returns:
            RecoveryStrategy with actions to take
        """
        failure_type = context.failure_type
        attempt = context.attempt_number
        
        # Strategy selection based on failure type
        strategies: Dict[FailureType, RecoveryStrategy] = {
            FailureType.CLICK_INTERCEPTED: RecoveryStrategy(
                actions=[RecoveryAction.CLOSE_POPUP, RecoveryAction.CLOSE_MODAL, RecoveryAction.RETRY],
                wait_seconds=1.5,
                message="Element blocked by overlay, attempting to close"
            ),
            
            FailureType.POPUP_BLOCKING: RecoveryStrategy(
                actions=[RecoveryAction.CLOSE_POPUP, RecoveryAction.RETRY],
                wait_seconds=1.0,
                message="Popup detected, closing"
            ),
            
            FailureType.MODAL_BLOCKING: RecoveryStrategy(
                actions=[RecoveryAction.CLOSE_MODAL, RecoveryAction.RETRY],
                wait_seconds=1.0,
                message="Modal detected, closing"
            ),
            
            FailureType.ELEMENT_NOT_FOUND: RecoveryStrategy(
                actions=[RecoveryAction.SCROLL_TO_ELEMENT, RecoveryAction.RETRY_WITH_WAIT, RecoveryAction.ALTERNATIVE_SELECTOR],
                wait_seconds=2.0,
                message="Element not found, scrolling and waiting"
            ),
            
            FailureType.TIMEOUT: RecoveryStrategy(
                actions=[RecoveryAction.WAIT_FOR_NETWORK, RecoveryAction.RETRY_WITH_WAIT],
                wait_seconds=3.0 * attempt,  # Exponential backoff
                message=f"Timeout occurred, waiting {3.0 * attempt}s before retry"
            ),
            
            FailureType.STALE_ELEMENT: RecoveryStrategy(
                actions=[RecoveryAction.REFRESH_PAGE, RecoveryAction.RETRY],
                wait_seconds=2.0,
                message="Stale element, refreshing page"
            ),
            
            FailureType.NETWORK_ERROR: RecoveryStrategy(
                actions=[RecoveryAction.EXPONENTIAL_BACKOFF, RecoveryAction.RETRY],
                wait_seconds=5.0 * attempt,
                message=f"Network error, backing off for {5.0 * attempt}s"
            ),
            
            FailureType.RATE_LIMITED: RecoveryStrategy(
                actions=[RecoveryAction.EXPONENTIAL_BACKOFF],
                wait_seconds=60.0 * attempt,  # Long wait for rate limits
                message=f"Rate limited, waiting {60 * attempt}s"
            ),
            
            FailureType.CAPTCHA_DETECTED: RecoveryStrategy(
                actions=[RecoveryAction.HUMAN_INTERVENTION],
                requires_human=True,
                message="CAPTCHA detected, human intervention required"
            ),
            
            FailureType.TWO_FACTOR_AUTH: RecoveryStrategy(
                actions=[RecoveryAction.HUMAN_INTERVENTION],
                requires_human=True,
                message="2FA required, waiting for human input"
            ),
            
            FailureType.LOGIN_REQUIRED: RecoveryStrategy(
                actions=[RecoveryAction.HUMAN_INTERVENTION],
                requires_human=True,
                message="Login required, please authenticate"
            ),
            
            FailureType.SESSION_EXPIRED: RecoveryStrategy(
                actions=[RecoveryAction.CLEAR_COOKIES, RecoveryAction.REFRESH_PAGE, RecoveryAction.RETRY],
                wait_seconds=2.0,
                message="Session expired, clearing cookies and retrying"
            ),
            
            FailureType.PAGE_CRASH: RecoveryStrategy(
                actions=[RecoveryAction.ABORT_TASK],
                message="Page crashed, aborting task"
            ),
            
            FailureType.UNKNOWN: RecoveryStrategy(
                actions=[RecoveryAction.RETRY_WITH_WAIT],
                wait_seconds=2.0 * attempt,
                message="Unknown error, generic retry"
            ),
        }
        
        # Get strategy or default
        strategy = strategies.get(failure_type, strategies[FailureType.UNKNOWN])
        
        # If max attempts reached, escalate
        if attempt >= context.max_attempts:
            if not strategy.requires_human:
                strategy = RecoveryStrategy(
                    actions=[RecoveryAction.HUMAN_INTERVENTION],
                    requires_human=True,
                    message=f"Max retries ({context.max_attempts}) exceeded, escalating to human"
                )
        
        return strategy
    
    async def execute_recovery(
        self,
        page: Page,
        context: FailureContext,
        strategy: RecoveryStrategy
    ) -> RecoveryResult:
        """
        Execute a recovery strategy on the page.
        
        Args:
            page: Playwright page instance
            context: Failure context
            strategy: Recovery strategy to execute
            
        Returns:
            RecoveryResult
        """
        for action in strategy.actions:
            try:
                result = await self._execute_action(page, action, strategy, context)
                if result.success:
                    return result
            except Exception as e:
                # Continue to next action if this one fails
                continue
        
        # All actions failed
        return RecoveryResult(
            success=False,
            action_taken=strategy.actions[-1] if strategy.actions else RecoveryAction.ABORT_TASK,
            message="All recovery actions failed",
            should_retry=False
        )
    
    async def _execute_action(
        self,
        page: Page,
        action: RecoveryAction,
        strategy: RecoveryStrategy,
        context: FailureContext
    ) -> RecoveryResult:
        """Execute a single recovery action."""
        
        if action == RecoveryAction.CLOSE_POPUP:
            return await self._close_overlay(page, "popup")
        
        elif action == RecoveryAction.CLOSE_MODAL:
            return await self._close_overlay(page, "modal")
        
        elif action == RecoveryAction.RETRY:
            return RecoveryResult(
                success=True,
                action_taken=action,
                message="Ready to retry",
                should_retry=True
            )
        
        elif action == RecoveryAction.RETRY_WITH_WAIT:
            await asyncio.sleep(strategy.wait_seconds)
            return RecoveryResult(
                success=True,
                action_taken=action,
                message=f"Waited {strategy.wait_seconds}s, ready to retry",
                should_retry=True
            )
        
        elif action == RecoveryAction.SCROLL_TO_ELEMENT:
            if context.selector:
                try:
                    await page.evaluate(f'''
                        document.querySelector("{context.selector}")?.scrollIntoView({{
                            behavior: "smooth",
                            block: "center"
                        }})
                    ''')
                    await asyncio.sleep(0.5)
                except:
                    pass
            return RecoveryResult(
                success=True,
                action_taken=action,
                message="Scrolled to element",
                should_retry=True
            )
        
        elif action == RecoveryAction.WAIT_FOR_NETWORK:
            try:
                await page.wait_for_load_state("networkidle", timeout=10000)
            except:
                pass
            return RecoveryResult(
                success=True,
                action_taken=action,
                message="Waited for network idle",
                should_retry=True
            )
        
        elif action == RecoveryAction.REFRESH_PAGE:
            await page.reload(wait_until="domcontentloaded")
            await asyncio.sleep(2.0)
            return RecoveryResult(
                success=True,
                action_taken=action,
                message="Page refreshed",
                should_retry=True
            )
        
        elif action == RecoveryAction.EXPONENTIAL_BACKOFF:
            wait_time = strategy.wait_seconds + random.uniform(0, 2)
            await asyncio.sleep(wait_time)
            return RecoveryResult(
                success=True,
                action_taken=action,
                message=f"Backed off for {wait_time:.1f}s",
                should_retry=True
            )
        
        elif action == RecoveryAction.HUMAN_INTERVENTION:
            return RecoveryResult(
                success=False,
                action_taken=action,
                message=strategy.message,
                should_retry=False,
                new_context={"requires_human": True, "reason": strategy.message}
            )
        
        elif action == RecoveryAction.SKIP_STEP:
            return RecoveryResult(
                success=True,
                action_taken=action,
                message="Step skipped",
                should_retry=False
            )
        
        elif action == RecoveryAction.ABORT_TASK:
            return RecoveryResult(
                success=False,
                action_taken=action,
                message="Task aborted",
                should_retry=False
            )
        
        else:
            return RecoveryResult(
                success=False,
                action_taken=action,
                message=f"Unknown action: {action}",
                should_retry=False
            )
    
    async def _close_overlay(self, page: Page, overlay_type: str) -> RecoveryResult:
        """Attempt to close popup/modal overlays."""
        
        # Try close button selectors
        for selector in self.CLOSE_BUTTON_SELECTORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    await elem.click()
                    await asyncio.sleep(0.5)
                    return RecoveryResult(
                        success=True,
                        action_taken=RecoveryAction.CLOSE_POPUP if overlay_type == "popup" else RecoveryAction.CLOSE_MODAL,
                        message=f"Closed {overlay_type} with selector: {selector}",
                        should_retry=True
                    )
            except:
                continue
        
        # Try cookie consent buttons
        for selector in self.COOKIE_CONSENT_SELECTORS:
            try:
                elem = await page.query_selector(selector)
                if elem and await elem.is_visible():
                    await elem.click()
                    await asyncio.sleep(0.5)
                    return RecoveryResult(
                        success=True,
                        action_taken=RecoveryAction.CLOSE_POPUP,
                        message=f"Accepted cookies with selector: {selector}",
                        should_retry=True
                    )
            except:
                continue
        
        # Try pressing Escape
        try:
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.3)
            return RecoveryResult(
                success=True,
                action_taken=RecoveryAction.CLOSE_POPUP,
                message="Pressed Escape to close overlay",
                should_retry=True
            )
        except:
            pass
        
        # Try clicking backdrop
        try:
            for backdrop_selector in [".modal-backdrop", ".overlay", "[class*='backdrop']"]:
                elem = await page.query_selector(backdrop_selector)
                if elem:
                    # Click at the edge of the backdrop
                    box = await elem.bounding_box()
                    if box:
                        await page.mouse.click(box["x"] + 10, box["y"] + 10)
                        await asyncio.sleep(0.5)
                        return RecoveryResult(
                            success=True,
                            action_taken=RecoveryAction.CLOSE_MODAL,
                            message="Clicked backdrop to close",
                            should_retry=True
                        )
        except:
            pass
        
        return RecoveryResult(
            success=False,
            action_taken=RecoveryAction.CLOSE_POPUP,
            message=f"Could not close {overlay_type}",
            should_retry=True
        )


# =============================================================================
# Celery Tasks
# =============================================================================

@celery_app.task(name="recovery.analyze_failure", bind=True)
def analyze_failure(
    self,
    error_message: str,
    error_type: str,
    context: Dict[str, Any]
) -> dict:
    """
    Analyze a task failure and determine recovery strategy.
    
    Args:
        error_message: The error message
        error_type: Exception type name
        context: Execution context at time of failure
        
    Returns:
        Analysis result with recovery strategy
    """
    agent = RecoveryAgent()
    
    # Create a mock exception for classification
    class MockError(Exception):
        pass
    
    error = MockError(error_message)
    error.__class__.__name__ = error_type
    
    failure_type = agent.classify_error(error, context)
    
    failure_context = FailureContext(
        failure_type=failure_type,
        error_message=error_message,
        selector=context.get("selector"),
        url=context.get("url"),
        step_name=context.get("step_name"),
        attempt_number=context.get("attempt_number", 1),
        max_attempts=context.get("max_attempts", 3),
    )
    
    strategy = agent.select_strategy(failure_context)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "failure_type": failure_type.value,
        "strategy": strategy.to_dict(),
        "requires_human": strategy.requires_human,
    }


@celery_app.task(name="recovery.get_strategy", bind=True)
def get_strategy(
    self,
    failure_type: str,
    attempt_number: int = 1,
    max_attempts: int = 3
) -> dict:
    """
    Get a recovery strategy for a specific failure type.
    
    Args:
        failure_type: Type of failure
        attempt_number: Current attempt number
        max_attempts: Maximum retry attempts
        
    Returns:
        Recovery strategy
    """
    agent = RecoveryAgent()
    
    try:
        ftype = FailureType(failure_type)
    except ValueError:
        ftype = FailureType.UNKNOWN
    
    context = FailureContext(
        failure_type=ftype,
        error_message="",
        attempt_number=attempt_number,
        max_attempts=max_attempts,
    )
    
    strategy = agent.select_strategy(context)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "strategy": strategy.to_dict(),
    }


@celery_app.task(name="recovery.escalate", bind=True)
def escalate(
    self,
    error: Dict[str, Any],
    attempts: List[Dict[str, Any]],
    task_id: str
) -> dict:
    """
    Escalate an unrecoverable error to human intervention.
    
    Args:
        error: Final error information
        attempts: List of previous recovery attempts
        task_id: ID of the task being escalated
        
    Returns:
        Escalation result with intervention request
    """
    return {
        "status": "escalated",
        "task_id": self.request.id,
        "original_task_id": task_id,
        "requires_human_intervention": True,
        "intervention_type": "manual_review",
        "error_summary": error.get("message", "Unknown error"),
        "attempt_count": len(attempts),
        "last_attempt": attempts[-1] if attempts else None,
        "message": "This task requires human intervention. Please review and take action.",
        "actions_available": [
            "retry_task",
            "skip_step",
            "abort_task",
            "provide_input",
        ],
    }


@celery_app.task(name="recovery.retry_with_fix", bind=True)
def retry_with_fix(
    self,
    original_task: Dict[str, Any],
    fix_strategy: Dict[str, Any]
) -> dict:
    """
    Prepare a fixed retry of a failed task.
    
    Args:
        original_task: The original task that failed
        fix_strategy: The strategy to apply for the retry
        
    Returns:
        Modified task ready for retry
    """
    modified_task = original_task.copy()
    
    # Apply fixes based on strategy
    actions = fix_strategy.get("actions", [])
    
    if "alternative_selector" in actions:
        if fix_strategy.get("alternative_selector"):
            modified_task["selector"] = fix_strategy["alternative_selector"]
    
    if "retry_with_wait" in actions:
        modified_task["pre_wait"] = fix_strategy.get("wait_seconds", 2.0)
    
    # Increment attempt counter
    modified_task["attempt_number"] = original_task.get("attempt_number", 0) + 1
    
    return {
        "status": "ready_for_retry",
        "task_id": self.request.id,
        "modified_task": modified_task,
        "fixes_applied": actions,
    }
