"""Request models for API endpoints."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Language(str, Enum):
    """Supported languages."""
    
    EN = "en"
    ES = "es"


class CVGenerateRequest(BaseModel):
    """Request model for CV generation (MVP)."""
    
    language: Language = Field(
        ...,
        description="Language for the CV (en for English, es for Spanish)",
        example="en"
    )


class CVGenerateDynamicRequest(BaseModel):
    """Request model for dynamic CV generation with LLM."""
    
    job_description: str = Field(
        ...,
        description="Job description as text or URL. If URL is provided, the system will automatically fetch and parse the content. Supports both plain text and HTML pages. Language and role will be automatically detected.",
        example="https://example.com/job-posting or We are looking for a Senior Software Engineer..."
    )


class CoverLetterGenerateRequest(BaseModel):
    """Request model for cover letter generation with LLM."""
    
    job_description: str = Field(
        ...,
        description="Job description as text or URL. If URL is provided, the system will automatically fetch and parse the content. Supports both plain text and HTML pages. Language and role will be automatically detected.",
        example="https://example.com/job-posting or We are looking for a Senior Software Engineer..."
    )
    company: Optional[str] = Field(
        None,
        description="Company name. If provided, the system will research company information to adapt the cover letter to the company culture.",
        example="Tech Corp"
    )

