"""FastAPI application for CV Generator."""

from io import BytesIO
from fastapi import FastAPI, HTTPException, status
from fastapi.responses import StreamingResponse
from app.models.request_models import (
    CVGenerateRequest,
    CVGenerateDynamicRequest,
    CoverLetterGenerateRequest,
    Language
)
from app.models.response_models import (
    ErrorResponse,
    HealthResponse,
    RootResponse
)
from app.services.cv_data_loader import get_data_loader
from app.services.pdf_generator import PDFGenerator
from app.services.cv_customizer import CVCustomizer
from app.services.cover_letter_generator import CoverLetterGenerator

app = FastAPI(
    title="CV Generator API",
    description="""API para generar CVs y cartas de presentación en PDF dinámicamente.

## Características

* **Generación estática de CV**: Genera CVs en PDF desde datos YAML (MVP)
* **Generación dinámica con LLM**: Personaliza CVs basándose en ofertas de trabajo usando IA
* **Cartas de presentación**: Genera cartas personalizadas adaptadas a la empresa
* **Soporte multiidioma**: Español e Inglés con detección automática
* **Integración con Ollama**: Utiliza modelos de lenguaje local para generación inteligente

## Uso

1. Usa `/api/v1/cv/generate` para generar CVs estáticos en español o inglés
2. Usa `/api/v1/cv/generate/dynamic` con una descripción del trabajo para generar un CV personalizado
3. Usa `/api/v1/cover-letter/generate` para generar cartas de presentación adaptadas""",
    version="1.0.0",
    contact={
        "name": "Álvaro Maldonado",
        "email": "alvaro@almapi.dev",
        "url": "https://almapi.dev"
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT"
    },
    terms_of_service="https://almapi.dev/terms",
    servers=[
        {
            "url": "http://localhost:8000",
            "description": "Local development server"
        }
    ],
    tags_metadata=[
        {
            "name": "health",
            "description": "Health check and status endpoints"
        },
        {
            "name": "cv",
            "description": "CV generation endpoints (static and dynamic)"
        },
        {
            "name": "cover-letter",
            "description": "Cover letter generation endpoints"
        }
    ]
)

# Initialize services
data_loader = get_data_loader()
pdf_generator = PDFGenerator()
cv_customizer = CVCustomizer()
cover_letter_generator = CoverLetterGenerator()


@app.get(
    "/",
    response_model=RootResponse,
    status_code=status.HTTP_200_OK,
    summary="Root endpoint",
    description="Returns API information including name and version",
    tags=["health"],
    responses={
        200: {
            "description": "API information",
            "content": {
                "application/json": {
                    "example": {
                        "message": "CV Generator API",
                        "version": "1.0.0"
                    }
                }
            }
        }
    }
)
async def root():
    """
    Root endpoint.
    
    Returns basic API information including name and version.
    """
    return RootResponse(message="CV Generator API", version="1.0.0")


@app.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Health check",
    description="Checks if the API service is running and healthy",
    tags=["health"],
    responses={
        200: {
            "description": "Service is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "ok"
                    }
                }
            }
        }
    }
)
async def health():
    """
    Health check endpoint.
    
    Returns the health status of the API service.
    Use this endpoint to verify the service is running correctly.
    """
    return HealthResponse(status="ok")


@app.post(
    "/api/v1/cv/generate",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate static CV",
    description="""
    Generates a static CV in PDF format from YAML data.
    
    This is the MVP endpoint that generates CVs using pre-defined data.
    Choose the language (Spanish or English) to generate the CV.
    """,
    tags=["cv"],
    responses={
        200: {
            "description": "CV PDF file",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Invalid input parameters",
            "model": ErrorResponse
        },
        404: {
            "description": "Not found - Language data file not found",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error",
            "model": ErrorResponse
        }
    }
)
async def generate_cv(request: CVGenerateRequest):
    """
    Generate static CV PDF.
    
    **Parameters:**
    - `language`: Language code (en for English, es for Spanish)
    
    **Returns:**
    - PDF file as binary stream with filename `CV_Alvaro_Maldonado_{language}.pdf`
    
    **Example:**
    ```json
    {
      "language": "en"
    }
    ```
    """
    try:
        # Load CV data for the requested language
        language = request.language.value
        cv_data = data_loader.load_cv_data(language)
        
        # Generate PDF
        pdf_bytes = pdf_generator.generate_pdf(cv_data, language)
        
        # Create filename based on language
        filename = f"CV_Alvaro_Maldonado_{language}.pdf"
        
        # Return PDF as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating CV: {str(e)}")


