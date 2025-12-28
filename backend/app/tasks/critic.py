"""
Project JobHunter V3 - Critic Agent (The Auditor)
Implements AIR-02: Adversarial validation of outputs

The Critic Agent is dedicated to finding mistakes in the Executor's work
BEFORE submission. It acts as an adversarial validator that:
1. Compares filled form values against resume facts
2. Detects hallucinations (invented skills, wrong dates, etc.)
3. Validates submission success by analyzing page state
4. Classifies errors for recovery strategy selection

Reference: BackendTechnicalDesign.md Phase 3 (The Critic)
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

from app.core.celery_app import celery_app
from app.core.config import get_settings

settings = get_settings()


class ValidationSeverity(str, Enum):
    """Severity levels for validation issues."""
    CRITICAL = "critical"   # Must fix before submission (hallucination)
    WARNING = "warning"     # Should review (mismatch)
    INFO = "info"          # Minor issue (formatting)


class ErrorType(str, Enum):
    """Types of errors detected."""
    HALLUCINATION = "hallucination"
    MISMATCH = "mismatch"
    MISSING_REQUIRED = "missing_required"
    FORMAT_ERROR = "format_error"
    ALREADY_APPLIED = "already_applied"
    VISA_REQUIRED = "visa_required"
    EXPERIENCE_MISMATCH = "experience_mismatch"
    SKILL_FABRICATION = "skill_fabrication"
    DATE_INCONSISTENCY = "date_inconsistency"
    FORM_VALIDATION = "form_validation"


@dataclass
class ValidationIssue:
    """A single validation issue found by the Critic."""
    field_name: str
    issue_type: ErrorType
    severity: ValidationSeverity
    message: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None
    suggestion: Optional[str] = None


@dataclass
class CriticResult:
    """Result of Critic Agent validation."""
    passed: bool
    issues: List[ValidationIssue] = field(default_factory=list)
    confidence_score: float = 1.0
    recommendation: str = "proceed"  # proceed, fix, halt, escalate
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "passed": self.passed,
            "issues": [
                {
                    "field_name": i.field_name,
                    "issue_type": i.issue_type.value,
                    "severity": i.severity.value,
                    "message": i.message,
                    "expected_value": i.expected_value,
                    "actual_value": i.actual_value,
                    "suggestion": i.suggestion,
                }
                for i in self.issues
            ],
            "confidence_score": self.confidence_score,
            "recommendation": self.recommendation,
        }


class CriticAgent:
    """
    The Critic Agent - Adversarial validation before submission.
    
    Core responsibilities:
    1. Anti-Hallucination: Ensure form answers match resume facts
    2. Consistency Check: Verify dates, numbers, and facts align
    3. Error Detection: Identify form validation errors on page
    4. Success Verification: Confirm application was submitted
    """
    
    # Common success indicators
    SUCCESS_PATTERNS = [
        r"application\s*(has been\s*)?received",
        r"thank\s*you\s*for\s*(your\s*)?applying",
        r"successfully\s*submitted",
        r"application\s*complete",
        r"we('ve|\s*have)\s*received\s*your\s*application",
        r"your\s*application\s*is\s*being\s*reviewed",
        r"application\s*confirmation",
        r"you('ve|\s*have)\s*applied",
    ]
    
    # Common error indicators
    ERROR_PATTERNS = [
        r"already\s*applied",
        r"previously\s*applied",
        r"duplicate\s*application",
        r"visa\s*sponsorship\s*(is\s*)?(not\s*)?(available|required)",
        r"unauthorized\s*to\s*work",
        r"must\s*be\s*authorized",
        r"error\s*submitting",
        r"please\s*correct\s*the\s*following",
        r"required\s*field",
        r"invalid\s*(format|input|value)",
    ]
    
    # Form validation error selectors
    ERROR_SELECTORS = [
        ".error-message",
        ".field-error",
        ".validation-error",
        "[class*='error']",
        "[class*='invalid']",
        ".form-error",
        ".input-error",
        "[aria-invalid='true']",
    ]

    def __init__(self, resume_facts: Optional[Dict[str, Any]] = None):
        """
        Initialize Critic with resume facts for comparison.
        
        Args:
            resume_facts: Structured resume data for validation
        """
        self.resume_facts = resume_facts or {}
        self.issues: List[ValidationIssue] = []
    
    def validate_form_data(
        self,
        filled_data: Dict[str, str],
        resume_facts: Optional[Dict[str, Any]] = None
    ) -> CriticResult:
        """
        Validate filled form data against resume facts.
        
        Args:
            filled_data: Dict of field_name -> filled_value
            resume_facts: Optional override for resume data
            
        Returns:
            CriticResult with validation outcome
        """
        facts = resume_facts or self.resume_facts
        self.issues = []
        
        # Check each filled field
        for field_name, value in filled_data.items():
            self._validate_field(field_name, value, facts)
        
        # Determine overall result
        critical_issues = [i for i in self.issues if i.severity == ValidationSeverity.CRITICAL]
        warning_issues = [i for i in self.issues if i.severity == ValidationSeverity.WARNING]
        
        if critical_issues:
            return CriticResult(
                passed=False,
                issues=self.issues,
                confidence_score=0.0,
                recommendation="halt"
            )
        elif warning_issues:
            return CriticResult(
                passed=True,
                issues=self.issues,
                confidence_score=0.7,
                recommendation="fix" if len(warning_issues) > 2 else "proceed"
            )
        else:
            return CriticResult(
                passed=True,
                issues=self.issues,
                confidence_score=1.0,
                recommendation="proceed"
            )
    
    def _validate_field(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate a single field against resume facts."""
        field_lower = field_name.lower()
        value_lower = value.lower().strip()
        
        # Experience years validation
        if "experience" in field_lower or "years" in field_lower:
            self._validate_experience(field_name, value, facts)
        
        # Skills validation
        elif "skill" in field_lower or "technolog" in field_lower:
            self._validate_skills(field_name, value, facts)
        
        # Education validation
        elif "degree" in field_lower or "education" in field_lower or "university" in field_lower:
            self._validate_education(field_name, value, facts)
        
        # Name validation
        elif "name" in field_lower:
            self._validate_name(field_name, value, facts)
        
        # Email/Phone validation
        elif "email" in field_lower or "phone" in field_lower:
            self._validate_contact(field_name, value, facts)
        
        # Salary validation
        elif "salary" in field_lower or "compensation" in field_lower:
            self._validate_salary(field_name, value, facts)
    
    def _validate_experience(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate experience-related fields."""
        # Extract number from value
        numbers = re.findall(r'\d+', value)
        if not numbers:
            return
            
        claimed_years = int(numbers[0])
        actual_years = facts.get("years_of_experience", 0)
        
        # Allow some flexibility (±1 year)
        if claimed_years > actual_years + 1:
            self.issues.append(ValidationIssue(
                field_name=field_name,
                issue_type=ErrorType.EXPERIENCE_MISMATCH,
                severity=ValidationSeverity.CRITICAL,
                message=f"Claimed {claimed_years} years but resume shows {actual_years}",
                expected_value=str(actual_years),
                actual_value=str(claimed_years),
                suggestion=f"Change to {actual_years} years"
            ))
        elif claimed_years < actual_years - 2:
            self.issues.append(ValidationIssue(
                field_name=field_name,
                issue_type=ErrorType.MISMATCH,
                severity=ValidationSeverity.WARNING,
                message=f"Under-reporting experience: claimed {claimed_years}, have {actual_years}",
                expected_value=str(actual_years),
                actual_value=str(claimed_years),
                suggestion=f"Consider updating to {actual_years} years"
            ))
    
    def _validate_skills(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate skills-related fields."""
        resume_skills = set(s.lower() for s in facts.get("skills", []))
        
        if not resume_skills:
            return
        
        # Check if mentioned skills exist in resume
        mentioned_skills = re.findall(r'\b[A-Za-z+#]+\b', value)
        
        for skill in mentioned_skills:
            skill_lower = skill.lower()
            # Check if it's a technical skill that should be in resume
            if len(skill) > 2 and skill_lower not in resume_skills:
                # Check for common variations
                variations = [skill_lower, skill_lower.replace('+', 'plus'), skill_lower + 'js']
                if not any(v in resume_skills for v in variations):
                    # Only flag if it looks like a technical skill
                    if self._is_technical_skill(skill):
                        self.issues.append(ValidationIssue(
                            field_name=field_name,
                            issue_type=ErrorType.SKILL_FABRICATION,
                            severity=ValidationSeverity.CRITICAL,
                            message=f"Skill '{skill}' not found in resume",
                            actual_value=skill,
                            suggestion=f"Remove '{skill}' or add to resume first"
                        ))
    
    def _is_technical_skill(self, skill: str) -> bool:
        """Check if a word looks like a technical skill."""
        tech_indicators = [
            'python', 'java', 'javascript', 'react', 'node', 'sql', 'aws',
            'docker', 'kubernetes', 'go', 'rust', 'typescript', 'vue',
            'angular', 'django', 'flask', 'fastapi', 'spring', 'redis',
            'mongodb', 'postgres', 'mysql', 'graphql', 'rest', 'api',
            'git', 'linux', 'azure', 'gcp', 'terraform', 'ansible'
        ]
        return skill.lower() in tech_indicators
    
    def _validate_education(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate education-related fields."""
        education = facts.get("education", {})
        degree = education.get("degree", "").lower()
        
        if not degree:
            return
        
        value_lower = value.lower()
        
        # Check for degree inflation
        if "phd" in value_lower or "doctorate" in value_lower:
            if "phd" not in degree and "doctorate" not in degree:
                self.issues.append(ValidationIssue(
                    field_name=field_name,
                    issue_type=ErrorType.HALLUCINATION,
                    severity=ValidationSeverity.CRITICAL,
                    message="Claimed PhD but resume shows different degree",
                    expected_value=degree,
                    actual_value=value,
                    suggestion=f"Change to: {education.get('degree', 'Unknown')}"
                ))
        
        elif "master" in value_lower:
            if "master" not in degree and "mba" not in degree and "ms" not in degree:
                self.issues.append(ValidationIssue(
                    field_name=field_name,
                    issue_type=ErrorType.HALLUCINATION,
                    severity=ValidationSeverity.CRITICAL,
                    message="Claimed Master's but resume shows different degree",
                    expected_value=degree,
                    actual_value=value,
                    suggestion=f"Change to: {education.get('degree', 'Unknown')}"
                ))
    
    def _validate_name(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate name fields."""
        full_name = facts.get("name", "").lower()
        first_name = facts.get("first_name", "").lower()
        last_name = facts.get("last_name", "").lower()
        
        value_lower = value.lower().strip()
        
        if full_name and value_lower not in full_name and full_name not in value_lower:
            if first_name and first_name not in value_lower and last_name and last_name not in value_lower:
                self.issues.append(ValidationIssue(
                    field_name=field_name,
                    issue_type=ErrorType.MISMATCH,
                    severity=ValidationSeverity.WARNING,
                    message=f"Name mismatch: filled '{value}' but resume shows '{facts.get('name', 'Unknown')}'",
                    expected_value=facts.get("name"),
                    actual_value=value
                ))
    
    def _validate_contact(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate contact information."""
        field_lower = field_name.lower()
        
        if "email" in field_lower:
            resume_email = facts.get("email", "").lower()
            if resume_email and value.lower() != resume_email:
                self.issues.append(ValidationIssue(
                    field_name=field_name,
                    issue_type=ErrorType.MISMATCH,
                    severity=ValidationSeverity.INFO,
                    message=f"Email differs from resume",
                    expected_value=resume_email,
                    actual_value=value
                ))
        
        elif "phone" in field_lower:
            resume_phone = facts.get("phone", "")
            # Normalize phone numbers for comparison
            value_digits = re.sub(r'\D', '', value)
            resume_digits = re.sub(r'\D', '', resume_phone)
            
            if resume_digits and value_digits != resume_digits:
                self.issues.append(ValidationIssue(
                    field_name=field_name,
                    issue_type=ErrorType.MISMATCH,
                    severity=ValidationSeverity.INFO,
                    message=f"Phone differs from resume",
                    expected_value=resume_phone,
                    actual_value=value
                ))
    
    def _validate_salary(
        self,
        field_name: str,
        value: str,
        facts: Dict[str, Any]
    ) -> None:
        """Validate salary expectations."""
        # Extract numbers
        numbers = re.findall(r'[\d,]+', value.replace(',', ''))
        if not numbers:
            return
        
        salary = int(numbers[0].replace(',', ''))
        expected_min = facts.get("salary_expectation_min", 0)
        expected_max = facts.get("salary_expectation_max", float('inf'))
        
        if salary < expected_min * 0.8:
            self.issues.append(ValidationIssue(
                field_name=field_name,
                issue_type=ErrorType.MISMATCH,
                severity=ValidationSeverity.WARNING,
                message=f"Salary ${salary:,} is below your target of ${expected_min:,}",
                expected_value=str(expected_min),
                actual_value=str(salary),
                suggestion=f"Consider asking for ${expected_min:,}"
            ))
    
    def detect_page_errors(self, html_content: str) -> List[ValidationIssue]:
        """
        Detect form validation errors in page HTML.
        
        Args:
            html_content: Page HTML to analyze
            
        Returns:
            List of detected validation issues
        """
        issues = []
        html_lower = html_content.lower()
        
        # Check for error patterns
        for pattern in self.ERROR_PATTERNS:
            matches = re.findall(pattern, html_lower)
            if matches:
                # Determine error type
                if "already applied" in pattern or "previously applied" in pattern:
                    error_type = ErrorType.ALREADY_APPLIED
                elif "visa" in pattern or "authorized" in pattern:
                    error_type = ErrorType.VISA_REQUIRED
                else:
                    error_type = ErrorType.FORM_VALIDATION
                
                issues.append(ValidationIssue(
                    field_name="page",
                    issue_type=error_type,
                    severity=ValidationSeverity.CRITICAL,
                    message=f"Detected error pattern: {pattern}",
                ))
        
        return issues
    
    def verify_submission_success(
        self,
        html_content: str,
        page_url: str
    ) -> Tuple[bool, str, float]:
        """
        Verify that form submission was successful.
        
        Args:
            html_content: Page HTML after submission
            page_url: Current page URL
            
        Returns:
            Tuple of (success, message, confidence)
        """
        html_lower = html_content.lower()
        
        # Check for success patterns
        for pattern in self.SUCCESS_PATTERNS:
            if re.search(pattern, html_lower):
                return True, f"Success pattern matched: {pattern}", 0.9
        
        # Check for error patterns
        for pattern in self.ERROR_PATTERNS:
            if re.search(pattern, html_lower):
                return False, f"Error pattern detected: {pattern}", 0.95
        
        # Check URL for success indicators
        url_lower = page_url.lower()
        if any(s in url_lower for s in ["success", "confirm", "thank", "complete"]):
            return True, "URL indicates success", 0.8
        
        if any(s in url_lower for s in ["error", "fail", "invalid"]):
            return False, "URL indicates error", 0.8
        
        # Uncertain
        return True, "No clear indicators, assuming success", 0.5


# =============================================================================
# Celery Tasks
# =============================================================================

@celery_app.task(name="critic.verify_field", bind=True)
def verify_field(
    self,
    field_name: str,
    filled_value: str,
    resume_facts: Dict[str, Any]
) -> dict:
    """
    Verify a single filled field against resume facts.
    
    Args:
        field_name: Name of the field
        filled_value: Value that was filled
        resume_facts: Structured resume data
        
    Returns:
        Validation result
    """
    critic = CriticAgent(resume_facts)
    result = critic.validate_form_data({field_name: filled_value})
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "passed": result.passed,
        "issues": result.to_dict()["issues"],
        "recommendation": result.recommendation,
    }


@celery_app.task(name="critic.validate_form", bind=True)
def validate_form(
    self,
    filled_data: Dict[str, str],
    resume_facts: Dict[str, Any]
) -> dict:
    """
    Validate entire form before submission.
    
    This is the main anti-hallucination check.
    
    Args:
        filled_data: Dict of field_name -> filled_value
        resume_facts: Structured resume data
        
    Returns:
        Complete validation result
    """
    critic = CriticAgent(resume_facts)
    result = critic.validate_form_data(filled_data)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        **result.to_dict()
    }


@celery_app.task(name="critic.verify_submission", bind=True)
def verify_submission(
    self,
    html_content: str,
    page_url: str
) -> dict:
    """
    Verify form submission was successful.
    
    Args:
        html_content: Page HTML after submission
        page_url: Current page URL
        
    Returns:
        Submission verification result
    """
    critic = CriticAgent()
    success, message, confidence = critic.verify_submission_success(html_content, page_url)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "submission_success": success,
        "message": message,
        "confidence": confidence,
    }


@celery_app.task(name="critic.detect_errors", bind=True)
def detect_errors(self, html_content: str) -> dict:
    """
    Detect form validation errors on the page.
    
    Args:
        html_content: Current page HTML
        
    Returns:
        Dict with detected errors and their types
    """
    critic = CriticAgent()
    issues = critic.detect_page_errors(html_content)
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "errors_found": len(issues),
        "errors": [
            {
                "type": i.issue_type.value,
                "severity": i.severity.value,
                "message": i.message,
            }
            for i in issues
        ],
    }


@celery_app.task(name="critic.full_audit", bind=True)
def full_audit(
    self,
    filled_data: Dict[str, str],
    resume_facts: Dict[str, Any],
    page_html: str,
    page_url: str
) -> dict:
    """
    Complete audit before final submission.
    
    Combines form validation + error detection + success indicators.
    
    Args:
        filled_data: All filled form values
        resume_facts: Resume data for comparison
        page_html: Current page HTML
        page_url: Current page URL
        
    Returns:
        Complete audit result with go/no-go recommendation
    """
    critic = CriticAgent(resume_facts)
    
    # Validate form data
    form_result = critic.validate_form_data(filled_data)
    
    # Check for page errors
    page_errors = critic.detect_page_errors(page_html)
    
    # Combine all issues
    all_issues = form_result.issues + page_errors
    
    # Determine final recommendation
    critical_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.CRITICAL)
    warning_count = sum(1 for i in all_issues if i.severity == ValidationSeverity.WARNING)
    
    if critical_count > 0:
        recommendation = "halt"
        can_submit = False
    elif warning_count > 3:
        recommendation = "review"
        can_submit = False
    elif warning_count > 0:
        recommendation = "proceed_with_caution"
        can_submit = True
    else:
        recommendation = "proceed"
        can_submit = True
    
    return {
        "status": "completed",
        "task_id": self.request.id,
        "can_submit": can_submit,
        "recommendation": recommendation,
        "critical_issues": critical_count,
        "warning_issues": warning_count,
        "all_issues": [
            {
                "field": i.field_name,
                "type": i.issue_type.value,
                "severity": i.severity.value,
                "message": i.message,
                "suggestion": i.suggestion,
            }
            for i in all_issues
        ],
    }
