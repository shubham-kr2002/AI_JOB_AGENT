"""
Project JobHunter V3 - Intent Compiler Service
Implements FR-01: Intent-Based Input

Parses natural language prompts into structured Goal and Constraints objects
using LLM-based intent recognition.

Example:
    Input: "Apply to 10 Product Manager roles in NYC. Avoid crypto startups."
    Output: Goal(action="apply", role="Product Manager", count=10, location="NYC")
            Constraints(exclude_industries=["crypto"])
"""

import json
import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any
from enum import Enum

from app.core.config import get_settings

settings = get_settings()


class ActionType(str, Enum):
    """Types of autonomous actions the agent can perform."""
    SEARCH = "search"       # Find job listings
    APPLY = "apply"         # Submit applications
    SCRAPE = "scrape"       # Extract job details
    FILTER = "filter"       # Filter job listings
    ANALYZE = "analyze"     # Analyze fit/match


@dataclass
class Constraints:
    """
    Filtering constraints extracted from user intent.
    
    These constraints are used to filter out jobs that don't match
    user preferences during the search/filter phase.
    """
    # Location preferences
    locations: List[str] = field(default_factory=list)
    remote_only: bool = False
    exclude_locations: List[str] = field(default_factory=list)
    
    # Company preferences
    company_sizes: List[str] = field(default_factory=list)  # startup, mid, enterprise
    exclude_companies: List[str] = field(default_factory=list)
    target_companies: List[str] = field(default_factory=list)
    
    # Industry preferences
    industries: List[str] = field(default_factory=list)
    exclude_industries: List[str] = field(default_factory=list)
    
    # Job preferences
    min_salary: Optional[int] = None
    max_salary: Optional[int] = None
    experience_level: Optional[str] = None  # entry, mid, senior, lead
    job_types: List[str] = field(default_factory=list)  # full-time, contract, etc.
    
    # Timing constraints
    max_job_age_days: int = 14  # Ignore jobs older than this
    
    # Tech stack preferences
    required_skills: List[str] = field(default_factory=list)
    preferred_skills: List[str] = field(default_factory=list)
    exclude_skills: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


@dataclass
class Goal:
    """
    Structured goal extracted from user prompt.
    
    Represents the high-level objective the agent should accomplish.
    """
    # Core action
    action: ActionType = ActionType.APPLY
    
    # Target role/position
    role: str = ""
    role_keywords: List[str] = field(default_factory=list)
    
    # Quantity targets
    target_count: int = 10  # How many applications/searches
    
    # Search platforms
    platforms: List[str] = field(default_factory=list)  # linkedin, indeed, etc.
    
    # Raw prompt for reference
    raw_prompt: str = ""
    
    # Constraints attached to this goal
    constraints: Constraints = field(default_factory=Constraints)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result["action"] = self.action.value
        return result


