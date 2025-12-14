"""Service to analyze job descriptions."""

import re
from typing import List, Set, Optional
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


class JobRequirements(BaseModel):
    """Structured job requirements extracted from JD."""
    
    role: Optional[str] = None
    company: Optional[str] = None
    summary: str
    technologies: List[str]
    requirements: List[str]
    responsibilities: List[str]
    industry_tags: List[str]
    min_years_experience: Optional[int] = None
    education_requirements: List[str] = []


class JobAnalyzer:
    """Analyze job descriptions to extract requirements."""
    
    # Common technology keywords
    TECH_KEYWORDS = [
        "python", "java", "javascript", "typescript", "go", "rust", "c++", "c#", "ruby",
        "react", "vue", "angular", "node.js", "spring boot", "django", "fastapi", "flask",
        "aws", "gcp", "azure", "docker", "kubernetes", "terraform", "ansible",
        "postgresql", "mysql", "mongodb", "redis", "elasticsearch",
        "machine learning", "deep learning", "ai", "ml", "nlp", "computer vision",
        "microservices", "rest api", "graphql", "grpc",
        "agile", "scrum", "ci/cd", "devops", "tdd", "bdd",
        "tensorflow", "pytorch", "scikit-learn", "pandas", "numpy",
        "kafka", "rabbitmq", "redis", "message queue",
        "git", "github", "gitlab", "jenkins", "github actions",
    ]
    
    # Common requirement patterns
    EXPERIENCE_PATTERNS = [
        r"(\d+)\+?\s*years?\s*of\s*experience",
        r"(\d+)\+?\s*años?\s*de\s*experiencia",
        r"minimum\s*(\d+)\s*years?",
        r"mínimo\s*(\d+)\s*años?",
    ]
    
    # Education patterns
    EDUCATION_PATTERNS = [
        r"bachelor.*(?:degree|science|engineering)",
        r"master.*(?:degree|science)",
        r"phd|doctorate",
        r"licenciatura",
        r"ingeniería",
        r"grado",
    ]
    
    async def analyze(self, job_description: str, role: Optional[str] = None) -> JobRequirements:
        """
        Analyze job description (text or URL).
        
        Args:
            job_description: Job description text or URL
            role: Target role name (optional)
            
        Returns:
            JobRequirements: Structured requirements
        """
        # If it's a URL, fetch and parse it
        if self._is_url(job_description):
            text = await self._fetch_url_content(job_description)
        else:
            text = job_description
        
        # Extract role if not provided
        if not role:
            role = self._extract_role(text)
        
        # Extract information
        technologies = self._extract_technologies(text)
        requirements = self._extract_requirements(text)
        responsibilities = self._extract_responsibilities(text)
        industry_tags = self._extract_industry_tags(text)
        min_years = self._extract_min_years(text)
        education_reqs = self._extract_education_requirements(text)
        
        return JobRequirements(
            role=role,
            summary=text[:500] + "..." if len(text) > 500 else text,
            technologies=technologies,
            requirements=requirements,
            responsibilities=responsibilities,
            industry_tags=industry_tags,
            min_years_experience=min_years,
            education_requirements=education_reqs,
        )
    
    def _extract_role(self, text: str) -> Optional[str]:
        """
        Extract job role/title from job description text.
        
        Args:
            text: Job description text
            
        Returns:
            Optional[str]: Extracted role or None
        """
        import re
        
        # Common patterns for job titles (English and Spanish)
        patterns = [
            # English patterns
            r'(?:looking for|seeking|hiring|we are looking for)\s+(?:a\s+)?([A-Z][a-zA-Z\s]+(?:Engineer|Developer|Architect|Manager|Lead|Specialist|Analyst|Consultant|Scientist))',
            r'([A-Z][a-zA-Z\s]+(?:Engineer|Developer|Architect|Manager|Lead|Specialist|Analyst|Consultant|Scientist))',
            # Spanish patterns
            r'(?:buscar|buscamos|estamos buscando|buscamos|se busca)\s+(?:un|una|el|la)?\s+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]{5,}(?:Ingeniero|Desarrollador|Arquitecto|Manager|Líder|Especialista|Analista|Consultor|Científico))',
            r'(?:puesto|posición|rol|trabajo|vacante)[:\s]+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]{5,})',
            # Generic patterns
            r'position[:\s]+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)',
            r'role[:\s]+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)',
            r'title[:\s]+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s]+)',
        ]
        
        text_lower = text.lower()
        for pattern in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                role = matches[0].strip()
                # Clean up role (remove extra words)
                role = re.sub(r'\s+', ' ', role)
                # Limit to reasonable length
                if len(role) < 100:
                    return role
        
        return None
    
    def _is_url(self, text: str) -> bool:
        """Check if text is a URL."""
        try:
            result = urlparse(text)
            return all([result.scheme, result.netloc])
        except Exception:
            return False
    
    async def _fetch_url_content(self, url: str) -> str:
        """
        Fetch and parse HTML content from URL.
        
        Args:
            url: URL to fetch
            
        Returns:
            str: Extracted text content
            
        Raises:
            httpx.HTTPError: If the URL cannot be fetched
            ValueError: If the content cannot be parsed
        """
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                # Add user agent to avoid blocking
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                }
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                
                # Check content type
                content_type = response.headers.get("content-type", "").lower()
                if "text/html" not in content_type and "text/plain" not in content_type:
                    # If not HTML, return as plain text
                    return response.text[:10000]  # Limit to first 10k chars
                
                soup = BeautifulSoup(response.text, "html.parser")
                
                # Remove script and style elements
                for script in soup(["script", "style", "nav", "footer", "header"]):
                    script.decompose()
                
                # Try to get main content from common semantic tags
                main_content = (
                    soup.find("main") or 
                    soup.find("article") or 
                    soup.find(class_=re.compile(r"content|description|job|posting", re.I)) or
                    soup.find(id=re.compile(r"content|description|job|posting", re.I)) or
                    soup.find("body")
                )
                
                if main_content:
                    text = main_content.get_text(separator="\n", strip=True)
                else:
                    text = soup.get_text(separator="\n", strip=True)
                
                # Clean up whitespace but preserve paragraph breaks
                text = re.sub(r'[ \t]+', ' ', text)  # Collapse spaces/tabs
                text = re.sub(r'\n{3,}', '\n\n', text)  # Max 2 newlines
                
                # Limit to reasonable length
                if len(text) > 50000:
                    text = text[:50000] + "... [truncated]"
                
                return text
        except httpx.TimeoutException as e:
            raise ValueError(f"Timeout fetching URL: {url}. The server took too long to respond.") from e
        except httpx.HTTPStatusError as e:
            raise ValueError(f"Failed to fetch URL: {url}. HTTP {e.response.status_code}") from e
        except Exception as e:
            raise ValueError(f"Error fetching URL {url}: {str(e)}") from e
    
    def _extract_technologies(self, text: str) -> List[str]:
        """Extract technology keywords from text."""
        text_lower = text.lower()
        found_techs = []
        
        for tech in self.TECH_KEYWORDS:
            if tech.lower() in text_lower:
                found_techs.append(tech)
        
        # Remove duplicates while preserving order
        seen = set()
        unique_techs = []
        for tech in found_techs:
            tech_lower = tech.lower()
            if tech_lower not in seen:
                seen.add(tech_lower)
                unique_techs.append(tech)
        
        return unique_techs
    
    def _extract_requirements(self, text: str) -> List[str]:
        """Extract key requirements from text."""
        # Look for bullet points or numbered lists
        lines = text.split('\n')
        requirements = []
        
        for line in lines:
            line = line.strip()
            # Match bullet points or numbered items
            if re.match(r'^[-*•]\s+|^\d+[.)]\s+', line):
                if len(line) > 20:  # Filter out very short lines
                    requirements.append(line)
            
            # Look for "required", "must have", etc.
            if any(keyword in line.lower() for keyword in ["required", "must have", "requisito", "debe tener"]):
                if len(line) > 20:
                    requirements.append(line)
        
        return requirements[:10]  # Limit to top 10
    
    def _extract_responsibilities(self, text: str) -> List[str]:
        """Extract key responsibilities from text."""
        # Similar to requirements but look for "responsibilities", "duties", etc.
        lines = text.split('\n')
        responsibilities = []
        
        in_responsibilities_section = False
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in ["responsibilities", "duties", "responsabilidades", "funciones"]):
                in_responsibilities_section = True
                continue
            
            if in_responsibilities_section:
                line = line.strip()
                if re.match(r'^[-*•]\s+|^\d+[.)]\s+', line):
                    if len(line) > 20:
                        responsibilities.append(line)
                elif line and not re.match(r'^[A-Z].*:$', line):  # Stop at next section header
                    if len(line) > 20:
                        responsibilities.append(line)
                    else:
                        break
        
        return responsibilities[:10]  # Limit to top 10
    
    def _extract_industry_tags(self, text: str) -> List[str]:
        """Extract industry/tag keywords from text."""
        industry_keywords = [
            "banking", "finance", "fintech", "bancario", "financiero",
            "retail", "e-commerce", "comercio", "retail",
            "healthcare", "health", "salud", "sanitario",
            "education", "educación", "edtech",
            "ai", "ml", "startup", "saas", "b2b", "b2c",
            "telecom", "telecomunicaciones",
            "government", "gobierno", "public sector",
        ]
        
        text_lower = text.lower()
        found_tags = []
        
        for keyword in industry_keywords:
            if keyword.lower() in text_lower:
                found_tags.append(keyword)
        
        return list(set(found_tags))  # Remove duplicates
    
    def _extract_min_years(self, text: str) -> Optional[int]:
        """Extract minimum years of experience requirement."""
        text_lower = text.lower()
        
        for pattern in self.EXPERIENCE_PATTERNS:
            match = re.search(pattern, text_lower, re.IGNORECASE)
            if match:
                years = int(match.group(1))
                return years
        
        return None
    
    def _extract_education_requirements(self, text: str) -> List[str]:
        """Extract education requirements from text."""
        text_lower = text.lower()
        education_reqs = []
        
        for pattern in self.EDUCATION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                education_reqs.append(pattern)
        
        return education_reqs