@app.post(
    "/api/v1/cv/generate/dynamic",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate dynamic CV with LLM",
    description="""
    Generates a personalized CV in PDF format using LLM based on job description.
    
    **Features:**
    - Automatically detects language from job description
    - Automatically extracts role/title from job description
    - Personalizes content based on job requirements
    - Adapts profile, experiences, and key skills to match the job
    - Supports both plain text and URLs as job description
    
    **Process:**
    1. Analyzes job description to extract requirements
    2. Detects language (Spanish or English)
    3. Extracts role/title
    4. Retrieves relevant experiences from portfolio
    5. Uses LLM to adapt and personalize content
    6. Generates optimized PDF (max 2 pages)
    """,
    tags=["cv"],
    responses={
        200: {
            "description": "Personalized CV PDF file",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            },
            "headers": {
                "X-CV-Generation-Mode": {
                    "description": "Generation mode indicator",
                    "schema": {
                        "type": "string",
                        "example": "llm"
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Invalid or missing job description",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error - LLM service or PDF generation failed",
            "model": ErrorResponse
        }
    }
)
async def generate_cv_dynamic(request: CVGenerateDynamicRequest):
    """
    Generate dynamic CV PDF using LLM.
    
    **Parameters:**
    - `job_description`: Job description as text or URL (required)
    
    **Returns:**
    - PDF file as binary stream with filename `CV_Dynamic_Alvaro_Maldonado.pdf`
    
    **Examples:**
    
    With plain text:
    ```json
    {
      "job_description": "We are looking for a Senior Backend Developer with Java and Spring Boot experience..."
    }
    ```
    
    With URL:
    ```json
    {
      "job_description": "https://example.com/job-posting"
    }
    ```
    
    **Note:** Generation typically takes 30-60 seconds due to LLM processing.
    """
    try:
        # Extract request parameters
        job_description = request.job_description
        
        # Validate required fields
        if not job_description:
            raise HTTPException(
                status_code=400,
                detail="job_description is required for dynamic CV generation"
            )
        
        # Generate dynamic CV (language and role will be auto-detected)
        pdf_bytes = await cv_customizer.generate_dynamic_cv(
            job_description=job_description
        )
        
        # Create filename (language will be detected during generation)
        filename = f"CV_Dynamic_Alvaro_Maldonado.pdf"
        
        # Return PDF as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-CV-Generation-Mode": "llm"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating dynamic CV: {str(e)}")


@app.post(
    "/api/v1/cover-letter/generate",
    response_class=StreamingResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate cover letter with LLM",
    description="""
    Generates a personalized cover letter in PDF format using LLM based on job description.
    
    **Features:**
    - Automatically detects language from job description
    - Automatically extracts role/title from job description
    - Researches company information using DuckDuckGo (if company name provided)
    - Adapts content to company culture (if company info available)
    - Mentions 2-3 most relevant experiences
    - Supports both plain text and URLs as job description
    - Maximum 1 page
    
    **Process:**
    1. Analyzes job description to extract requirements
    2. Detects language (Spanish or English)
    3. Extracts role/title
    4. Researches company information (if company provided)
    5. Retrieves top 2-3 relevant experiences
    6. Uses LLM to generate personalized cover letter
    7. Generates optimized PDF (1 page)
    """,
    tags=["cover-letter"],
    responses={
        200: {
            "description": "Personalized cover letter PDF file",
            "content": {
                "application/pdf": {
                    "schema": {
                        "type": "string",
                        "format": "binary"
                    }
                }
            },
            "headers": {
                "X-Cover-Letter-Generation-Mode": {
                    "description": "Generation mode indicator",
                    "schema": {
                        "type": "string",
                        "example": "llm"
                    }
                }
            }
        },
        400: {
            "description": "Bad request - Invalid or missing job description",
            "model": ErrorResponse
        },
        500: {
            "description": "Internal server error - LLM service or PDF generation failed",
            "model": ErrorResponse
        }
    }
)
async def generate_cover_letter(request: CoverLetterGenerateRequest):
    """
    Generate cover letter PDF using LLM.
    
    **Parameters:**
    - `job_description`: Job description as text or URL (required)
    - `company`: Company name (optional) - If provided, researches company info for better adaptation
    
    **Returns:**
    - PDF file as binary stream with filename `Cover_Letter_Alvaro_Maldonado.pdf`
    
    **Examples:**
    
    Without company:
    ```json
    {
      "job_description": "We are looking for a Senior Backend Developer..."
    }
    ```
    
    With company:
    ```json
    {
      "job_description": "We are looking for a Senior Backend Developer...",
      "company": "Tech Corp"
    }
    ```
    
    **Note:** Generation typically takes 20-60 seconds depending on whether company research is performed.
    """
    try:
        # Extract request parameters
        job_description = request.job_description
        company = request.company
        
        # Validate required fields
        if not job_description:
            raise HTTPException(
                status_code=400,
                detail="job_description is required for cover letter generation"
            )
        
        # Generate cover letter (language and role will be auto-detected)
        pdf_bytes = await cover_letter_generator.generate_cover_letter(
            job_description=job_description,
            company=company
        )
        
        # Create filename (language will be detected during generation)
        filename = f"Cover_Letter_Alvaro_Maldonado.pdf"
        
        # Return PDF as streaming response
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-Cover-Letter-Generation-Mode": "llm"
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating cover letter: {str(e)}")