class IntentCompiler:
    """
    Compiles natural language prompts into structured Goal objects.
    
    Uses a combination of:
    1. Regex patterns for common structures
    2. LLM for complex/ambiguous intents
    """
    
    # Patterns for extracting common intent elements
    PATTERNS = {
        "count": [
            r"(?:apply\s+to|find|search\s+for)\s+(\d+)",
            r"(\d+)\s+(?:jobs?|roles?|positions?)",
            r"top\s+(\d+)",
        ],
        "role": [
            r"(?:for|as\s+a?n?)\s+([A-Za-z\s]+?)\s+(?:roles?|positions?|jobs?)",
            r"([A-Za-z\s]+?)\s+(?:roles?|positions?|jobs?)\s+(?:in|at|for)",
            r"hiring\s+(?:for\s+)?([A-Za-z\s]+)",
        ],
        "location": [
            r"(?:in|at|near)\s+([A-Za-z\s,]+?)(?:\.|,|$|\s+(?:and|or|with|avoid|exclude))",
            r"(?:remote|hybrid|onsite)\s+(?:in\s+)?([A-Za-z\s,]+)",
        ],
        "remote": [
            r"\b(remote(?:\s+only)?)\b",
            r"\b(work\s+from\s+home)\b",
            r"\b(wfh)\b",
        ],
        "exclude": [
            r"(?:avoid|exclude|no|not|without)\s+([A-Za-z\s,]+?)(?:\.|$)",
            r"(?:don'?t\s+(?:want|include|apply))\s+([A-Za-z\s,]+)",
        ],
        "companies": [
            r"(?:at|from|to)\s+([A-Z][A-Za-z\s,&]+?)\s+(?:companies|startups|firms)",
            r"(YCombinator|Y\s*Combinator|YC)\s+companies",
            r"(FAANG|MAANG|Big\s*Tech)",
        ],
        "salary": [
            r"\$?(\d{2,3})[kK]?\s*(?:\+|or\s+more|minimum)",
            r"(?:salary|pay|compensation)\s+(?:above|over|at\s+least)\s+\$?(\d{2,3})[kK]?",
        ],
    }
    
    # Platform keywords
    PLATFORM_KEYWORDS = {
        "linkedin": ["linkedin", "li"],
        "indeed": ["indeed"],
        "glassdoor": ["glassdoor"],
        "greenhouse": ["greenhouse"],
        "lever": ["lever"],
        "workday": ["workday"],
        "angellist": ["angellist", "angel.co", "wellfound"],
    }
    
    def __init__(self, use_llm: bool = True):
        """
        Initialize the intent compiler.
        
        Args:
            use_llm: Whether to use LLM for complex parsing (vs regex only)
        """
        self.use_llm = use_llm
        self._llm_client = None
    
    def _get_llm_client(self):
        """Lazy-load LLM client."""
        if self._llm_client is None:
            try:
                from groq import Groq
                self._llm_client = Groq(api_key=settings.GROQ_API_KEY)
            except Exception as e:
                print(f"[IntentCompiler] Warning: Could not initialize LLM client: {e}")
                self._llm_client = None
        return self._llm_client
    
    def compile(self, prompt: str) -> Goal:
        """
        Compile a natural language prompt into a structured Goal.
        
        Args:
            prompt: User's natural language prompt
            
        Returns:
            Goal object with extracted intent and constraints
        """
        # First, try regex-based extraction
        goal = self._extract_with_patterns(prompt)
        
        # If LLM is enabled and we have a client, enhance with LLM
        if self.use_llm and settings.GROQ_API_KEY:
            goal = self._enhance_with_llm(prompt, goal)
        
        return goal
    
    def _extract_with_patterns(self, prompt: str) -> Goal:
        """Extract intent using regex patterns."""
        prompt_lower = prompt.lower()
        constraints = Constraints()
        
        # Determine action type
        action = ActionType.APPLY
        if any(w in prompt_lower for w in ["search", "find", "look for"]):
            if not any(w in prompt_lower for w in ["apply", "submit"]):
                action = ActionType.SEARCH
        
        # Extract count
        count = 10  # default
        for pattern in self.PATTERNS["count"]:
            match = re.search(pattern, prompt_lower)
            if match:
                count = int(match.group(1))
                break
        
        # Extract role
        role = ""
        role_keywords = []
        for pattern in self.PATTERNS["role"]:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                role = match.group(1).strip()
                role_keywords = [w.lower() for w in role.split() if len(w) > 2]
                break
        
        # If no role found, try to extract from common patterns
        if not role:
            # Look for capitalized job titles
            title_match = re.search(
                r"((?:[A-Z][a-z]+\s+)*(?:Engineer|Developer|Manager|Designer|Analyst|Scientist|Lead|Director))",
                prompt
            )
            if title_match:
                role = title_match.group(1).strip()
                role_keywords = [w.lower() for w in role.split() if len(w) > 2]
        
        # Extract location
        for pattern in self.PATTERNS["location"]:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                locations = [l.strip() for l in match.group(1).split(",")]
                constraints.locations = [l for l in locations if l]
                break
        
        # Check for remote
        for pattern in self.PATTERNS["remote"]:
            if re.search(pattern, prompt_lower):
                constraints.remote_only = True
                break
        
        # Extract exclusions
        for pattern in self.PATTERNS["exclude"]:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                exclusions = [e.strip() for e in match.group(1).split(",")]
                # Categorize exclusions
                for excl in exclusions:
                    excl_lower = excl.lower()
                    if any(ind in excl_lower for ind in ["crypto", "blockchain", "web3", "fintech", "gaming"]):
                        constraints.exclude_industries.append(excl)
                    elif any(comp in excl_lower for comp in ["startup", "enterprise", "agency"]):
                        constraints.exclude_companies.append(excl)
                    else:
                        constraints.exclude_industries.append(excl)
        
        # Extract target companies
        for pattern in self.PATTERNS["companies"]:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                company_ref = match.group(1).strip()
                if "ycombinator" in company_ref.lower() or "yc" in company_ref.lower():
                    constraints.target_companies.append("YCombinator")
                elif "faang" in company_ref.lower() or "maang" in company_ref.lower():
                    constraints.target_companies.extend(["Meta", "Apple", "Amazon", "Netflix", "Google", "Microsoft"])
                else:
                    constraints.target_companies.append(company_ref)
        
        # Extract salary
        for pattern in self.PATTERNS["salary"]:
            match = re.search(pattern, prompt_lower)
            if match:
                salary = int(match.group(1))
                # Assume it's in thousands if < 1000
                if salary < 1000:
                    salary *= 1000
                constraints.min_salary = salary
                break
        
        # Detect platforms
        platforms = []
        for platform, keywords in self.PLATFORM_KEYWORDS.items():
            if any(kw in prompt_lower for kw in keywords):
                platforms.append(platform)
        
        # Default to LinkedIn if no platform specified
        if not platforms:
            platforms = ["linkedin"]
        
        return Goal(
            action=action,
            role=role,
            role_keywords=role_keywords,
            target_count=count,
            platforms=platforms,
            raw_prompt=prompt,
            constraints=constraints,
        )
    
    def _enhance_with_llm(self, prompt: str, initial_goal: Goal) -> Goal:
        """Enhance the goal extraction using LLM."""
        client = self._get_llm_client()
        if not client:
            return initial_goal
        
        system_prompt = """You are an intent parser for a job application automation system.
Given a user's natural language prompt, extract structured information.

Return a JSON object with these fields:
{
    "action": "search" or "apply",
    "role": "job title/role",
    "role_keywords": ["keyword1", "keyword2"],
    "target_count": number,
    "platforms": ["linkedin", "indeed", etc.],
    "constraints": {
        "locations": ["city1", "city2"],
        "remote_only": boolean,
        "exclude_locations": [],
        "exclude_industries": ["industry1"],
        "exclude_companies": ["company1"],
        "target_companies": ["company1"],
        "min_salary": number or null,
        "experience_level": "entry/mid/senior/lead" or null,
        "max_job_age_days": number
    }
}

Only return the JSON, no explanation."""

        try:
            response = client.chat.completions.create(
                model=settings.LLM_MODEL_FAST,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500,
            )
            
            content = response.choices[0].message.content.strip()
            
            # Extract JSON from response
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                parsed = json.loads(json_match.group())
                
                # Update goal with LLM-extracted data
                if parsed.get("role"):
                    initial_goal.role = parsed["role"]
                if parsed.get("role_keywords"):
                    initial_goal.role_keywords = parsed["role_keywords"]
                if parsed.get("target_count"):
                    initial_goal.target_count = parsed["target_count"]
                if parsed.get("platforms"):
                    initial_goal.platforms = parsed["platforms"]
                if parsed.get("action"):
                    initial_goal.action = ActionType(parsed["action"])
                
                # Update constraints
                if "constraints" in parsed:
                    c = parsed["constraints"]
                    if c.get("locations"):
                        initial_goal.constraints.locations = c["locations"]
                    if c.get("remote_only"):
                        initial_goal.constraints.remote_only = c["remote_only"]
                    if c.get("exclude_industries"):
                        initial_goal.constraints.exclude_industries = c["exclude_industries"]
                    if c.get("exclude_companies"):
                        initial_goal.constraints.exclude_companies = c["exclude_companies"]
                    if c.get("target_companies"):
                        initial_goal.constraints.target_companies = c["target_companies"]
                    if c.get("min_salary"):
                        initial_goal.constraints.min_salary = c["min_salary"]
                    if c.get("experience_level"):
                        initial_goal.constraints.experience_level = c["experience_level"]
                        
        except Exception as e:
            print(f"[IntentCompiler] LLM enhancement failed: {e}")
        
        return initial_goal


# Convenience function
def compile_intent(prompt: str, use_llm: bool = True) -> Goal:
    """
    Compile a natural language prompt into a Goal.
    
    Args:
        prompt: User's natural language prompt
        use_llm: Whether to use LLM for complex parsing
        
    Returns:
        Goal object with extracted intent
    """
    compiler = IntentCompiler(use_llm=use_llm)
    return compiler.compile(prompt)
