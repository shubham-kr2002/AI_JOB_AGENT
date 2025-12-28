"""
Answer Generation API - Enhanced with FR-07 Contextual Answer Generation.

The "Brain" - Uses RAG to generate answers for form fields.

Enhancements (from PRD):
- FR-07: Contextual Answer Generation with JD + Resume
- FR-08: Hallucination Guardrails
- AIR-02: Model Routing (simple vs complex)
- AIR-03: Learning Loop integration

Endpoint: POST /api/v1/generate-answers
"""

from typing import List, Optional, Dict, Any
import asyncio
import re

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services.vector_store import VectorStoreService
from app.services.hallucination_guard import HallucinationGuard, create_hallucination_guard
from app.services.jd_scraper import JDScraper, get_jd_scraper, JobDescription
from app.db.database import get_db
from app.db.models import LearningHistory

settings = get_settings()
router = APIRouter()


# ============================================================================
# Request/Response Models
# ============================================================================

class FormField(BaseModel):
    """A single form field from the extension."""
    id: str = Field(..., description="Field ID or name")
    label: str = Field(..., description="Field label (heuristically determined)")
    type: str = Field(..., description="Field type (text, email, textarea, etc.)")
    options: Optional[List[str]] = Field(
        default=None,
        description="Options for select/radio/checkbox fields"
    )


class GenerateAnswersRequest(BaseModel):
    """Request to generate answers for form fields."""
    fields: List[FormField] = Field(
        ..., 
        description="List of form fields to generate answers for",
        min_length=1
    )
    job_description: Optional[str] = Field(
        default=None,
        description="Job description text scraped from the page"
    )
    page_url: Optional[str] = Field(
        default=None,
        description="URL of the job application page"
    )
    user_id: Optional[int] = Field(
        default=None,
        description="Optional user ID for personalized answers"
    )
    use_hallucination_guard: bool = Field(
        default=True,
        description="Whether to validate answers against resume"
    )


class FieldAnswer(BaseModel):
    """Generated answer for a single field."""
    id: str
    answer: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: str = Field(description="Where the answer came from: 'resume', 'generated', 'learning', 'default'")
    verified: bool = Field(
        default=True,
        description="Whether the answer passed hallucination check"
    )
    flagged_claims: Optional[List[str]] = Field(
        default=None,
        description="Claims that couldn't be verified (if any)"
    )


class GenerateAnswersResponse(BaseModel):
    """Response containing generated answers."""
    success: bool
    answers: List[FieldAnswer]
    fields_processed: int
    message: str
    job_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Parsed job description context"
    )


# ============================================================================
# Context Builder - FR-07 Implementation
# ============================================================================

