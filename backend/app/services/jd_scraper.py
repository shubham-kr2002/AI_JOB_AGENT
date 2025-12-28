"""
Job Description Scraping Service.

From AFD.md Phase B:
"Query Vector DB for relevant experience based on the 
Job Description found on the page."

This service extracts and processes job descriptions from job pages
to provide better context for answer generation.
"""

import re
from typing import Optional, Dict, List
from dataclasses import dataclass, field


@dataclass
class JobDescription:
    """Parsed job description data."""
    title: str = ""
    company: str = ""
    location: str = ""
    description: str = ""
    requirements: List[str] = field(default_factory=list)
    responsibilities: List[str] = field(default_factory=list)
    skills: List[str] = field(default_factory=list)
    experience_years: Optional[int] = None
    salary_range: Optional[str] = None
    job_type: str = ""  # full-time, part-time, contract, etc.
    raw_text: str = ""


class JDScraper:
    """
    Extracts and parses job descriptions from raw page text.
    
    The extension sends the page text, and we parse it here
    to extract structured job information.
    """
    
    # Section headers to identify different parts of JD
    REQUIREMENT_HEADERS = [
        'requirements', 'qualifications', 'what we\'re looking for',
        'who you are', 'must have', 'required skills', 'what you need',
        'minimum qualifications', 'basic qualifications'
    ]
    
    RESPONSIBILITY_HEADERS = [
        'responsibilities', 'what you\'ll do', 'role', 'duties',
        'about the role', 'job description', 'the opportunity',
        'what you will do', 'key responsibilities'
    ]
    
    SKILL_PATTERNS = [
        r'\b(python|java|javascript|typescript|react|angular|vue)\b',
        r'\b(aws|azure|gcp|docker|kubernetes|terraform)\b',
        r'\b(sql|postgresql|mysql|mongodb|redis)\b',
        r'\b(machine learning|ml|ai|deep learning|nlp)\b',
        r'\b(agile|scrum|ci/cd|devops|git)\b',
        r'\b(node\.?js|django|flask|spring|fastapi)\b',
        r'\b(rest|graphql|microservices|api)\b',
    ]
    
    EXPERIENCE_PATTERNS = [
        r'(\d+)\+?\s*(?:years?|yrs?)(?:\s+of)?\s+(?:experience|exp)',
        r'(?:experience|exp)(?:\s+of)?\s*(\d+)\+?\s*(?:years?|yrs?)',
        r'(\d+)\s*-\s*(\d+)\s*(?:years?|yrs?)',
    ]
    
    def __init__(self):
        """Initialize the JD scraper."""
        pass
    
    def parse_job_description(self, raw_text: str) -> JobDescription:
        """
        Parse raw page text into structured job description.
        
        Args:
            raw_text: Raw text content from the job page
            
        Returns:
            JobDescription with extracted fields
        """
        jd = JobDescription(raw_text=raw_text)
        
        # Clean the text
        clean_text = self._clean_text(raw_text)
        lines = clean_text.split('\n')
        
        # Extract structured sections
        jd.requirements = self._extract_section(lines, self.REQUIREMENT_HEADERS)
        jd.responsibilities = self._extract_section(lines, self.RESPONSIBILITY_HEADERS)
        jd.skills = self._extract_skills(clean_text)
        jd.experience_years = self._extract_experience(clean_text)
        jd.description = self._extract_description(clean_text)
        
        # Try to extract title and company from common patterns
        jd.title = self._extract_title(lines)
        jd.company = self._extract_company(lines)
        
        return jd
    
    def _clean_text(self, text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        # Preserve newlines for structure
        text = re.sub(r'[•●○◦▪▸►]\s*', '\n• ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        return text.strip()
    
    def _extract_section(
        self, 
        lines: List[str], 
        headers: List[str]
    ) -> List[str]:
        """Extract bullet points from a section."""
        items = []
        in_section = False
        
        for line in lines:
            line_lower = line.lower().strip()
            
            # Check if we're entering the section
            if any(h in line_lower for h in headers):
                in_section = True
                continue
            
            # Check if we're leaving the section (new major header)
            if in_section and self._is_section_header(line_lower):
                break
            
            # Collect items in section
            if in_section and line.strip():
                # Clean bullet points
                item = re.sub(r'^[•●○◦▪▸►-]\s*', '', line.strip())
                if len(item) > 10:  # Skip very short items
                    items.append(item)
        
        return items[:15]  # Limit to 15 items
    
    def _is_section_header(self, line: str) -> bool:
        """Check if a line is a section header."""
        all_headers = (
            self.REQUIREMENT_HEADERS + 
            self.RESPONSIBILITY_HEADERS + 
            ['benefits', 'perks', 'about us', 'company', 'apply', 'salary']
        )
        return any(h in line for h in all_headers)
    
    def _extract_skills(self, text: str) -> List[str]:
        """Extract technical skills from text."""
        skills = set()
        text_lower = text.lower()
        
        for pattern in self.SKILL_PATTERNS:
            matches = re.findall(pattern, text_lower, re.IGNORECASE)
            skills.update(matches)
        
        return list(skills)
    
    def _extract_experience(self, text: str) -> Optional[int]:
        """Extract years of experience requirement."""
        text_lower = text.lower()
        
        for pattern in self.EXPERIENCE_PATTERNS:
            match = re.search(pattern, text_lower)
            if match:
                # Return the first number found
                try:
                    return int(match.group(1))
                except (IndexError, ValueError):
                    continue
        
        return None
    
    def _extract_description(self, text: str) -> str:
        """Extract a summary description."""
        # Take first 500 chars as description
        # In production, use more sophisticated extraction
        clean = re.sub(r'\s+', ' ', text)
        return clean[:500] + "..." if len(clean) > 500 else clean
    
    def _extract_title(self, lines: List[str]) -> str:
        """Try to extract job title from first few lines."""
        title_keywords = ['engineer', 'developer', 'manager', 'analyst', 'designer']
        
        for line in lines[:10]:
            line_lower = line.lower()
            if any(kw in line_lower for kw in title_keywords):
                # Clean and return
                return line.strip()[:100]
        
        return lines[0][:100] if lines else ""
    
    def _extract_company(self, lines: List[str]) -> str:
        """Try to extract company name."""
        # Look for "at Company" or "Company is hiring" patterns
        for line in lines[:15]:
            match = re.search(r'(?:at|join)\s+([A-Z][A-Za-z0-9\s]+)', line)
            if match:
                return match.group(1).strip()[:100]
        
        return ""
    
    def summarize_for_prompt(self, jd: JobDescription) -> str:
        """
        Create a concise summary for LLM prompts.
        
        Args:
            jd: Parsed JobDescription
            
        Returns:
            Summary string for inclusion in prompts
        """
        parts = []
        
        if jd.title:
            parts.append(f"Position: {jd.title}")
        
        if jd.company:
            parts.append(f"Company: {jd.company}")
        
        if jd.skills:
            parts.append(f"Required Skills: {', '.join(jd.skills[:10])}")
        
        if jd.experience_years:
            parts.append(f"Experience Required: {jd.experience_years}+ years")
        
        if jd.requirements:
            parts.append(f"Key Requirements: {'; '.join(jd.requirements[:5])}")
        
        if jd.responsibilities:
            parts.append(f"Responsibilities: {'; '.join(jd.responsibilities[:5])}")
        
        return "\n".join(parts)


# Singleton instance
_jd_scraper: Optional[JDScraper] = None


def get_jd_scraper() -> JDScraper:
    """Get the singleton JD scraper instance."""
    global _jd_scraper
    if _jd_scraper is None:
        _jd_scraper = JDScraper()
    return _jd_scraper
