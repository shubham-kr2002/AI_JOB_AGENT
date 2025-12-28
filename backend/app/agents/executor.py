"""
Project JobHunter V3 - Browser Agent (The Executor)
Implements FR-07, FR-08, FR-09 from PRD and Phase 2 from BackendTechnicalDesign.

The Executor is the "soldier" that carries out browser automation tasks.
It uses Playwright with stealth capabilities to navigate job sites,
fill forms, and submit applications while evading bot detection.

Features:
- FR-07: Headless & Headed modes
- FR-08: Stealth browsing (fingerprint spoofing)
- FR-09: Self-healing selectors (DOM analysis fallback)
- FR-10: World Model integration for learned selectors
"""

import asyncio
import random
import re
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError,
)

from app.agents.world_model_service import WorldModelService
from app.services.learning import LearningService, get_learning_service
from app.core.config import get_settings

settings = get_settings()


class ActionType(str, Enum):
    """Types of browser actions the executor can perform."""
    NAVIGATE = "navigate"
    CLICK = "click"
    TYPE = "type"
    SELECT = "select"
    UPLOAD = "upload"
    SCREENSHOT = "screenshot"
    WAIT = "wait"
    SCROLL = "scroll"
    HOVER = "hover"
    EXTRACT = "extract"


@dataclass
class StepResult:
    """Result of executing a browser step."""
    success: bool
    action: str
    selector: Optional[str] = None
    selector_path: Optional[str] = None  # For learning: the logical path
    selector_source: Optional[str] = None  # "world_model", "provided", "healed"
    data: Optional[Dict[str, Any]] = None
    screenshot_path: Optional[str] = None
    error: Optional[str] = None
    duration_ms: int = 0