class ContextBuilder:
    """
    Builds rich context for answer generation.
    
    Combines:
    - Resume chunks from vector store
    - Job description analysis
    - Learning history (past corrections)
    """
    
    def __init__(
        self,
        vector_service: VectorStoreService,
        jd_scraper: JDScraper,
        db: Optional[Session] = None
    ):
        self.vector_service = vector_service
        self.jd_scraper = jd_scraper
        self.db = db
        self._jd: Optional[JobDescription] = None
        self._resume_chunks: List[str] = []
    
    def build_context(
        self,
        field: FormField,
        job_description: Optional[str] = None,
        user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Build complete context for a field.
        
        Returns:
            Dict with 'resume_context', 'jd_context', 'learning_context'
        """
        context = {
            "resume_context": "",
            "jd_context": "",
            "jd_summary": None,
            "learning_answer": None,
            "learning_confidence": 0.0
        }
        
        # 1. Get relevant resume chunks
        query = f"{field.label} {field.type}"
        results = self.vector_service.search(query, k=3)
        if results:
            context["resume_context"] = "\n\n".join([doc.page_content for doc in results])
            self._resume_chunks = [doc.page_content for doc in results]
        
        # 2. Parse and include JD context
        if job_description:
            if self._jd is None:
                self._jd = self.jd_scraper.parse_job_description(job_description)
            
            context["jd_context"] = self.jd_scraper.summarize_for_prompt(self._jd)
            context["jd_summary"] = {
                "title": self._jd.title,
                "company": self._jd.company,
                "skills": self._jd.skills[:10],
                "experience_years": self._jd.experience_years
            }
        
        # 3. Check learning history for past corrections
        if self.db:
            learning_answer = self._get_learning_answer(field.label, user_id)
            if learning_answer:
                context["learning_answer"] = learning_answer
                context["learning_confidence"] = 0.95  # High confidence for learned answers
        
        return context
    
    def _get_learning_answer(
        self, 
        question: str, 
        user_id: Optional[int]
    ) -> Optional[str]:
        """Check if we have a learned answer for this question."""
        if not self.db:
            return None
        
        try:
            question_hash = LearningHistory.hash_question(question)
            
            query = self.db.query(LearningHistory).filter(
                LearningHistory.question_hash == question_hash
            )
            
            if user_id:
                query = query.filter(LearningHistory.user_id == user_id)
            
            correction = query.first()
            
            if correction:
                # Update usage count
                correction.times_used += 1
                self.db.commit()
                return correction.corrected_answer
            
            return None
            
        except Exception as e:
            print(f"[ContextBuilder] Error checking learning history: {e}")
            return None
    
    def get_resume_chunks(self) -> List[str]:
        """Get cached resume chunks."""
        return self._resume_chunks
    
    def get_parsed_jd(self) -> Optional[JobDescription]:
        """Get the parsed job description."""
        return self._jd


# ============================================================================
# Answer Generation Logic - Enhanced
# ============================================================================

def get_answer_for_field(
    field: FormField,
    context: Dict[str, Any],
    vector_service: VectorStoreService,
    hallucination_guard: Optional[HallucinationGuard] = None,
    use_guard: bool = True
) -> FieldAnswer:
    """
    Generate an answer for a single form field using RAG.
    
    Enhanced with:
    - Learning history (AIR-03)
    - JD context (FR-07)
    - Hallucination check (FR-08)
    """
    label_lower = field.label.lower()
    field_type = field.type.lower()
    
    # ==== LEARNING HISTORY FIRST (AIR-03) ====
    if context.get("learning_answer"):
        return FieldAnswer(
            id=field.id,
            answer=context["learning_answer"],
            confidence=context["learning_confidence"],
            source="learning",
            verified=True
        )
    
    resume_chunks = context.get("resume_context", "").split("\n\n")
    
    # ==== SIMPLE FIELD MATCHING (No LLM needed) ====
    
    # Email fields
    if field_type == "email" or "email" in label_lower:
        email = extract_from_context(resume_chunks, ["email", "@"])
        if email:
            return FieldAnswer(
                id=field.id,
                answer=email,
                confidence=0.95,
                source="resume",
                verified=True
            )
    
    # Phone fields
    if field_type == "tel" or any(x in label_lower for x in ["phone", "mobile", "telephone", "cell"]):
        phone = extract_from_context(resume_chunks, ["phone", "mobile", "tel", "+1", "("])
        if phone:
            return FieldAnswer(
                id=field.id,
                answer=phone,
                confidence=0.90,
                source="resume",
                verified=True
            )
    
    # Name fields
    if any(x in label_lower for x in ["first name", "firstname", "given name"]):
        results = vector_service.search("name contact information", k=1)
        if results:
            name = extract_first_name(results[0].page_content)
            if name:
                return FieldAnswer(
                    id=field.id,
                    answer=name,
                    confidence=0.85,
                    source="resume",
                    verified=True
                )
    
    if any(x in label_lower for x in ["last name", "lastname", "surname", "family name"]):
        results = vector_service.search("name contact information", k=1)
        if results:
            name = extract_last_name(results[0].page_content)
            if name:
                return FieldAnswer(
                    id=field.id,
                    answer=name,
                    confidence=0.85,
                    source="resume",
                    verified=True
                )
    
    if label_lower in ["name", "full name", "your name"]:
        results = vector_service.search("name contact information", k=1)
        if results:
            name = extract_full_name(results[0].page_content)
            if name:
                return FieldAnswer(
                    id=field.id,
                    answer=name,
                    confidence=0.85,
                    source="resume",
                    verified=True
                )
    
    # LinkedIn
    if "linkedin" in label_lower:
        linkedin = extract_from_context(resume_chunks, ["linkedin.com", "linkedin"])
        if linkedin:
            return FieldAnswer(
                id=field.id,
                answer=linkedin,
                confidence=0.90,
                source="resume",
                verified=True
            )
    
    # GitHub
    if "github" in label_lower:
        github = extract_from_context(resume_chunks, ["github.com", "github"])
        if github:
            return FieldAnswer(
                id=field.id,
                answer=github,
                confidence=0.90,
                source="resume",
                verified=True
            )
    
    # Website/Portfolio
    if any(x in label_lower for x in ["website", "portfolio", "url", "personal site"]):
        url = extract_from_context(resume_chunks, ["http", "www.", ".com", ".io"])
        if url:
            return FieldAnswer(
                id=field.id,
                answer=url,
                confidence=0.85,
                source="resume",
                verified=True
            )
    
    # Location/Address
    if any(x in label_lower for x in ["city", "location", "address"]):
        location = extract_from_context(resume_chunks, ["city", "location", ","])
        if location:
            return FieldAnswer(
                id=field.id,
                answer=location,
                confidence=0.80,
                source="resume",
                verified=True
            )
    
    # ==== COMPLEX FIELDS (Need LLM with RAG) ====
    answer = generate_llm_answer(field, context, vector_service)
    
    # ==== HALLUCINATION CHECK (FR-08) ====
    if use_guard and hallucination_guard and answer.answer:
        validation = hallucination_guard.validate_answer(
            answer.answer,
            field.label,
            strict_mode=False
        )
        
        if not validation.is_valid:
            answer.verified = False
            answer.flagged_claims = validation.flagged_claims
            answer.confidence = min(answer.confidence, validation.confidence)
        else:
            answer.verified = True
    
    return answer


def extract_from_context(chunks: List[str], keywords: List[str]) -> Optional[str]:
    """Extract a value from context chunks based on keywords."""
    full_text = " ".join(chunks)
    
    # Email pattern
    if "@" in keywords or "email" in keywords:
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        match = re.search(email_pattern, full_text)
        if match:
            return match.group()
    
    # Phone pattern
    if any(x in keywords for x in ["phone", "mobile", "tel", "+1", "("]):
        phone_patterns = [
            r'\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            r'\d{10}',
            r'\(\d{3}\)\s*\d{3}-\d{4}'
        ]
        for pattern in phone_patterns:
            match = re.search(pattern, full_text)
            if match:
                return match.group()
    
    # URL patterns
    if any(x in keywords for x in ["http", "www.", ".com", ".io", "linkedin", "github"]):
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        matches = re.findall(url_pattern, full_text)
        for match in matches:
            for kw in keywords:
                if kw in match.lower():
                    return match
        if matches:
            return matches[0]
    
    return None


def extract_first_name(text: str) -> Optional[str]:
    """Extract first name from text."""
    patterns = [
        r'(?:name|contact)[:\s]+([A-Z][a-z]+)',
        r'^([A-Z][a-z]+)\s+[A-Z]',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
    
    words = text.split()
    for word in words[:5]:
        if word and word[0].isupper() and word.isalpha():
            return word
    
    return None


def extract_last_name(text: str) -> Optional[str]:
    """Extract last name from text."""
    patterns = [
        r'(?:name|contact)[:\s]+[A-Z][a-z]+\s+([A-Z][a-z]+)',
        r'^[A-Z][a-z]+\s+([A-Z][a-z]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
    
    return None


def extract_full_name(text: str) -> Optional[str]:
    """Extract full name from text."""
    patterns = [
        r'(?:name|contact)[:\s]+([A-Z][a-z]+\s+[A-Z][a-z]+)',
        r'^([A-Z][a-z]+\s+[A-Z][a-z]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            return match.group(1)
    
    return None


def generate_llm_answer(
    field: FormField, 
    context: Dict[str, Any],
    vector_service: VectorStoreService
) -> FieldAnswer:
    """
    Generate an answer using LLM with RAG context.
    
    Enhanced with JD context (FR-07) for tailored answers.
    """
    try:
        from langchain_groq import ChatGroq
        
        resume_context = context.get("resume_context", "")
        jd_context = context.get("jd_context", "")
        
        if not resume_context:
            # Query for relevant context
            query = f"Information relevant to: {field.label}"
            results = vector_service.search(query, k=3)
            
            if not results:
                return FieldAnswer(
                    id=field.id,
                    answer="",
                    confidence=0.0,
                    source="default",
                    verified=True
                )
            
            resume_context = "\n\n".join([doc.page_content for doc in results])
        
        # Build enhanced prompt with JD context (FR-07)
        prompt = f"""You are filling out a job application form. Based on the resume/profile information and job context provided, generate an appropriate answer.

FORM FIELD:
- Label: {field.label}
- Type: {field.type}
- ID: {field.id}

RESUME/PROFILE CONTEXT:
{resume_context}

"""
        
        # Add JD context if available (FR-07)
        if jd_context:
            prompt += f"""JOB DESCRIPTION CONTEXT:
{jd_context}

IMPORTANT: Tailor your answer to highlight experience relevant to this specific job.
"""
        
        prompt += """
INSTRUCTIONS:
1. Provide ONLY the answer text, nothing else
2. Be concise and professional
3. If the field is a short text field, keep the answer brief (1-2 lines)
4. If it's a textarea, provide a longer response (3-5 sentences)
5. CRITICAL: Only mention skills/experience that are in the resume context
6. If you cannot find relevant information, respond with an empty string ""

YOUR ANSWER:"""

        # Check if Groq API key is configured
        if not settings.GROQ_API_KEY:
            return FieldAnswer(
                id=field.id,
                answer=extract_best_match(field.label, resume_context),
                confidence=0.5,
                source="generated",
                verified=True
            )
        
        # Use complex model for textarea, simple for short fields (AIR-02)
        model = settings.LLM_MODEL_COMPLEX if field.type == "textarea" else settings.LLM_MODEL_SIMPLE
        
        llm = ChatGroq(
            api_key=settings.GROQ_API_KEY,
            model_name=model,
            temperature=0.1,
            max_tokens=500
        )
        
        response = llm.invoke(prompt)
        answer = response.content.strip()
        
        # Clean up the answer
        if answer.startswith('"') and answer.endswith('"'):
            answer = answer[1:-1]
        
        return FieldAnswer(
            id=field.id,
            answer=answer,
            confidence=0.75 if answer else 0.0,
            source="generated",
            verified=True  # Will be updated by hallucination guard
        )
        
    except Exception as e:
        print(f"LLM generation error for field {field.id}: {e}")
        return FieldAnswer(
            id=field.id,
            answer="",
            confidence=0.0,
            source="default",
            verified=True
        )


def extract_best_match(label: str, context: str) -> str:
    """Simple extraction without LLM - find best matching line."""
    label_words = set(label.lower().split())
    lines = context.split('\n')
    
    best_match = ""
    best_score = 0
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        line_words = set(line.lower().split())
        overlap = len(label_words & line_words)
        
        if overlap > best_score:
            best_score = overlap
            best_match = line
    
    return best_match[:500] if best_match else ""


# ============================================================================
# API Endpoint - Enhanced
# ============================================================================

@router.post(
    "/generate-answers",
    response_model=GenerateAnswersResponse,
    summary="Generate answers for form fields",
    description="Uses RAG with JD context to generate answers for job application form fields"
)
async def generate_answers(
    request: GenerateAnswersRequest,
    db: Session = Depends(get_db)
):
    """
    Generate answers for form fields using resume + JD context.
    
    Enhanced with:
    - FR-07: Contextual Answer Generation (JD + Resume)
    - FR-08: Hallucination Guardrails
    - AIR-02: Model Routing
    - AIR-03: Learning Loop integration
    """
    try:
        vector_service = VectorStoreService()
        jd_scraper = get_jd_scraper()
        
        # Check if we have any documents
        stats = vector_service.get_collection_stats()
        if stats.get("document_count", 0) == 0:
            return GenerateAnswersResponse(
                success=False,
                answers=[],
                fields_processed=0,
                message="No resume uploaded. Please upload your resume first."
            )
        
        # Initialize context builder
        context_builder = ContextBuilder(
            vector_service=vector_service,
            jd_scraper=jd_scraper,
            db=db
        )
        
        # Initialize hallucination guard if enabled
        hallucination_guard = None
        if request.use_hallucination_guard:
            hallucination_guard = create_hallucination_guard()
        
        # Generate answers for each field
        answers = []
        for field in request.fields:
            # Build context for this field
            context = context_builder.build_context(
                field=field,
                job_description=request.job_description,
                user_id=request.user_id
            )
            
            # Generate answer with all enhancements
            answer = get_answer_for_field(
                field=field,
                context=context,
                vector_service=vector_service,
                hallucination_guard=hallucination_guard,
                use_guard=request.use_hallucination_guard
            )
            answers.append(answer)
        
        # Count results
        successful = sum(1 for a in answers if a.answer and a.confidence > 0)
        verified = sum(1 for a in answers if a.verified)
        from_learning = sum(1 for a in answers if a.source == "learning")
        
        # Get parsed JD for response
        jd_summary = None
        parsed_jd = context_builder.get_parsed_jd()
        if parsed_jd:
            jd_summary = {
                "title": parsed_jd.title,
                "company": parsed_jd.company,
                "skills": parsed_jd.skills[:10],
                "experience_years": parsed_jd.experience_years
            }
        
        return GenerateAnswersResponse(
            success=True,
            answers=answers,
            fields_processed=len(request.fields),
            message=f"Generated {successful} answers ({from_learning} from learning history, {verified} verified)",
            job_context=jd_summary
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate answers: {str(e)}"
        )


@router.options("/generate-answers")
async def options_generate_answers():
    """Handle CORS preflight requests."""
    return JSONResponse(
        content={},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )
