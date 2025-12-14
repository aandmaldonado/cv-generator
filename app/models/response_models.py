"""Response models for API endpoints."""

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    """Error response model."""
    
    detail: str = Field(
        ...,
        description="Error message describing what went wrong",
        example="Invalid language provided. Supported languages: en, es"
    )


class HealthResponse(BaseModel):
    """Health check response model."""
    
    status: str = Field(
        ...,
        description="Service status",
        example="ok"
    )


class RootResponse(BaseModel):
    """Root endpoint response model."""
    
    message: str = Field(
        ...,
        description="API name and version information",
        example="CV Generator API"
    )
    version: str = Field(
        ...,
        description="API version",
        example="1.0.0"
    )

