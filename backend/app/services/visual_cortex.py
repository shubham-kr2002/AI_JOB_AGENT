"""
Project JobHunter V3 - Visual Cortex Service
Screenshot analysis using GPT-4o-Vision for intelligent page understanding.

The Visual Cortex provides:
1. Screenshot-based element detection
2. Page state analysis (forms, errors, success indicators)
3. Visual confirmation of actions
4. Fallback when selectors fail

Reference: ProductRequirementsDocument.md AIR-01 - Multi-Modal LLM Integration

NOTE: OpenAI API key is OPTIONAL. If not provided, visual analysis will be disabled
and the system will rely on DOM-based selectors only.
"""

import base64
import json
import re
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import logging

# OpenAI is optional - import with fallback
try:
    from openai import AsyncOpenAI, OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    AsyncOpenAI = None
    OpenAI = None

from pydantic import BaseModel

from app.core.config import get_settings
from app.core.celery_app import celery_app

settings = get_settings()
logger = logging.getLogger(__name__)


class PageState(str, Enum):
    """Detected page states."""
    LOGIN_FORM = "login_form"
    JOB_LISTING = "job_listing"
    JOB_DETAIL = "job_detail"
    APPLICATION_FORM = "application_form"
    SUCCESS_PAGE = "success_page"
    ERROR_PAGE = "error_page"
    CAPTCHA = "captcha"
    TWO_FACTOR = "two_factor"
    MODAL_POPUP = "modal_popup"
    COOKIE_BANNER = "cookie_banner"
    LOADING = "loading"
    UNKNOWN = "unknown"


class ElementType(str, Enum):
    """Types of detected elements."""
    BUTTON = "button"
    INPUT_TEXT = "input_text"
    INPUT_EMAIL = "input_email"
    INPUT_PASSWORD = "input_password"
    INPUT_PHONE = "input_phone"
    TEXTAREA = "textarea"
    SELECT = "select"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE_UPLOAD = "file_upload"
    LINK = "link"
    IMAGE = "image"
    ERROR_MESSAGE = "error_message"
    SUCCESS_MESSAGE = "success_message"


@dataclass
class DetectedElement:
    """An element detected in the screenshot."""
    element_type: ElementType
    label: str
    approximate_location: str  # e.g., "top-center", "middle-left"
    suggested_selector: Optional[str]
    confidence: float
    value_if_visible: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "element_type": self.element_type.value,
            "label": self.label,
            "location": self.approximate_location,
            "suggested_selector": self.suggested_selector,
            "confidence": self.confidence,
            "value": self.value_if_visible,
        }


@dataclass
class PageAnalysis:
    """Complete analysis of a page screenshot."""
    state: PageState
    title: str
    description: str
    elements: List[DetectedElement]
    action_suggestions: List[str]
    errors_detected: List[str]
    confidence: float
    raw_analysis: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.value,
            "title": self.title,
            "description": self.description,
            "elements": [e.to_dict() for e in self.elements],
            "action_suggestions": self.action_suggestions,
            "errors_detected": self.errors_detected,
            "confidence": self.confidence,
        }


