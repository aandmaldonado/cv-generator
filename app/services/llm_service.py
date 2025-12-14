"""Service for LLM integration with Ollama."""

import os
from typing import Optional, Dict, Any
import httpx
from pydantic_settings import BaseSettings


class OllamaSettings(BaseSettings):
    """Ollama configuration settings."""
    
    ollama_base_url: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3:8b")
    ollama_timeout: int = int(os.getenv("OLLAMA_TIMEOUT", "60"))
    ollama_api_key: Optional[str] = os.getenv("OLLAMA_API_KEY", None)
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        extra = "ignore"  # Ignore extra fields from .env (like PHONE_NUMBER)


class LLMService:
    """Service for interacting with Ollama LLM."""
    
    def __init__(self, settings: Optional[OllamaSettings] = None):
        """
        Initialize LLM service.
        
        Args:
            settings: Ollama settings (uses defaults if None)
        """
        self.settings = settings or OllamaSettings()
        self.base_url = self.settings.ollama_base_url.rstrip("/")
        self.model = self.settings.ollama_model
        self.timeout = self.settings.ollama_timeout
        self.api_key = self.settings.ollama_api_key
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """
        Generate text using Ollama.
        
        Args:
            prompt: User prompt
            system: System prompt (optional)
            temperature: Temperature for generation (0.0-1.0)
            max_tokens: Maximum tokens to generate (optional)
            
        Returns:
            str: Generated text
            
        Raises:
            httpx.HTTPError: If request fails
        """
        url = f"{self.base_url}/api/generate"
        
        payload: Dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
            }
        }
        
        if system:
            payload["system"] = system
        
        if max_tokens:
            payload["options"]["num_predict"] = max_tokens
        
        # Prepare headers (add API key if provided)
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload, headers=headers)
                response.raise_for_status()
                result = response.json()
                
                # Extract response text
                if "response" in result:
                    return result["response"]
                else:
                    raise ValueError(f"Unexpected response format: {result}")
            except httpx.TimeoutException as e:
                raise TimeoutError(f"Ollama request timed out after {self.timeout}s") from e
            except httpx.HTTPError as e:
                raise RuntimeError(f"Failed to communicate with Ollama: {str(e)}") from e
    
    async def generate_cv_content(
        self,
        filtered_experience: str,
        job_reqs: str,
        company_info: Optional[str] = None,
        language: str = "en"
    ) -> str:
        """
        Generate CV content using LLM.
        
        Args:
            filtered_experience: Filtered experience data as text/JSON
            job_reqs: Job requirements summary
            company_info: Company information (optional)
            language: Language for output (en/es)
            
        Returns:
            str: Generated CV content (structured text or JSON)
        """
        system_prompt = (
            "You are an expert CV writer. You MUST use ONLY the information provided. "
            "DO NOT invent any data. All experiences, achievements, and technologies "
            "must come from the provided portfolio data."
        )
        
        user_prompt = f"""
Generate a personalized CV content based on the following information.

Job Requirements:
{job_reqs}

{'Company Information:' + company_info if company_info else ''}

Available Experience Data (USE ONLY THIS):
{filtered_experience}

Language: {language}

Instructions:
1. Create a professional CV summary/profile highlighting relevant skills and experience
2. Rewrite achievements to emphasize relevance to the job role
3. Select and prioritize the most relevant technologies from the provided list
4. USE ONLY data from the provided portfolio - DO NOT invent anything
5. Output format: Structured text ready for CV integration

Output the CV content in {language.upper()}.
"""
        
        return await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.5,  # Lower temperature for more factual output
            max_tokens=2000
        )
    
    async def generate_cover_letter(
        self,
        filtered_experience: str,
        job_reqs: str,
        company_info: Optional[str] = None,
        language: str = "en"
    ) -> str:
        """
        Generate cover letter using LLM.
        
        Args:
            filtered_experience: Filtered experience data (top 2-3 projects)
            job_reqs: Job requirements summary
            company_info: Company information (optional)
            language: Language for output (en/es)
            
        Returns:
            str: Generated cover letter text
        """
        system_prompt = (
            "You are an expert cover letter writer. You MUST use ONLY the information provided. "
            "DO NOT invent any data. All experiences, achievements, and projects "
            "must come from the provided portfolio data."
        )
        
        if language == "en":
            user_prompt = f"""Write a professional cover letter based on the following information.

CRITICAL RULES:
1. DO NOT use placeholders like [Date], [Your Name], [Your Address], [City, Country], [Email Address], [Phone Number], [Tu nombre]
2. DO NOT include header information (name, address, date) - that is handled by the template
3. DO NOT include salutations like "Dear [Hiring Manager]" - just start with the body
4. Write ONLY the body paragraphs of the cover letter (3-4 paragraphs)
5. Maximum 1 page when formatted
6. USE ONLY data from the provided portfolio - DO NOT invent anything

Target Role: {job_reqs}

{'Company Information:' + company_info if company_info else ''}

Relevant Experience (USE ONLY THIS):
{filtered_experience}

Instructions:
1. Start directly with an engaging opening paragraph (no greeting, no date, no header)
2. Mention 2-3 most relevant experiences from the provided data
3. Demonstrate alignment with the job requirements
4. Show enthusiasm for the role and company (if company_info is provided)
5. End with a professional closing paragraph (but no signature - that's in the template)

Write ONLY the body paragraphs. Output in English."""
        else:
            user_prompt = f"""Escribe una carta de presentación profesional basada en la siguiente información.

REGLAS CRÍTICAS:
1. NO uses placeholders como [Fecha], [Tu nombre], [Tu dirección], [Ciudad, País], [Correo electrónico], [Teléfono]
2. NO incluyas información de encabezado (nombre, dirección, fecha) - eso lo maneja el template
3. NO incluyas saludos como "Estimado [Gerente de RRHH]" - simplemente comienza con el cuerpo
4. Escribe SOLO los párrafos del cuerpo de la carta (3-4 párrafos)
5. Máximo 1 página cuando se formatea
6. Usa SOLO datos del portfolio proporcionado - NO inventes nada

Rol objetivo: {job_reqs}

{'Información de la empresa:' + company_info if company_info else ''}

Experiencia relevante (USA SOLO ESTO):
{filtered_experience}

Instrucciones:
1. Comienza directamente con un párrafo inicial atractivo (sin saludo, sin fecha, sin encabezado)
2. Menciona 2-3 experiencias más relevantes de los datos proporcionados
3. Demuestra alineación con los requisitos del trabajo
4. Muestra entusiasmo por el rol y la empresa (si se proporciona company_info)
5. Termina con un párrafo de cierre profesional (pero sin firma - eso está en el template)

Escribe SOLO los párrafos del cuerpo. Salida en español."""
        
        return await self.generate(
            prompt=user_prompt,
            system=system_prompt,
            temperature=0.4,  # Lowered from 0.6 for more focused output
            max_tokens=1200  # Reduced from 1500 for more concise output
        )

