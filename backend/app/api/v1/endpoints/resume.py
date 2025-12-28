"""
Resume Ingestion API
Handles PDF upload, text extraction, chunking, and vector storage.

Endpoint: POST /api/v1/resume/upload
"""

import re
from io import BytesIO
from typing import Optional, List

from fastapi import APIRouter, File, UploadFile, HTTPException, status
from pydantic import BaseModel
from PyPDF2 import PdfReader
from PyPDF2.errors import PdfReadError

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class ResumeUploadResponse(BaseModel):
    """Response model for resume upload."""
    success: bool
    filename: str
    page_count: int
    character_count: int
    raw_text: str
    chunks_created: int
    message: str


class ChunkInfo(BaseModel):
    """Information about a single chunk."""
    content: str
    metadata: dict
    relevance_score: Optional[float] = None


class ErrorResponse(BaseModel):
    """Error response model."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ============================================================================
# Text Cleaning Utilities
# ============================================================================

def clean_extracted_text(text: str) -> str:
    """
    Clean extracted PDF text by removing excess whitespace and normalizing formatting.
    
    Operations:
    1. Replace multiple spaces with single space
    2. Replace multiple newlines with double newline (preserve paragraphs)
    3. Remove leading/trailing whitespace from lines
    4. Remove non-printable characters
    5. Normalize unicode characters
    
    Args:
        text: Raw extracted text from PDF
        
    Returns:
        Cleaned text string
    """
    if not text:
        return ""
    
    # Remove non-printable characters (keep newlines, tabs, and standard chars)
    text = re.sub(r'[^\x20-\x7E\n\t]', ' ', text)
    
    # Replace tabs with spaces
    text = text.replace('\t', ' ')
    
    # Replace multiple spaces with single space
    text = re.sub(r' +', ' ', text)
    
    # Clean up each line (strip whitespace)
    lines = [line.strip() for line in text.split('\n')]
    
    # Remove empty lines but preserve paragraph breaks
    cleaned_lines = []
    prev_empty = False
    
    for line in lines:
        if line:
            cleaned_lines.append(line)
            prev_empty = False
        elif not prev_empty:
            cleaned_lines.append('')  # Keep one empty line for paragraph break
            prev_empty = True
    
    # Join lines back together
    text = '\n'.join(cleaned_lines)
    
    # Final trim
    text = text.strip()
    
    return text


def extract_text_from_pdf(pdf_content: bytes) -> tuple[str, int]:
    """
    Extract text from PDF bytes using PyPDF2.
    
    Args:
        pdf_content: Raw PDF file bytes
        
    Returns:
        Tuple of (extracted_text, page_count)
        
    Raises:
        ValueError: If PDF is invalid or cannot be read
    """
    try:
        pdf_file = BytesIO(pdf_content)
        reader = PdfReader(pdf_file)
        
        page_count = len(reader.pages)
        
        # Extract text from all pages
        text_parts = []
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
        
        full_text = '\n\n'.join(text_parts)
        
        return full_text, page_count
        
    except PdfReadError as e:
        raise ValueError(f"Invalid or corrupted PDF file: {str(e)}")
    except Exception as e:
        raise ValueError(f"Failed to read PDF: {str(e)}")


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "/upload",
    response_model=ResumeUploadResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid file"},
        415: {"model": ErrorResponse, "description": "Unsupported file type"},
        500: {"model": ErrorResponse, "description": "Processing error"},
    },
    summary="Upload Resume PDF",
    description="Upload a PDF resume file. Extracts and cleans text content."
)
async def upload_resume(
    file: UploadFile = File(..., description="PDF resume file")
) -> ResumeUploadResponse:
    """
    Upload and process a resume PDF file.
    
    - **file**: PDF file to upload (max recommended: 10MB)
    
    Returns extracted and cleaned text from the resume.
    """
    
    # Validate file type
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided"
        )
    
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only PDF files are supported. Please upload a .pdf file."
        )
    
    # Check content type if available
    if file.content_type and file.content_type != 'application/pdf':
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Invalid content type: {file.content_type}. Expected application/pdf."
        )
    
    try:
        # Read file content
        content = await file.read()
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(content) > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large. Maximum size is 10MB, got {len(content) / 1024 / 1024:.2f}MB"
            )
        
        # Validate it's actually a PDF (check magic bytes)
        if not content.startswith(b'%PDF'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File does not appear to be a valid PDF"
            )
        
        # Extract text from PDF
        raw_text, page_count = extract_text_from_pdf(content)
        
        # Clean the extracted text
        cleaned_text = clean_extracted_text(raw_text)
        
        if not cleaned_text:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Could not extract any text from the PDF. The file may be image-based or empty."
            )
        
        # Chunk and store in vector database
        from app.services.vector_store import ingest_resume
        
        try:
            ingestion_result = ingest_resume(
                text=cleaned_text,
                filename=file.filename,
                user_id=None  # TODO: Get from auth when implemented
            )
            chunks_created = ingestion_result["chunks_created"]
        except Exception as e:
            # Log but don't fail - text extraction still succeeded
            print(f"Warning: Vector storage failed: {e}")
            chunks_created = 0
        
        return ResumeUploadResponse(
            success=True,
            filename=file.filename,
            page_count=page_count,
            character_count=len(cleaned_text),
            raw_text=cleaned_text,
            chunks_created=chunks_created,
            message=f"Successfully extracted {len(cleaned_text)} characters from {page_count} page(s). Created {chunks_created} vector chunks."
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process resume: {str(e)}"
        )
    finally:
        # Ensure file is closed
        await file.close()