class VisualCortex:
    """
    Visual understanding service using GPT-4o-Vision.
    
    Analyzes screenshots to:
    1. Understand page context and state
    2. Locate interactive elements
    3. Detect errors and success messages
    4. Suggest next actions
    """
    
    # System prompts for different analysis types
    PAGE_ANALYSIS_PROMPT = """You are an expert at analyzing web page screenshots for a job application automation system.

Analyze the provided screenshot and return a JSON object with the following structure:

{
  "state": "<one of: login_form, job_listing, job_detail, application_form, success_page, error_page, captcha, two_factor, modal_popup, cookie_banner, loading, unknown>",
  "title": "<page title or main heading>",
  "description": "<brief description of what's on the page>",
  "elements": [
    {
      "type": "<button|input_text|input_email|input_password|textarea|select|checkbox|radio|file_upload|link|error_message|success_message>",
      "label": "<visible label or placeholder text>",
      "location": "<top-left|top-center|top-right|middle-left|middle-center|middle-right|bottom-left|bottom-center|bottom-right>",
      "selector_hint": "<CSS selector suggestion based on visible attributes>",
      "confidence": <0.0-1.0>,
      "current_value": "<if a value is visible in the field>"
    }
  ],
  "suggested_actions": ["<action 1>", "<action 2>"],
  "errors": ["<any error messages visible>"],
  "overall_confidence": <0.0-1.0>
}

Focus on:
1. Form fields that need to be filled
2. Buttons that need to be clicked
3. Error messages that indicate problems
4. Success indicators
5. Popups or modals that might block interaction"""

    ELEMENT_FINDER_PROMPT = """You are an expert at locating specific elements in web page screenshots.

I need you to find the element described as: "{element_description}"

Look at the screenshot and return a JSON object:

{
  "found": true/false,
  "location": "<top-left|top-center|top-right|middle-left|middle-center|middle-right|bottom-left|bottom-center|bottom-right>",
  "bounding_box_estimate": {
    "x_percent": <0-100 from left>,
    "y_percent": <0-100 from top>,
    "width_percent": <estimated width>,
    "height_percent": <estimated height>
  },
  "selector_suggestions": [
    "<most likely CSS selector>",
    "<alternative selector>"
  ],
  "confidence": <0.0-1.0>,
  "notes": "<any relevant observations>"
}"""

    ACTION_VERIFICATION_PROMPT = """You are verifying that a browser action was successful.

The action attempted was: "{action_description}"

Look at the screenshot taken AFTER the action and determine:

{
  "success": true/false,
  "evidence": "<what visual evidence supports your conclusion>",
  "new_state": "<description of current page state>",
  "errors_visible": ["<any error messages>"],
  "next_action_suggestion": "<what should happen next>",
  "confidence": <0.0-1.0>
}"""

    def __init__(self):
        """Initialize Visual Cortex. OpenAI is optional - will work without it."""
        self.enabled = False
        self.client = None
        self.sync_client = None
        self.model = "gpt-4o"  # Vision-capable model
        
        # Check if OpenAI is available and configured
        if OPENAI_AVAILABLE and settings.OPENAI_API_KEY and settings.OPENAI_API_KEY != "sk-your-openai-api-key-here":
            try:
                self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
                self.sync_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                self.enabled = True
                logger.info("[VisualCortex] Initialized with OpenAI GPT-4o Vision")
            except Exception as e:
                logger.warning(f"[VisualCortex] Failed to initialize OpenAI: {e}")
                self.enabled = False
        else:
            logger.info("[VisualCortex] OpenAI not configured - visual analysis disabled. System will use DOM selectors only.")
    
    async def analyze_page(
        self,
        screenshot_base64: str,
        context: Optional[str] = None
    ) -> PageAnalysis:
        """
        Analyze a full page screenshot.
        
        Args:
            screenshot_base64: Base64-encoded PNG screenshot
            context: Optional context about what we're looking for
            
        Returns:
            PageAnalysis with detected state, elements, and suggestions
        """
        # Return empty analysis if visual cortex is disabled
        if not self.enabled:
            logger.debug("[VisualCortex] Skipping analysis - not enabled")
            return PageAnalysis(
                state=PageState.UNKNOWN,
                title="Visual Analysis Disabled",
                description="OpenAI API key not configured. Using DOM selectors only.",
                elements=[],
                action_suggestions=["Configure OPENAI_API_KEY for visual analysis"],
                errors_detected=[],
                confidence=0.0,
                raw_analysis="Visual cortex disabled"
            )
        
        prompt = self.PAGE_ANALYSIS_PROMPT
        if context:
            prompt += f"\n\nAdditional context: {context}"
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,
            temperature=0.1,
        )
        
        return self._parse_page_analysis(response.choices[0].message.content)
    
    async def find_element(
        self,
        screenshot_base64: str,
        element_description: str
    ) -> Dict[str, Any]:
        """
        Find a specific element in a screenshot.
        
        Args:
            screenshot_base64: Base64-encoded PNG screenshot
            element_description: Description of the element to find
            
        Returns:
            Element location and selector suggestions
        """
        prompt = self.ELEMENT_FINDER_PROMPT.format(
            element_description=element_description
        )
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        
        return self._parse_json_response(response.choices[0].message.content)
    
    async def verify_action(
        self,
        screenshot_base64: str,
        action_description: str
    ) -> Dict[str, Any]:
        """
        Verify that an action was successful.
        
        Args:
            screenshot_base64: Screenshot taken after the action
            action_description: Description of the action that was attempted
            
        Returns:
            Verification result with success/failure and evidence
        """
        prompt = self.ACTION_VERIFICATION_PROMPT.format(
            action_description=action_description
        )
        
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        
        return self._parse_json_response(response.choices[0].message.content)
    
    async def compare_screenshots(
        self,
        before_base64: str,
        after_base64: str,
        expected_change: str
    ) -> Dict[str, Any]:
        """
        Compare two screenshots to detect changes.
        
        Args:
            before_base64: Screenshot before action
            after_base64: Screenshot after action
            expected_change: What change we expected to see
            
        Returns:
            Comparison result with detected changes
        """
        prompt = f"""Compare these two screenshots (before and after an action).

Expected change: {expected_change}

Return a JSON object:
{{
  "change_detected": true/false,
  "expected_change_occurred": true/false,
  "changes_observed": ["<list of visual changes>"],
  "errors_appeared": ["<any new errors>"],
  "confidence": <0.0-1.0>
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{before_base64}",
                                "detail": "low",
                            },
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{after_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        
        return self._parse_json_response(response.choices[0].message.content)
    
    async def generate_fallback_selector(
        self,
        screenshot_base64: str,
        target_description: str,
        failed_selector: str
    ) -> Dict[str, Any]:
        """
        Generate alternative selectors when the primary one fails.
        
        Args:
            screenshot_base64: Current page screenshot
            target_description: What element we're trying to find
            failed_selector: The selector that didn't work
            
        Returns:
            Alternative selector suggestions
        """
        prompt = f"""A CSS selector failed to find an element. Help me find alternatives.

