"""
Hallucination Guard Service - PRD FR-08 Implementation.

From Architecture.md Section 5:
"A secondary 'Critic' agent checks the generated answer against the 
Resume Vector Store. If the fact isn't in the DB, it forces a 
'I don't have experience with X' answer or asks the user."

This service validates LLM-generated answers against the resume
to prevent the AI from inventing fake skills or experiences.
"""

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass

from app.services.vector_store import VectorStoreService


@dataclass
class ValidationResult:
    """Result of hallucination check."""
    is_valid: bool
    confidence: float  # 0.0 to 1.0
    flagged_claims: List[str]  # Claims that couldn't be verified
    verified_claims: List[str]  # Claims found in resume
    suggestion: Optional[str]  # Suggested rewrite if invalid
    reason: str


class HallucinationGuard:
    """
    Validates LLM-generated answers against the resume vector store.
    
    Strategy:
    1. Extract claims/facts from the generated answer
    2. Search the vector store for supporting evidence
    3. Flag any claims not found in the resume
    4. Suggest rewrites for flagged content
    """
    
    # Keywords that indicate factual claims about skills/experience
    SKILL_PATTERNS = [
        r'\b(?:proficient|expert|experienced|skilled)\s+(?:in|with)\s+([A-Za-z0-9\+\#\.\s]+)',
        r'\b(?:worked|work)\s+(?:with|on)\s+([A-Za-z0-9\+\#\.\s]+)',
        r'\b(?:built|developed|created|designed|implemented)\s+([A-Za-z0-9\+\#\.\s]+)',
        r'\b(\d+)\s*(?:\+)?\s*years?\s+(?:of\s+)?(?:experience|exp)',
        r'\b(?:using|used)\s+([A-Za-z0-9\+\#\.\s]+)',
    ]
    
    # Common tech skills to look for
    TECH_KEYWORDS = [
        'python', 'javascript', 'typescript', 'react', 'angular', 'vue',
        'node', 'django', 'flask', 'fastapi', 'spring', 'java', 'kotlin',
        'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'terraform',
        'sql', 'postgresql', 'mongodb', 'redis', 'elasticsearch',
        'machine learning', 'ml', 'ai', 'deep learning', 'pytorch', 'tensorflow',
        'ci/cd', 'git', 'agile', 'scrum', 'devops', 'microservices',
        'rest', 'graphql', 'api', 'backend', 'frontend', 'full stack',
        'c++', 'c#', 'go', 'rust', 'ruby', 'php', 'swift', 'objective-c'
    ]
    
    def __init__(self, vector_service: VectorStoreService):
        """
        Initialize the guard with a vector store service.
        
        Args:
            vector_service: VectorStoreService instance for resume search
        """
        self.vector_service = vector_service
    
    def extract_claims(self, answer: str) -> List[str]:
        """
        Extract factual claims from an answer.
        
        Args:
            answer: The LLM-generated answer
            
        Returns:
            List of extracted claims/skills
        """
        claims = set()
        answer_lower = answer.lower()
        
        # Check for explicit skill patterns
        for pattern in self.SKILL_PATTERNS:
            matches = re.findall(pattern, answer_lower, re.IGNORECASE)
            claims.update(m.strip() for m in matches if m.strip())
        
        # Check for tech keywords
        for keyword in self.TECH_KEYWORDS:
            if keyword in answer_lower:
                claims.add(keyword)
        
        # Extract years of experience claims
        years_pattern = r'(\d+)\s*\+?\s*years?'
        years_matches = re.findall(years_pattern, answer_lower)
        for years in years_matches:
            claims.add(f"{years} years experience")
        
        return list(claims)
    
    def verify_claim(
        self, 
        claim: str, 
        threshold: float = 0.5
    ) -> Tuple[bool, float, List[str]]:
        """
        Verify a single claim against the resume.
        
        Args:
            claim: The claim to verify
            threshold: Minimum similarity score to consider verified
            
        Returns:
            Tuple of (is_verified, confidence, supporting_chunks)
        """
        try:
            results = self.vector_service.search_with_scores(claim, k=3)
            
            if not results:
                return False, 0.0, []
            
            # Get the best match
            best_doc, best_score = results[0]
            
            # Check if claim keywords appear in the retrieved context
            claim_keywords = set(claim.lower().split())
            doc_lower = best_doc.page_content.lower()
            
            keyword_matches = sum(1 for kw in claim_keywords if kw in doc_lower)
            keyword_ratio = keyword_matches / len(claim_keywords) if claim_keywords else 0
            
            # Combine semantic similarity with keyword matching
            combined_confidence = (best_score + keyword_ratio) / 2
            
            is_verified = combined_confidence >= threshold
            supporting = [doc.page_content for doc, score in results if score >= threshold * 0.8]
            
            return is_verified, combined_confidence, supporting
            
        except Exception as e:
            print(f"[HallucinationGuard] Error verifying claim: {e}")
            return False, 0.0, []
    
    def validate_answer(
        self, 
        answer: str, 
        question: str,
        strict_mode: bool = False
    ) -> ValidationResult:
        """
        Validate an LLM-generated answer against the resume.
        
        Args:
            answer: The generated answer to validate
            question: The original question (for context)
            strict_mode: If True, flag answers even for minor issues
            
        Returns:
            ValidationResult with validation details
        """
        # Extract claims from the answer
        claims = self.extract_claims(answer)
        
        if not claims:
            # No factual claims to verify
            return ValidationResult(
                is_valid=True,
                confidence=0.8,
                flagged_claims=[],
                verified_claims=[],
                suggestion=None,
                reason="No factual claims requiring verification"
            )
        
        verified_claims = []
        flagged_claims = []
        total_confidence = 0.0
        
        for claim in claims:
            is_verified, confidence, _ = self.verify_claim(claim)
            total_confidence += confidence
            
            if is_verified:
                verified_claims.append(claim)
            else:
                flagged_claims.append(claim)
        
        avg_confidence = total_confidence / len(claims) if claims else 0.0
        
        # Determine validity
        if strict_mode:
            is_valid = len(flagged_claims) == 0
        else:
            # Allow some unverified claims if most are verified
            verified_ratio = len(verified_claims) / len(claims) if claims else 1.0
            is_valid = verified_ratio >= 0.5 and avg_confidence >= 0.4
        
        # Generate suggestion if invalid
        suggestion = None
        if not is_valid and flagged_claims:
            suggestion = self._generate_suggestion(answer, flagged_claims, question)
        
        reason = self._generate_reason(verified_claims, flagged_claims, is_valid)
        
        return ValidationResult(
            is_valid=is_valid,
            confidence=avg_confidence,
            flagged_claims=flagged_claims,
            verified_claims=verified_claims,
            suggestion=suggestion,
            reason=reason
        )
    
    def _generate_suggestion(
        self, 
        answer: str, 
        flagged_claims: List[str],
        question: str
    ) -> str:
        """Generate a safer alternative answer."""
        # For now, generate a humble disclaimer
        # In production, this could use the LLM to rewrite
        
        flagged_str = ", ".join(flagged_claims[:3])
        
        return (
            f"I notice this answer mentions {flagged_str}, which I couldn't "
            f"verify from the resume. Consider revising or providing additional context."
        )
    
    def _generate_reason(
        self, 
        verified: List[str], 
        flagged: List[str], 
        is_valid: bool
    ) -> str:
        """Generate a human-readable reason for the validation result."""
        if is_valid:
            if verified:
                return f"Verified claims: {', '.join(verified[:3])}"
            return "No claims requiring verification"
        else:
            return f"Unverified claims: {', '.join(flagged[:3])}"


def create_hallucination_guard() -> Optional[HallucinationGuard]:
    """
    Factory function to create a HallucinationGuard instance.
    
    Returns:
        HallucinationGuard or None if vector store unavailable
    """
    try:
        vector_service = VectorStoreService()
        return HallucinationGuard(vector_service)
    except Exception as e:
        print(f"[HallucinationGuard] Failed to initialize: {e}")
        return None