class BrowserAgent:
    """
    The Executor Agent - Browser automation with stealth capabilities.
    
    This agent:
    1. Launches browsers with anti-detection measures
    2. Executes steps (navigate, click, type, etc.)
    3. Uses World Model for known selectors
    4. Falls back to LLM-based selector discovery when needed
    5. Learns from successful interactions
    
    Reference: BackendTechnicalDesign.md Phase 2 (The Executor)
    """
    
    # Stealth user agents (rotated randomly)
    USER_AGENTS = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    ]
    
    # Viewport sizes that look human
    VIEWPORTS = [
        {"width": 1920, "height": 1080},
        {"width": 1536, "height": 864},
        {"width": 1440, "height": 900},
        {"width": 1366, "height": 768},
        {"width": 1280, "height": 720},
    ]
    
    def __init__(
        self,
        headless: bool = True,
        world_model: Optional[WorldModelService] = None,
        learning_service: Optional[LearningService] = None,
    ):
        """
        Initialize the Browser Agent.
        
        Args:
            headless: Whether to run in headless mode (FR-07)
            world_model: World Model service for selector lookup
            learning_service: Learning service for capturing successful selectors
        """
        self.headless = headless
        self.world_model = world_model or WorldModelService()
        self.learning_service = learning_service or get_learning_service()
        
        # Playwright instances
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None
        
        # State tracking
        self._current_url: str = ""
        self._screenshots_dir: str = "./screenshots"
        
        # Learning: Track successful steps for workflow capture
        self._executed_steps: List[Dict[str, Any]] = []
        self._workflow_start_time: Optional[float] = None
    
    async def launch_browser(self) -> Page:
        """
        Launch a browser with stealth configuration.
        
        Implements FR-08: Stealth Browsing
        - Fingerprint spoofing
        - Canvas noise injection
        - WebGL vendor masking
        - Randomized user agents
        
        Returns:
            Playwright Page object
        """
        self._playwright = await async_playwright().start()
        
        # Select random user agent and viewport
        user_agent = random.choice(self.USER_AGENTS)
        viewport = random.choice(self.VIEWPORTS)
        
        # Determine if we need stealth based on headless mode
        # For high-security sites, use headed mode
        headless = self.headless if settings.PLAYWRIGHT_HEADLESS else False
        
        # Launch with stealth arguments
        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--disable-background-networking",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-breakpad",
            "--disable-component-extensions-with-background-pages",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-features=TranslateUI",
            "--disable-hang-monitor",
            "--disable-ipc-flooding-protection",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-renderer-backgrounding",
            "--disable-sync",
            "--enable-features=NetworkService,NetworkServiceInProcess",
            "--force-color-profile=srgb",
            "--metrics-recording-only",
            "--no-first-run",
            "--password-store=basic",
            "--use-mock-keychain",
            "--export-tagged-pdf",
        ]
        
        # Add headless-specific args
        if headless:
            launch_args.extend([
                "--headless=new",  # New headless mode (harder to detect)
            ])
        
        self._browser = await self._playwright.chromium.launch(
            headless=headless,
            args=launch_args,
            slow_mo=settings.PLAYWRIGHT_SLOW_MO,
        )
        
        # Create context with stealth settings
        self._context = await self._browser.new_context(
            user_agent=user_agent,
            viewport=viewport,
            locale="en-US",
            timezone_id="America/New_York",
            geolocation={"latitude": 40.7128, "longitude": -74.0060},  # NYC
            permissions=["geolocation"],
            color_scheme="light",
            device_scale_factor=1,
            is_mobile=False,
            has_touch=False,
            java_script_enabled=True,
            bypass_csp=False,
            ignore_https_errors=False,
        )
        
        # Inject stealth scripts before any page loads
        await self._context.add_init_script(self._get_stealth_script())
        
        # Create page
        self._page = await self._context.new_page()
        
        # Set default timeout
        self._page.set_default_timeout(30000)  # 30 seconds
        
        print(f"[BrowserAgent] Launched browser (headless={headless})")
        print(f"[BrowserAgent] User-Agent: {user_agent[:50]}...")
        print(f"[BrowserAgent] Viewport: {viewport['width']}x{viewport['height']}")
        
        return self._page
    
    def _get_stealth_script(self) -> str:
        """
        Get JavaScript to inject for stealth mode.
        
        This script masks automation indicators that sites check for:
        - navigator.webdriver
        - Chrome runtime
        - Permissions
        - Plugin count
        """
        return """
        // Remove webdriver flag
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
        
        // Mock chrome runtime
        window.chrome = {
            runtime: {},
            loadTimes: function() {},
            csi: function() {},
            app: {}
        };
        
        // Mock permissions
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
        
        // Add plugins (most real browsers have these)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ]
        });
        
        // Mock languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-US', 'en']
        });
        
        // Add subtle randomness to canvas fingerprint
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function(type) {
            if (type === 'image/png' && this.width > 16 && this.height > 16) {
                const context = this.getContext('2d');
                const imageData = context.getImageData(0, 0, this.width, this.height);
                // Add noise to a few random pixels
                for (let i = 0; i < 10; i++) {
                    const idx = Math.floor(Math.random() * imageData.data.length / 4) * 4;
                    imageData.data[idx] = imageData.data[idx] ^ 1;
                }
                context.putImageData(imageData, 0, 0);
            }
            return originalToDataURL.apply(this, arguments);
        };
        
        // Mock WebGL vendor/renderer
        const getParameter = WebGLRenderingContext.prototype.getParameter;
        WebGLRenderingContext.prototype.getParameter = function(parameter) {
            if (parameter === 37445) return 'Intel Inc.';  // UNMASKED_VENDOR_WEBGL
            if (parameter === 37446) return 'Intel Iris OpenGL Engine';  // UNMASKED_RENDERER_WEBGL
            return getParameter.call(this, parameter);
        };
        """
    
    async def execute_step(self, step_data: Dict[str, Any]) -> StepResult:
        """
        Execute a single step based on the action type.
        
        Implements FR-09: Self-Healing Selectors
        - First tries World Model selectors
        - Falls back to provided selector
        - Can use LLM to find new selectors if both fail
        
        Args:
            step_data: Step configuration with:
                - action: ActionType (navigate, click, type, etc.)
                - selector: CSS selector (optional, uses World Model first)
                - value: Value for type/select actions
                - url: URL for navigate action
                - wait_for: Wait condition after action
                
        Returns:
            StepResult with success status and data
        """
        if not self._page:
            return StepResult(
                success=False,
                action="unknown",
                error="Browser not launched. Call launch_browser() first."
            )
        
        action = step_data.get("action", "").lower()
        
        # Add human-like delay before action
        await self._human_delay()
        
        import time
        start_time = time.time()
        
        try:
            # Route to appropriate handler
            if action == ActionType.NAVIGATE:
                result = await self._handle_navigate(step_data)
            elif action == ActionType.CLICK:
                result = await self._handle_click(step_data)
            elif action == ActionType.TYPE:
                result = await self._handle_type(step_data)
            elif action == ActionType.SELECT:
                result = await self._handle_select(step_data)
            elif action == ActionType.UPLOAD:
                result = await self._handle_upload(step_data)
            elif action == ActionType.SCREENSHOT:
                result = await self._handle_screenshot(step_data)
            elif action == ActionType.WAIT:
                result = await self._handle_wait(step_data)
            elif action == ActionType.SCROLL:
                result = await self._handle_scroll(step_data)
            elif action == ActionType.HOVER:
                result = await self._handle_hover(step_data)
            elif action == ActionType.EXTRACT:
                result = await self._handle_extract(step_data)
            else:
                result = StepResult(
                    success=False,
                    action=action,
                    error=f"Unknown action type: {action}"
                )
            
            # Record duration
            result.duration_ms = int((time.time() - start_time) * 1000)
            
            # =========================================================
            # LEARNING LOOP: Capture successful selectors
            # Reference: agentflow.md Section 4
            # =========================================================
            if result.success:
                self.world_model.record_success(self._current_url)
                
                # Capture selector for learning if it was successful
                if result.selector and result.selector_path:
                    self.learning_service.capture_selector(
                        url=self._current_url,
                        selector_path=result.selector_path,
                        css_selector=result.selector,
                        action=action,
                    )
                
                # Track step for workflow capture
                self._executed_steps.append({
                    "action": action,
                    "selector": result.selector,
                    "selector_path": result.selector_path,
                    "duration_ms": result.duration_ms,
                    "url": self._current_url,
                })
            else:
                self.world_model.record_failure(self._current_url, result.error or "Unknown error")
            
            return result
            
        except PlaywrightTimeout as e:
            return StepResult(
                success=False,
                action=action,
                error=f"Timeout: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except PlaywrightError as e:
            return StepResult(
                success=False,
                action=action,
                error=f"Browser error: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
        except Exception as e:
            return StepResult(
                success=False,
                action=action,
                error=f"Unexpected error: {str(e)}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    async def _resolve_selector(
        self,
        provided_selector: Optional[str],
        selector_path: Optional[str] = None,
    ) -> Tuple[str, str]:
        """
        Resolve the best selector to use.
        
        Priority:
        1. World Model selector (if selector_path provided)
        2. Provided selector
        3. LLM-discovered selector (TODO)
        
        Returns:
            Tuple of (selector, source) where source is "world_model", "provided", or "llm"
        """
        # Try World Model first
        if selector_path:
            world_selector = self.world_model.get_selector(self._current_url, selector_path)
            if world_selector:
                return world_selector, "world_model"
        
        # Fall back to provided selector
        if provided_selector:
            return provided_selector, "provided"
        
        # TODO: LLM-based selector discovery
        # This would capture the DOM and ask an LLM to find the element
        
        raise ValueError("No selector available")
    
    async def _handle_navigate(self, step_data: Dict[str, Any]) -> StepResult:
        """Handle navigation to a URL."""
        url = step_data.get("url")
        if not url:
            return StepResult(success=False, action="navigate", error="No URL provided")
        
        wait_until = step_data.get("wait_until", "domcontentloaded")
        
        response = await self._page.goto(url, wait_until=wait_until)
        self._current_url = self._page.url
        
        # Check for blocked/captcha pages
        if await self._is_blocked():
            return StepResult(
                success=False,
                action="navigate",
                error="Bot detection triggered",
                data={"url": url, "final_url": self._current_url}
            )
        
        return StepResult(
            success=True,
            action="navigate",
            data={
                "url": url,
                "final_url": self._current_url,
                "status": response.status if response else None
            }
        )
    
    async def _handle_click(self, step_data: Dict[str, Any]) -> StepResult:
        """Handle clicking an element."""
        selector_path = step_data.get("selector_path")
        provided_selector = step_data.get("selector")
        
        try:
            selector, source = await self._resolve_selector(provided_selector, selector_path)
        except ValueError as e:
            return StepResult(success=False, action="click", error=str(e))
        
        # Wait for element and click with human-like behavior
        try:
            element = await self._page.wait_for_selector(selector, state="visible", timeout=10000)
            if not element:
                # Try self-healing: look for similar elements
                healed_selector = await self._self_heal_selector(step_data)
                if not healed_selector:
                    return StepResult(success=False, action="click", error=f"Element not found: {selector}")
                selector = healed_selector
                source = "healed"
                element = await self._page.wait_for_selector(selector, state="visible", timeout=5000)
            
            # Human-like click (with slight offset)
            await element.click(
                delay=random.randint(50, 150),  # Human-like click duration
                position={"x": random.randint(-3, 3), "y": random.randint(-3, 3)}  # Slight offset
            )
            
            # Update World Model if we found a working selector
            if source != "world_model" and selector_path:
                self.world_model.update_selector(self._current_url, selector_path, selector)
            
            return StepResult(
                success=True,
                action="click",
                selector=selector,
                selector_path=selector_path,
                selector_source=source,
                data={"source": source}
            )
            
        except PlaywrightTimeout:
            return StepResult(
                success=False,
                action="click",
                selector=selector,
                error=f"Element not visible after timeout: {selector}"
            )
    
    async def _handle_type(self, step_data: Dict[str, Any]) -> StepResult:
        """Handle typing text into an input field."""
        selector_path = step_data.get("selector_path")
        provided_selector = step_data.get("selector")
        value = step_data.get("value", "")
        clear_first = step_data.get("clear_first", True)
        
        try:
            selector, source = await self._resolve_selector(provided_selector, selector_path)
        except ValueError as e:
            return StepResult(success=False, action="type", error=str(e))
        
        try:
            element = await self._page.wait_for_selector(selector, state="visible", timeout=10000)
            if not element:
                return StepResult(success=False, action="type", error=f"Element not found: {selector}")
            
            # Clear existing content if needed
            if clear_first:
                await element.click(click_count=3)  # Select all
                await self._page.keyboard.press("Backspace")
            
            # Type with human-like delays
            await element.type(
                value,
                delay=random.randint(30, 100)  # ms between keystrokes
            )
            
            # Update World Model if we found a working selector
            if source != "world_model" and selector_path:
                self.world_model.update_selector(self._current_url, selector_path, selector)
            
            return StepResult(
                success=True,
                action="type",
                selector=selector,
                selector_path=selector_path,
                selector_source=source,
                data={"value_length": len(value), "source": source}
            )
            
        except PlaywrightTimeout:
            return StepResult(
                success=False,
                action="type",
                selector=selector,
                error=f"Input element not visible: {selector}"
            )
    
    async def _handle_select(self, step_data: Dict[str, Any]) -> StepResult:
        """Handle selecting an option from a dropdown."""
        selector = step_data.get("selector")
        value = step_data.get("value")
        
        if not selector:
            return StepResult(success=False, action="select", error="No selector provided")
        
        try:
            await self._page.select_option(selector, value)
            return StepResult(
                success=True,
                action="select",
                selector=selector,
                data={"value": value}
            )
        except Exception as e:
            return StepResult(
                success=False,
                action="select",
                selector=selector,
                error=str(e)
            )
    
    async def _handle_upload(self, step_data: Dict[str, Any]) -> StepResult:
        """Handle file upload."""
        selector = step_data.get("selector")
        file_path = step_data.get("file_path")
        
        if not selector or not file_path:
            return StepResult(success=False, action="upload", error="Missing selector or file_path")
        
        try:
            await self._page.set_input_files(selector, file_path)
            return StepResult(
                success=True,
                action="upload",
                selector=selector,
                data={"file": file_path}
            )
        except Exception as e:
            return StepResult(
                success=False,
                action="upload",
                selector=selector,
                error=str(e)
            )
    
    async def _handle_screenshot(self, step_data: Dict[str, Any]) -> StepResult:
        """Capture a screenshot."""
        path = step_data.get("path", f"{self._screenshots_dir}/screenshot_{random.randint(1000, 9999)}.png")
        full_page = step_data.get("full_page", False)
        
        try:
            await self._page.screenshot(path=path, full_page=full_page)
            return StepResult(
                success=True,
                action="screenshot",
                screenshot_path=path
            )
        except Exception as e:
            return StepResult(
                success=False,
                action="screenshot",
                error=str(e)
            )
    
    async def _handle_wait(self, step_data: Dict[str, Any]) -> StepResult:
        """Wait for a condition or fixed time."""
        wait_for = step_data.get("wait_for")
        timeout = step_data.get("timeout", 5000)
        
        if wait_for == "navigation":
            await self._page.wait_for_load_state("networkidle", timeout=timeout)
        elif wait_for == "selector":
            selector = step_data.get("selector")
            await self._page.wait_for_selector(selector, timeout=timeout)
        elif isinstance(wait_for, (int, float)):
            await asyncio.sleep(wait_for / 1000)  # Convert ms to seconds
        else:
            # Default: small random wait
            await asyncio.sleep(random.uniform(0.5, 1.5))
        
        return StepResult(success=True, action="wait", data={"wait_for": wait_for})
    
    async def _handle_scroll(self, step_data: Dict[str, Any]) -> StepResult:
        """Scroll the page."""
        direction = step_data.get("direction", "down")
        amount = step_data.get("amount", 500)
        
        if direction == "down":
            await self._page.evaluate(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            await self._page.evaluate(f"window.scrollBy(0, -{amount})")
        elif direction == "bottom":
            await self._page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        elif direction == "top":
            await self._page.evaluate("window.scrollTo(0, 0)")
        
        return StepResult(success=True, action="scroll", data={"direction": direction})
    
    async def _handle_hover(self, step_data: Dict[str, Any]) -> StepResult:
        """Hover over an element."""
        selector = step_data.get("selector")
        if not selector:
            return StepResult(success=False, action="hover", error="No selector provided")
        
        try:
            await self._page.hover(selector)
            return StepResult(success=True, action="hover", selector=selector)
        except Exception as e:
            return StepResult(success=False, action="hover", selector=selector, error=str(e))
    
    async def _handle_extract(self, step_data: Dict[str, Any]) -> StepResult:
        """Extract data from the page."""
        selector = step_data.get("selector")
        attribute = step_data.get("attribute", "textContent")
        multiple = step_data.get("multiple", False)
        
        if not selector:
            return StepResult(success=False, action="extract", error="No selector provided")
        
        try:
            if multiple:
                elements = await self._page.query_selector_all(selector)
                data = []
                for el in elements:
                    if attribute == "textContent":
                        data.append(await el.text_content())
                    else:
                        data.append(await el.get_attribute(attribute))
            else:
                element = await self._page.query_selector(selector)
                if element:
                    if attribute == "textContent":
                        data = await element.text_content()
                    else:
                        data = await element.get_attribute(attribute)
                else:
                    data = None
            
            return StepResult(
                success=True,
                action="extract",
                selector=selector,
                data={"extracted": data}
            )
        except Exception as e:
            return StepResult(
                success=False,
                action="extract",
                selector=selector,
                error=str(e)
            )
    
    async def _human_delay(self) -> None:
        """Add a human-like random delay between actions."""
        behavior = self.world_model.get_behavior(self._current_url)
        delays = behavior.get("human_delays", {"min": 300, "max": 1500})
        
        delay_ms = random.randint(delays.get("min", 300), delays.get("max", 1500))
        await asyncio.sleep(delay_ms / 1000)
    
    async def _is_blocked(self) -> bool:
        """Check if we hit a bot detection or captcha page."""
        # Common indicators of being blocked
        block_indicators = [
            "captcha",
            "challenge",
            "blocked",
            "access denied",
            "please verify",
            "are you a robot",
            "unusual traffic",
        ]
        
        try:
            page_text = await self._page.text_content("body") or ""
            page_text = page_text.lower()
            
            for indicator in block_indicators:
                if indicator in page_text:
                    return True
            
            # Check for common captcha elements
            captcha_selectors = [
                "[data-sitekey]",  # reCAPTCHA
                ".g-recaptcha",
                "#captcha",
                ".challenge-container",
                "iframe[src*='captcha']",
            ]
            
            for selector in captcha_selectors:
                element = await self._page.query_selector(selector)
                if element:
                    return True
                    
        except Exception:
            pass
        
        return False
    
    async def _self_heal_selector(self, step_data: Dict[str, Any]) -> Optional[str]:
        """
        Attempt to find a working selector when the primary one fails.
        
        Implements FR-09: Self-Healing Selectors
        
        Strategy:
        1. Try variations of the selector (ID, class, aria-label)
        2. Look for semantic elements (button, a, input)
        3. Use LLM to analyze DOM (TODO)
        """
        target_text = step_data.get("target_text", "")
        element_type = step_data.get("element_type", "")
        
        # Try finding by text content
        if target_text:
            selectors_to_try = [
                f"text={target_text}",
                f"button:has-text('{target_text}')",
                f"a:has-text('{target_text}')",
                f"[aria-label='{target_text}']",
                f"[title='{target_text}']",
            ]
            
            for selector in selectors_to_try:
                try:
                    element = await self._page.query_selector(selector)
                    if element and await element.is_visible():
                        print(f"[BrowserAgent] Self-healed selector: {selector}")
                        return selector
                except Exception:
                    continue
        
        # TODO: LLM-based selector discovery
        # This would capture a DOM snapshot and ask an LLM to find the element
        
        return None
    
    async def get_page_content(self) -> str:
        """Get the current page HTML content."""
        if self._page:
            return await self._page.content()
        return ""
    
    async def get_page_url(self) -> str:
        """Get the current page URL."""
        if self._page:
            return self._page.url
        return ""
    
    async def finalize_learning(self) -> Dict[str, Any]:
        """
        Finalize the learning loop by persisting captured data.
        
        This should be called at the end of a successful workflow
        to save all learned selectors to the database.
        
        Reference: agentflow.md Section 4 - The Learning Loop
        
        Returns:
            Dict with learning statistics
        """
        import time
        
        # Capture the complete workflow
        if self._executed_steps and self._workflow_start_time:
            total_duration = int((time.time() - self._workflow_start_time) * 1000)
            self.learning_service.capture_workflow(
                url=self._current_url,
                steps=self._executed_steps,
                total_duration_ms=total_duration,
            )
        
        # Flush all captured data to database
        result = await self.learning_service.flush_to_database()
        
        print(f"[BrowserAgent] Learning finalized: {result}")
        
        # Reset tracking
        self._executed_steps = []
        self._workflow_start_time = None
        
        return result
    
    def start_workflow_tracking(self) -> None:
        """Start tracking steps for workflow learning."""
        import time
        self._workflow_start_time = time.time()
        self._executed_steps = []
        print("[BrowserAgent] Workflow tracking started")
    
    def get_execution_summary(self) -> Dict[str, Any]:
        """Get a summary of executed steps."""
        return {
            "total_steps": len(self._executed_steps),
            "steps": self._executed_steps,
            "pending_learning": self.learning_service.get_pending_count(),
        }
    
    async def close(self) -> None:
        """Close the browser and cleanup resources."""
        # Finalize any pending learning before closing
        if self._executed_steps:
            await self.finalize_learning()
        
        if self._page:
            await self._page.close()
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None
        
        print("[BrowserAgent] Browser closed")
    
    async def __aenter__(self):
        """Async context manager entry."""
        await self.launch_browser()
        self.start_workflow_tracking()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