Target element: {target_description}
Failed selector: {failed_selector}

Look at the screenshot and suggest alternative selectors.

Return JSON:
{{
  "element_visible": true/false,
  "alternative_selectors": [
    {{"selector": "<selector>", "confidence": <0.0-1.0>, "approach": "<xpath|css|text|aria>"}},
  ],
  "element_location": "<approximate screen location>",
  "possible_reasons_for_failure": ["<reason 1>", "<reason 2>"],
  "recommendation": "<best approach to find this element>"
}}"""

        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        
        return self._parse_json_response(response.choices[0].message.content)
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        # Try to find JSON in the response
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Return raw content as error
        return {
            "error": "Failed to parse response",
            "raw_content": content,
        }
    
    def _parse_page_analysis(self, content: str) -> PageAnalysis:
        """Parse page analysis response into PageAnalysis dataclass."""
        data = self._parse_json_response(content)
        
        if "error" in data:
            return PageAnalysis(
                state=PageState.UNKNOWN,
                title="Parse Error",
                description=data.get("raw_content", ""),
                elements=[],
                action_suggestions=[],
                errors_detected=[],
                confidence=0.0,
                raw_analysis=content,
            )
        
        # Parse state
        try:
            state = PageState(data.get("state", "unknown"))
        except ValueError:
            state = PageState.UNKNOWN
        
        # Parse elements
        elements = []
        for elem_data in data.get("elements", []):
            try:
                elem_type = ElementType(elem_data.get("type", "button"))
            except ValueError:
                elem_type = ElementType.BUTTON
            
            elements.append(DetectedElement(
                element_type=elem_type,
                label=elem_data.get("label", ""),
                approximate_location=elem_data.get("location", "middle-center"),
                suggested_selector=elem_data.get("selector_hint"),
                confidence=elem_data.get("confidence", 0.5),
                value_if_visible=elem_data.get("current_value"),
            ))
        
        return PageAnalysis(
            state=state,
            title=data.get("title", ""),
            description=data.get("description", ""),
            elements=elements,
            action_suggestions=data.get("suggested_actions", []),
            errors_detected=data.get("errors", []),
            confidence=data.get("overall_confidence", 0.5),
            raw_analysis=content,
        )
    
    # =========================================================================
    # Synchronous methods for Celery tasks
    # =========================================================================
    
    def sync_analyze_page(
        self,
        screenshot_base64: str,
        context: Optional[str] = None
    ) -> PageAnalysis:
        """Synchronous version of analyze_page for Celery tasks."""
        prompt = self.PAGE_ANALYSIS_PROMPT
        if context:
            prompt += f"\n\nAdditional context: {context}"
        
        response = self.sync_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=2000,
            temperature=0.1,
        )
        
        return self._parse_page_analysis(response.choices[0].message.content)
    
    def sync_find_element(
        self,
        screenshot_base64: str,
        element_description: str
    ) -> Dict[str, Any]:
        """Synchronous version of find_element for Celery tasks."""
        prompt = self.ELEMENT_FINDER_PROMPT.format(
            element_description=element_description
        )
        
        response = self.sync_client.chat.completions.create(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{screenshot_base64}",
                                "detail": "high",
                            },
                        },
                    ],
                },
            ],
            max_tokens=1000,
            temperature=0.1,
        )
        
        return self._parse_json_response(response.choices[0].message.content)


# =============================================================================
# Celery Tasks
# =============================================================================

@celery_app.task(name="visual.analyze_page", bind=True)
def analyze_page_task(
    self,
    screenshot_base64: str,
    context: Optional[str] = None
) -> dict:
    """
    Analyze a page screenshot.
    
    Args:
        screenshot_base64: Base64-encoded PNG screenshot
        context: Optional context about what we're looking for
        
    Returns:
        Page analysis result
    """
    cortex = VisualCortex()
    analysis = cortex.sync_analyze_page(screenshot_base64, context)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "analysis": analysis.to_dict(),
    }


@celery_app.task(name="visual.find_element", bind=True)
def find_element_task(
    self,
    screenshot_base64: str,
    element_description: str
) -> dict:
    """
    Find a specific element in a screenshot.
    
    Args:
        screenshot_base64: Base64-encoded PNG screenshot
        element_description: Description of the element to find
        
    Returns:
        Element location and selector suggestions
    """
    cortex = VisualCortex()
    result = cortex.sync_find_element(screenshot_base64, element_description)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "result": result,
    }


@celery_app.task(name="visual.verify_action", bind=True)
def verify_action_task(
    self,
    screenshot_base64: str,
    action_description: str
) -> dict:
    """
    Verify that an action was successful.
    
    Args:
        screenshot_base64: Screenshot taken after the action
        action_description: Description of the action that was attempted
        
    Returns:
        Verification result
    """
    cortex = VisualCortex()
    
    prompt = cortex.ACTION_VERIFICATION_PROMPT.format(
        action_description=action_description
    )
    
    response = cortex.sync_client.chat.completions.create(
        model=cortex.model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=1000,
        temperature=0.1,
    )
    
    result = cortex._parse_json_response(response.choices[0].message.content)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "result": result,
    }


@celery_app.task(name="visual.get_fallback_selector", bind=True)
def get_fallback_selector_task(
    self,
    screenshot_base64: str,
    target_description: str,
    failed_selector: str
) -> dict:
    """
    Generate alternative selectors when primary selector fails.
    
    Args:
        screenshot_base64: Current page screenshot
        target_description: What element we're trying to find
        failed_selector: The selector that didn't work
        
    Returns:
        Alternative selector suggestions
    """
    cortex = VisualCortex()
    
    prompt = f"""A CSS selector failed to find an element. Help me find alternatives.

Target element: {target_description}
Failed selector: {failed_selector}

Look at the screenshot and suggest alternative selectors.

Return JSON:
{{
  "element_visible": true/false,
  "alternative_selectors": [
    {{"selector": "<selector>", "confidence": <0.0-1.0>, "approach": "<xpath|css|text|aria>"}},
  ],
  "element_location": "<approximate screen location>",
  "possible_reasons_for_failure": ["<reason 1>", "<reason 2>"],
  "recommendation": "<best approach to find this element>"
}}"""

    response = cortex.sync_client.chat.completions.create(
        model=cortex.model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{screenshot_base64}",
                            "detail": "high",
                        },
                    },
                ],
            },
        ],
        max_tokens=1000,
        temperature=0.1,
    )
    
    result = cortex._parse_json_response(response.choices[0].message.content)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "result": result,
    }
