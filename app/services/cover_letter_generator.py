"""Service for generating cover letters using LLM."""

from datetime import datetime
from typing import Optional, Dict, List
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML as WeasyHTML, CSS
from app.models.portfolio_models import PortfolioData
from app.services.portfolio_loader import PortfolioLoader
from app.services.job_analyzer import JobAnalyzer, JobRequirements
from app.services.llm_service import LLMService
from app.services.web_research_service import WebResearchService


class CoverLetterGenerator:
    """Service for generating cover letters using LLM."""
    
    def __init__(self):
        """Initialize cover letter generator."""
        self.portfolio_loader = PortfolioLoader()
        self.job_analyzer = JobAnalyzer()
        self.llm_service = LLMService()
        self.web_research_service = WebResearchService()
        
        # Setup Jinja2 environment for cover letter template
        app_dir = Path(__file__).parent.parent
        template_dir = app_dir / "templates"
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=True
        )
    
    async def generate_cover_letter(
        self,
        job_description: str,
        company: Optional[str] = None
    ) -> bytes:
        """
        Generate cover letter PDF using LLM.
        Language and role are automatically detected from the job description.
        
        Args:
            job_description: Job description text or URL (language and role will be auto-detected)
            company: Company name (optional, if provided will research company info using DuckDuckGo)
            
        Returns:
            bytes: PDF content
        """
        if not job_description:
            raise ValueError("job_description is required for cover letter generation")
        
        try:
            # 1. Load portfolio data
            portfolio = self.portfolio_loader.load_portfolio()
            
            # 2. Detect language from job description
            language = await self._detect_language(job_description)
            
            # 3. Analyze job description (extracts role automatically)
            job_reqs = await self.job_analyzer.analyze(job_description)
            
            # 4. Research company using DuckDuckGo (if provided)
            company_info = None
            if company:
                try:
                    company_research = await self.web_research_service.research_company(company, job_reqs.role)
                    company_info = self.web_research_service.format_company_info(company_research)
                except Exception as e:
                    print(f"Warning: Company research failed: {e}, continuing without company info")
                    company_info = None
            
            # 5. Extract critical keywords BEFORE generation
            critical_keywords = self._extract_critical_keywords(job_reqs, portfolio)
            
            # 6. Get top relevant jobs (top 2-3 for cover letter)
            top_jobs = self._get_top_jobs_for_cover_letter(portfolio, job_reqs, max_jobs=3)
            
            # 7. Build keyword-focused experience context
            keyword_focused_experience = self._build_keyword_focused_context(
                top_jobs, critical_keywords, portfolio, job_reqs
            )
            
            # 8. Format job requirements with keyword emphasis
            formatted_job_reqs = self._format_job_reqs_with_keywords(job_reqs, critical_keywords)
            
            # 9. Generate cover letter content with LLM (with keyword emphasis)
            cover_letter_content = await self._generate_cover_letter_with_keywords(
                formatted_job_reqs,
                keyword_focused_experience,
                critical_keywords,
                company_info,
                language,
                portfolio
            )
            
            # 10. Format cover letter content as paragraphs
            formatted_content = self._format_cover_letter_content(cover_letter_content)
            
            # 11. Render HTML template
            html_content = self._render_template(
                portfolio, formatted_content, language, job_reqs.role, company
            )
            
            # 12. Generate PDF
            pdf_bytes = self._generate_pdf(html_content)
            
            return pdf_bytes
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate cover letter: {str(e)}") from e
    
    async def _detect_language(self, job_description: str) -> str:
        """
        Detect language from job description using LLM.
        
        Args:
            job_description: Job description text
            
        Returns:
            str: Language code ("en" or "es")
        """
        # Take first 1000 characters for language detection (more context = better detection)
        text_sample = job_description[:1000]
        
        # First, try simple heuristics (fast and reliable)
        text_lower = text_sample.lower()
        spanish_indicators = [
            "se busca", "buscamos", "estamos buscando", "requisitos", "experiencia", 
            "empresa", "ofrecemos", "buscamos", "perfil", "candidato", "trabajo",
            "desarrollo", "tecnología", "ingeniero", "arquitecto", "responsabilidades",
            "conocimientos", "formación", "titulación"
        ]
        english_indicators = [
            "we are looking", "looking for", "requirements", "experience", "company",
            "we offer", "candidate", "profile", "development", "technology", "engineer",
            "architect", "responsibilities", "knowledge", "education", "degree"
        ]
        
        spanish_count = sum(1 for indicator in spanish_indicators if indicator in text_lower)
        english_count = sum(1 for indicator in english_indicators if indicator in text_lower)
        
        # If heuristics are clear, use them (faster and more reliable)
        if spanish_count > english_count * 1.5:
            return "es"
        elif english_count > spanish_count * 1.5:
            return "en"
        
        # If unclear, use LLM for detection
        prompt = f"""Detecta el idioma del siguiente texto de descripción de trabajo.
Responde SOLO con una palabra: "en" para inglés o "es" para español.

Texto de descripción:
{text_sample}

Idioma:"""
        
        system = "Eres una herramienta de detección de idioma. Responde SOLO con 'en' o 'es'."
        
        try:
            response = await self.llm_service.generate(
                prompt=prompt,
                system=system,
                temperature=0.0,  # Minimum temperature for maximum determinism
                max_tokens=5
            )
            
            # Clean response and extract language
            response_clean = response.strip().lower()
            
            # Extract "en" or "es" from response
            if "es" in response_clean or "spanish" in response_clean or "español" in response_clean:
                return "es"
            elif "en" in response_clean or "english" in response_clean:
                return "en"
            else:
                # Default to Spanish if unclear (most job postings in Spain are in Spanish)
                return "es"
        except Exception:
            # Fallback: use heuristics result or default to Spanish
            if spanish_count >= english_count:
                return "es"
            else:
                return "en"
    
    def _get_top_jobs_for_cover_letter(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        max_jobs: int = 3
    ) -> list:
        """
        Get top relevant jobs for cover letter.
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            max_jobs: Maximum number of jobs to include
            
        Returns:
            List: Top relevant jobs
        """
        if not portfolio.jobs:
            return []
        
        # Score and rank jobs by relevance
        scored_jobs = []
        for job in portfolio.jobs:
            score = self._calculate_job_relevance_score(job, job_reqs)
            scored_jobs.append((score, job))
        
        # Sort by score (descending) and return top N
        scored_jobs.sort(key=lambda x: x[0], reverse=True)
        return [job for _, job in scored_jobs[:max_jobs]]
    
    def _calculate_job_relevance_score(self, job, job_reqs: JobRequirements) -> float:
        """
        Calculate relevance score for a job with improved matching.
        
        Args:
            job: Job from portfolio
            job_reqs: Job requirements
            
        Returns:
            float: Relevance score (0-1)
        """
        score = 0.0
        
        # Normalize technologies for comparison
        job_techs_lower = [t.lower() for t in (job.technologies if job.technologies else [])]
        req_techs_lower = [t.lower() for t in (job_reqs.technologies or [])]
        
        # CRITICAL: Industry tag matching (weight: 0.5 - HIGHEST PRIORITY)
        # If job requires "banca" or "banking", prioritize jobs with "industria_bancaria" tag
        if job.tags and job_reqs.industry_tags:
            job_tags_lower = [t.lower() for t in job.tags]
            req_tags_lower = [t.lower() for t in job_reqs.industry_tags]
            
            # Check for exact industry matches
            industry_matches = sum(1 for req_tag in req_tags_lower if req_tag in job_tags_lower)
            
            # Special handling for "banca" / "banking"
            if any('banca' in tag or 'banking' in tag for tag in req_tags_lower):
                if 'industria_bancaria' in job_tags_lower:
                    score += 0.5  # Strong industry match
                    industry_matches += 1
            
            if req_tags_lower:
                tag_score = (industry_matches / len(req_tags_lower)) * 0.5
                score += min(tag_score, 0.5)
        
        # CRITICAL: GenAI/LLM specific technology matching (weight: 0.4)
        # If job requires "GenAI", "LLM", "RAG", prioritize jobs with these technologies
        genai_keywords = ['genai', 'llm', 'llms', 'rag', 'langchain', 'huggingface', 'prompt engineering']
        req_has_genai = any(keyword in ' '.join(req_techs_lower) for keyword in genai_keywords)
        
        if req_has_genai:
            # Check if job has GenAI technologies
            job_has_genai = any(keyword in ' '.join(job_techs_lower) for keyword in genai_keywords)
            if job_has_genai:
                score += 0.4  # Strong GenAI match
            else:
                # Penalize non-GenAI jobs when GenAI is required
                score -= 0.2
        
        # Technology matching (weight: 0.3)
        tech_matches = 0
        for req_tech in req_techs_lower:
            if req_tech in job_techs_lower:
                tech_matches += 1
            else:
                # Check partial matches
                for job_tech in job_techs_lower:
                    if req_tech in job_tech or job_tech in req_tech:
                        tech_matches += 1
                        break
        
        if req_techs_lower:
            tech_score = (tech_matches / len(req_techs_lower)) * 0.3
            score += tech_score
        
        # Role matching (weight: 0.1)
        if job_reqs.role and job.role:
            role_lower = job_reqs.role.lower()
            job_role_lower = job.role.lower()
            
            role_keywords = ["senior", "lead", "tech lead", "architect", "cto", "engineer", "developer"]
            for keyword in role_keywords:
                if keyword in role_lower and keyword in job_role_lower:
                    score += 0.1
                    break
        
        # Description keyword matching (weight: 0.1)
        if job_reqs.summary and job.description:
            job_desc_lower = job.description.lower()
            req_summary_lower = job_reqs.summary.lower()
            
            req_words = set(req_summary_lower.split())
            job_words = set(job_desc_lower.split())
            
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            req_words = {w for w in req_words if w not in stop_words and len(w) > 3}
            job_words = {w for w in job_words if w not in stop_words and len(w) > 3}
            
            if req_words:
                common_words = req_words.intersection(job_words)
                word_score = (len(common_words) / len(req_words)) * 0.1
                score += min(word_score, 0.1)
        
        # Normalize score to 0-1 range
        return max(0.0, min(score, 1.0))
    
    def _format_jobs_for_llm(self, jobs: list) -> str:
        """Format jobs for LLM prompt."""
        parts = []
        
        for job in jobs:
            achievements_text = ', '.join(job.achievements[:3]) if job.achievements else 'N/A'
            parts.append(f"""
Job: {job.company} - {job.role}
Duration: {job.duration}
Location: {job.location}
Description: {job.description}
Key Achievements: {achievements_text}
Technologies: {', '.join(job.technologies[:10]) if job.technologies else 'N/A'}
""")
        
        return "\n".join(parts)
    
    def _extract_critical_keywords(
        self,
        job_reqs: JobRequirements,
        portfolio: PortfolioData
    ) -> Dict[str, List[str]]:
        """
        Extract critical keywords and match them to portfolio content.
        
        Returns:
            Dict with 'must_mention', 'industry', 'technologies', 'skills'
        """
        critical = {
            'must_mention': [],
            'industry': [],
            'technologies': [],
            'skills': []
        }
        
        # Extract from job requirements
        role_lower = (job_reqs.role or '').lower()
        summary_lower = (job_reqs.summary or '').lower()
        all_text = f"{role_lower} {summary_lower}"
        
        # Check for critical AI keywords
        ai_keywords = ['genai', 'llm', 'llms', 'rag', 'langchain', 'prompt engineering', 
                      'inteligencia artificial', 'ia', 'machine learning', 'ml']
        for keyword in ai_keywords:
            if keyword in all_text:
                critical['must_mention'].append(keyword.title())
        
        # Extract industry tags
        if job_reqs.industry_tags:
            critical['industry'] = job_reqs.industry_tags[:3]
        
        # Extract top technologies
        if job_reqs.technologies:
            critical['technologies'] = job_reqs.technologies[:5]
        
        # Extract skills from requirements summary
        skill_keywords = ['liderazgo', 'leadership', 'stakeholder', 'comunicación', 'communication',
                         'arquitectura', 'architecture', 'end-to-end', 'producción', 'production']
        for keyword in skill_keywords:
            if keyword in all_text:
                critical['skills'].append(keyword.title())
        
        return critical
    
    def _build_keyword_focused_context(
        self,
        top_jobs: list,
        critical_keywords: Dict[str, List[str]],
        portfolio: PortfolioData,
        job_reqs: JobRequirements
    ) -> str:
        """
        Build experience context that highlights keyword matches and includes explicit mapping instructions.
        """
        parts = []
        
        # Build explicit mapping instructions based on job requirements
        mapping_instructions = []
        
        # Check for industry requirements
        if job_reqs.industry_tags:
            industry_tags_lower = [t.lower() for t in job_reqs.industry_tags]
            if any('banca' in tag or 'banking' in tag for tag in industry_tags_lower):
                mapping_instructions.append(
                    "CRITICAL: La oferta requiere experiencia en BANCA. "
                    "DEBES priorizar proyectos con tag 'industria_bancaria' "
                    "(ej. Banco BCI, Banco de Chile, Transbank)."
                )
        
        # Check for GenAI requirements
        req_text = f"{job_reqs.role or ''} {job_reqs.summary or ''}".lower()
        genai_keywords = ['genai', 'llm', 'llms', 'rag', 'langchain', 'prompt engineering']
        if any(keyword in req_text for keyword in genai_keywords):
            mapping_instructions.append(
                "CRITICAL: La oferta requiere experiencia en GenAI/LLMs. "
                "DEBES buscar proyectos que contengan tecnologías como 'RAG', 'LLMs', 'LangChain', 'HuggingFace' "
                "en sus tecnologías (ej. proyectos relacionados con IA/ML)."
            )
        
        if mapping_instructions:
            parts.append("### MAPEO DE EVIDENCIA (LEE ESTO PRIMERO):")
            parts.append("\n".join(mapping_instructions))
            parts.append("")
        
        parts.append("### EXPERIENCIAS RELEVANTES:")
        
        for idx, job in enumerate(top_jobs, 1):
            # Find keyword matches in this job
            job_text = f"{job.description} {' '.join(job.achievements or [])}"
            job_text_lower = job_text.lower()
            
            matches = []
            for keyword_list in critical_keywords.values():
                for keyword in keyword_list:
                    if keyword.lower() in job_text_lower:
                        matches.append(keyword)
            
            # Highlight industry match
            industry_match = ""
            if job.tags:
                job_tags_lower = [t.lower() for t in job.tags]
                if job_reqs.industry_tags:
                    req_tags_lower = [t.lower() for t in job_reqs.industry_tags]
                    if any(req_tag in job_tags_lower for req_tag in req_tags_lower):
                        industry_match = " [INDUSTRY_MATCH]"
            
            # Highlight GenAI match
            genai_match = ""
            job_techs_lower = [t.lower() for t in (job.technologies or [])]
            if any(keyword in ' '.join(job_techs_lower) for keyword in genai_keywords):
                genai_match = " [GENAI_MATCH]"
            
            match_str = f"{industry_match}{genai_match} [RELEVANT: {', '.join(matches[:3])}]" if matches or industry_match or genai_match else ""
            
            achievements_text = ', '.join(job.achievements[:3]) if job.achievements else 'N/A'
            
            # Format technologies with emphasis on GenAI techs
            techs_list = job.technologies[:15] if job.technologies else []
            techs_str = ', '.join(techs_list)
            
            parts.append(f"""
PROYECTO {idx}: {job.company} - {job.role}{match_str}
Tags: {', '.join(job.tags) if job.tags else 'N/A'}
Descripción: {job.description}
Logros Clave: {achievements_text}
Tecnologías: {techs_str}
""")
        
        return "\n".join(parts)
    
    def _format_job_reqs_with_keywords(
        self,
        job_reqs: JobRequirements,
        critical_keywords: Dict[str, List[str]]
    ) -> str:
        """Format job requirements with keyword emphasis."""
        parts = []
        
        if job_reqs.role:
            parts.append(f"Role: {job_reqs.role}")
        
        if job_reqs.company:
            parts.append(f"Company: {job_reqs.company}")
        
        parts.append(f"Summary: {job_reqs.summary}")
        
        if critical_keywords.get('must_mention'):
            parts.append(f"CRITICAL KEYWORDS (MUST MENTION): {', '.join(critical_keywords['must_mention'])}")
        
        if critical_keywords.get('industry'):
            parts.append(f"Industry: {', '.join(critical_keywords['industry'])}")
        
        if job_reqs.technologies:
            parts.append(f"Technologies: {', '.join(job_reqs.technologies[:10])}")
        
        return "\n".join(parts)
    
    def _format_job_reqs(self, job_reqs: JobRequirements) -> str:
        """Format job requirements for LLM prompt (legacy method, kept for compatibility)."""
        parts = []
        
        if job_reqs.role:
            parts.append(f"Role: {job_reqs.role}")
        
        if job_reqs.company:
            parts.append(f"Company: {job_reqs.company}")
        
        parts.append(f"Summary: {job_reqs.summary}")
        
        if job_reqs.technologies:
            parts.append(f"Technologies: {', '.join(job_reqs.technologies[:10])}")
        
        return "\n".join(parts)
    
    async def _generate_cover_letter_with_keywords(
        self,
        formatted_job_reqs: str,
        keyword_focused_experience: str,
        critical_keywords: Dict[str, List[str]],
        company_info: Optional[str],
        language: str,
        portfolio: PortfolioData
    ) -> str:
        """
        Generate cover letter with explicit keyword emphasis following the 5-part structure.
        """
        must_mention = ', '.join(critical_keywords.get('must_mention', []))
        industry = ', '.join(critical_keywords.get('industry', []))
        
        # Extract main keyword from job requirements (for Section 1)
        main_keyword = must_mention.split(',')[0].strip() if must_mention else ''
        if not main_keyword and formatted_job_reqs:
            # Try to extract from role or summary
            if 'Role:' in formatted_job_reqs:
                main_keyword = formatted_job_reqs.split('Role:')[1].split('\n')[0].strip()[:50]
        
        # Extract philosophy_and_interests for Section 3
        philosophy_text = ""
        if portfolio.professional_summary and hasattr(portfolio.professional_summary, 'philosophy_and_interests'):
            philosophy_items = portfolio.professional_summary.philosophy_and_interests or []
            if philosophy_items:
                # Use the first philosophy item (Product Engineer)
                first_philosophy = philosophy_items[0]
                philosophy_text = f"{first_philosophy.title}: {first_philosophy.description}"
        
        if language == "en":
            prompt = f"""Write a professional cover letter that demonstrates alignment with the job requirements.

### CRITICAL REQUIREMENTS (MUST INCLUDE):
1. **Mention these keywords at least once:** {must_mention if must_mention else 'None specific'}
2. **Emphasize industry experience:** {industry if industry else 'General tech'}
3. **Use ONLY data from provided portfolio** - DO NOT invent anything

### STRUCTURE (Write 4 natural paragraphs, DO NOT mention section numbers or labels):

**Paragraph 1 - Opening Hook (2-3 sentences):**
Start by stating your intent: Mention the exact [ROLE] and where you saw it. Immediately present your "value proposition": Connect your profile (Senior, Product Engineer, AI Specialist) with the main keyword from the job description: "{main_keyword}". This paragraph should answer "Who are you and what do you want?" - Establish the premise naturally.

**Paragraph 2 - Technical Evidence (3-4 sentences):**
**CRITICAL - EVIDENCE MAPPING:** Before writing, review [EVIDENCE_MAPPING] in [RELEVANT_EXPERIENCE]. If the offer requires "Banking", you MUST use projects with tag "industria_bancaria". If the offer requires "GenAI/LLMs", you MUST use projects with technologies like "RAG", "LLMs", "LangChain" in their technologies. DO NOT invent technologies that are not in the project's technology list. Scan the [JOB_REQUIREMENTS] for 2-3 critical technical requirements (e.g., "GenAI experience", "AWS", "Java", "Microservices"). Extract the PROOF (achievements or description) from the CORRECT project in [RELEVANT_EXPERIENCE] that demonstrates this skill. Use a natural structure like: "The offer highlights the need for [keyword from JD]. My specialization focuses precisely on this: I have [specific achievement from RELEVANT_EXPERIENCE using ONLY technologies that appear in the technology list]". This paragraph should answer "Can you do the job?" - Provide factual proof naturally.

**Paragraph 3 - Strategic Differentiator (2-3 sentences):**
Scan the [JOB_REQUIREMENTS] for VALUES or SOFT SKILLS (e.g., "business vision", "stakeholder communication", "solving complex problems", "innovation"). Connect those values with your [PHILOSOPHY_AND_INTERESTS]. Use a natural structure like: "Beyond technology, your search for [value keyword from JD] resonates with my core philosophy: [extract from PHILOSOPHY_AND_INTERESTS]". This paragraph should answer "Why are YOU better than others?" - Show maturity and strategic vision naturally.

**Paragraph 4 - Closing and Logistics (2-3 sentences):**
Use a confident closing phrase (e.g., "I am convinced that my hybrid profile (Engineering + AI + Product) can be a valuable asset..."). **CRITICAL:** Include the logistics naturally: "As part of my search for a strategic role in Spain, my conditions are a **100% remote role** and **PAC visa sponsorship**." End with a professional CTA: "I appreciate your time and remain available to discuss how I can contribute to [COMPANY]."

### CRITICAL INSTRUCTIONS:
- Write ONLY the 4 body paragraphs (no greeting, no signature, no section labels)
- **CRITICAL:** Each paragraph MUST be separated by a blank line (double newline: \n\n)
- **CRITICAL:** Write each paragraph on its own, then leave a blank line before the next paragraph
- DO NOT include labels like "Section 1", "SECCIÓN 1", "**SECTION 1**", etc.
- Write naturally as if you wrote this yourself, not generated by AI
- Each paragraph should flow naturally into the next
- Paragraph 1: 2-3 sentences
- Paragraph 2: 3-4 sentences  
- Paragraph 3: 2-3 sentences
- Paragraph 4: 2-3 sentences (INCLUDE the logistics about remote work and PAC visa)
- Mention critical keywords naturally (not forced)
- Total length: ~300-400 words
- Maximum 4 paragraphs

### OUTPUT FORMAT EXAMPLE (CRITICAL - FOLLOW THIS EXACTLY):
Me dirijo a usted con la intención de presentar mi perfil como [ROLE]. Como Senior Product Engineer y Especialista en IA, estoy convencido de que puedo contribuir al éxito de su empresa.

La oferta destaca la necesidad de [keyword]. Mi especialización se centra precisamente en esto: he [logro específico] que demuestra mi experiencia en [tecnología].

Más allá de la tecnología, su búsqueda de [valor] resuena con mi filosofía central como Product Engineer: mi prioridad es entender el 'porqué' del negocio para diseñar la solución correcta.

Estoy convencido de que mi perfil híbrido puede ser un activo valioso. Como parte de mi búsqueda de un rol estratégico en España, mis condiciones son un rol **100% remoto** y el **patrocinio del visado PAC**. Agradezco su tiempo y quedo a su disposición.

### CRITICAL_KEYWORDS (MUST MENTION):
{must_mention if must_mention else 'None specific - use general tech terms'}

### MAIN_KEYWORD (for Paragraph 1):
{main_keyword if main_keyword else 'Use the most prominent keyword from job requirements'}

### INDUSTRY CONTEXT:
{industry if industry else 'General technology industry'}

### TARGET ROLE:
{formatted_job_reqs}

### COMPANY INFORMATION:
{company_info if company_info else 'N/A'}

### RELEVANT_EXPERIENCE:
{keyword_focused_experience}

### PHILOSOPHY_AND_INTERESTS:
{philosophy_text if philosophy_text else 'N/A - focus on Product Engineer mindset and strategic thinking'}"""

            system = "You are an expert cover letter writer. Write naturally as if you wrote this yourself. DO NOT include section labels or numbers. Write 4 DISTINCT paragraphs, each separated by a blank line (double newline). Follow the structure but make it flow naturally. Mention critical keywords naturally. Use ONLY provided portfolio data."
        else:
            prompt = f"""IMPORTANTE: DEBES ESCRIBIR TODO EL CONTENIDO EN ESPAÑOL. NO uses inglés en ningún momento.

Escribe una carta de presentación profesional que demuestre alineación con los requisitos del trabajo.

### REQUISITOS CRÍTICOS (DEBES INCLUIR):
1. **Menciona estas palabras clave al menos una vez:** {must_mention if must_mention else 'Ninguna específica'}
2. **Enfatiza experiencia en industria:** {industry if industry else 'Tecnología general'}
3. **Usa SOLO datos del portfolio proporcionado** - NO inventes nada
4. **ESCRIBE TODO EN ESPAÑOL** - No uses inglés en ningún momento

### ESTRUCTURA (Escribe 4 párrafos naturales, NO menciones números de sección o etiquetas):

**Párrafo 1 - Apertura Gancho (2-3 oraciones):**
Comienza declarando tu intención: Menciona el [ROL] exacto y dónde lo viste. Inmediatamente presenta tu "propuesta de valor": Conecta tu perfil (Senior, Product Engineer, Especialista en IA) con la palabra clave principal de la oferta: "{main_keyword}". Este párrafo debe responder "¿Quién eres y qué quieres?" - Establece la premisa de forma natural.

**Párrafo 2 - Evidencia Técnica (3-4 oraciones):**
**CRÍTICO - MAPEO DE EVIDENCIA:** Antes de escribir, revisa [MAPEO_DE_EVIDENCIA] en [EXPERIENCIA_RELEVANTE]. Si la oferta requiere "Banca", DEBES usar proyectos con tag "industria_bancaria". Si la oferta requiere "GenAI/LLMs", DEBES usar proyectos con tecnologías como "RAG", "LLMs", "LangChain" en sus tecnologías. NO inventes tecnologías que no están en la lista de tecnologías del proyecto. Escanea los [REQUISITOS_DEL_TRABAJO] en busca de 2-3 requisitos técnicos clave (ej. "experiencia en GenAI", "AWS", "Java", "Microservicios"). Extrae la PRUEBA (achievements o description) del proyecto CORRECTO de [EXPERIENCIA_RELEVANTE] que demuestre esa habilidad. Usa una estructura natural como: "La oferta destaca la necesidad de [keyword del JD]. Mi especialización se centra precisamente en esto: he [logro específico de EXPERIENCIA_RELEVANTE usando SOLO tecnologías que aparecen en la lista de tecnologías]". Este párrafo debe responder "¿Puedes hacer el trabajo?" - Proporciona prueba fáctica de forma natural.

**Párrafo 3 - Diferenciador Estratégico (2-3 oraciones):**
Escanea los [REQUISITOS_DEL_TRABAJO] en busca de VALORES o SOFT SKILLS (ej. "visión de negocio", "comunicación con stakeholders", "resolver problemas complejos", "innovación"). Conecta esos valores con tu [FILOSOFÍA_E_INTERESES]. Usa una estructura natural como: "Más allá de la tecnología, su búsqueda de [valor keyword del JD] resuena con mi filosofía central: [extrae de FILOSOFÍA_E_INTERESES]". Este párrafo debe responder "¿Por qué TÚ eres mejor que los demás?" - Muestra madurez y visión estratégica de forma natural.

**Párrafo 4 - Cierre y Logística (2-3 oraciones):**
Usa una frase de cierre segura (ej. "Estoy convencido de que mi perfil híbrido (Ingeniería + IA + Producto) puede ser un activo valioso..."). **CRÍTICO:** Incluye la logística de forma natural: "Como parte de mi búsqueda de un rol estratégico en España, mis condiciones son un rol **100% remoto** y el **patrocinio del visado PAC**." Termina con un CTA profesional: "Agradezco su tiempo y quedo a su disposición para discutir cómo puedo contribuir a [EMPRESA]."

### INSTRUCCIONES CRÍTICAS:
- Escribe SOLO los 4 párrafos del cuerpo (sin saludo, sin firma, sin etiquetas de sección)
- **CRÍTICO:** Cada párrafo DEBE estar separado por una línea en blanco (doble salto de línea: \n\n)
- **CRÍTICO:** Escribe cada párrafo por su cuenta, luego deja una línea en blanco antes del siguiente párrafo
- NO incluyas etiquetas como "Sección 1", "SECCIÓN 1", "**SECCIÓN 1**", etc.
- Escribe de forma natural como si lo hubieras escrito tú mismo, no generado por IA
- Cada párrafo debe fluir naturalmente hacia el siguiente
- Párrafo 1: 2-3 oraciones
- Párrafo 2: 3-4 oraciones
- Párrafo 3: 2-3 oraciones
- Párrafo 4: 2-3 oraciones (INCLUYE la logística sobre trabajo remoto y visado PAC)
- Escribe TODO en ESPAÑOL. NO uses inglés.
- Menciona palabras clave críticas naturalmente (no forzado)
- Máximo 4 párrafos
- Longitud total: ~300-400 palabras

### FORMATO DE SALIDA EJEMPLO (CRÍTICO - SIGUE ESTO EXACTAMENTE):
Me dirijo a usted con la intención de presentar mi perfil como [ROL]. Como Senior Product Engineer y Especialista en IA, estoy convencido de que puedo contribuir al éxito de su empresa.

La oferta destaca la necesidad de [keyword]. Mi especialización se centra precisamente en esto: he [logro específico] que demuestra mi experiencia en [tecnología].

Más allá de la tecnología, su búsqueda de [valor] resuena con mi filosofía central como Product Engineer: mi prioridad es entender el 'porqué' del negocio para diseñar la solución correcta.

Estoy convencido de que mi perfil híbrido puede ser un activo valioso. Como parte de mi búsqueda de un rol estratégico en España, mis condiciones son un rol **100% remoto** y el **patrocinio del visado PAC**. Agradezco su tiempo y quedo a su disposición.

### PALABRAS_CLAVE_CRÍTICAS (DEBES MENCIONAR):
{must_mention if must_mention else 'Ninguna específica - usa términos técnicos generales'}

### PALABRA_CLAVE_PRINCIPAL (para Párrafo 1):
{main_keyword if main_keyword else 'Usa la palabra clave más prominente de los requisitos del trabajo'}

### CONTEXTO DE INDUSTRIA:
{industry if industry else 'Industria de tecnología general'}

### ROL OBJETIVO:
{formatted_job_reqs}

### INFORMACIÓN DE LA EMPRESA:
{company_info if company_info else 'N/A'}

### EXPERIENCIA_RELEVANTE:
{keyword_focused_experience}

### FILOSOFÍA_E_INTERESES:
{philosophy_text if philosophy_text else 'N/A - enfócate en mentalidad de Product Engineer y pensamiento estratégico'}"""

            system = "Eres un redactor experto de cartas de presentación en español. DEBES escribir TODO en ESPAÑOL. Escribe de forma natural como si lo hubieras escrito tú mismo. NO incluyas etiquetas de sección ni números. Escribe 4 PÁRRAFOS DISTINTOS, cada uno separado por una línea en blanco (doble salto de línea). Sigue la estructura pero haz que fluya naturalmente. Menciona palabras clave críticas naturalmente. Usa SOLO datos del portfolio proporcionado. NO uses inglés en ningún momento."
        
        return await self.llm_service.generate(
            prompt=prompt,
            system=system,
            temperature=0.4,  # Lower than before for more focused output
            max_tokens=1200
        )
    
    def _format_cover_letter_content(self, content: str) -> str:
        """
        Format cover letter content into HTML paragraphs.
        Also removes any placeholders that the LLM might have included.
        
        Args:
            content: Raw LLM-generated content
            
        Returns:
            str: HTML-formatted content with paragraphs
        """
        import re
        
        # Remove section labels that might appear in the text
        section_patterns = [
            r'\*\*SECCI[ÓO]N\s*\d+\*\*',
            r'\*\*SECTION\s*\d+\*\*',
            r'SECCI[ÓO]N\s*\d+',
            r'SECTION\s*\d+',
            r'\*\*Sección\s*\d+\*\*',
            r'\*\*Section\s*\d+\*\*',
        ]
        
        for pattern in section_patterns:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove common placeholders that LLM might generate
        placeholders = [
            r'\[Date\]', r'\[DATE\]', r'\[Fecha\]', r'\[FECHA\]', r'\[date\]', r'\[fecha\]',
            r'\[Your Name\]', r'\[YOUR NAME\]', r'\[Tu nombre\]', r'\[TU NOMBRE\]', r'\[tu nombre\]',
            r'\[Your Address\]', r'\[YOUR ADDRESS\]', r'\[Tu dirección\]', r'\[TU DIRECCIÓN\]', r'\[tu dirección\]',
            r'\[City, Country\]', r'\[CITY, COUNTRY\]', r'\[Ciudad, País\]', r'\[CIUDAD, PAÍS\]', r'\[ciudad, país\]',
            r'\[Email Address\]', r'\[EMAIL ADDRESS\]', r'\[Correo electrónico\]', r'\[CORREO ELECTRÓNICO\]', r'\[correo electrónico\]',
            r'\[Phone Number\]', r'\[PHONE NUMBER\]', r'\[Teléfono\]', r'\[TELÉFONO\]', r'\[teléfono\]',
            r'Dear\s+\[Hiring Manager\]', r'Estimado\s+\[Gerente de RRHH\]', r'Estimado\s+\[Gerente\]',
            r'Dear\s+\[.*?\]', r'Estimado\s+\[.*?\]', r'Querido\s+\[.*?\]',
            r'^Saludos\s+cordiales,?\s*$', r'^Best\s+regards,?\s*$', r'^Atentamente,?\s*$',
            r'^Cordialmente,?\s*$', r'^Sincerely,?\s*$', r'^Respetuosamente,?\s*$',
        ]
        
        for pattern in placeholders:
            content = re.sub(pattern, '', content, flags=re.IGNORECASE | re.MULTILINE)
        
        # Remove lines containing "None" at the start
        lines_clean = []
        for line in content.split('\n'):
            line_stripped = line.strip()
            # Skip empty lines, "None", and closing signatures
            if (line_stripped and 
                not line_stripped.lower().startswith('none') and
                line_stripped.lower() not in ['saludos cordiales', 'best regards', 'atentamente', 'sincerely', 'cordialmente', 'respetuosamente']):
                lines_clean.append(line)
        content = '\n'.join(lines_clean)
        
        # Split by double newlines or single newlines followed by capital letter
        paragraphs = []
        current_paragraph = []
        
        lines = content.split('\n')
        
        for line in lines:
            line = line.strip()
            # Skip empty lines
            if not line:
                if current_paragraph:
                    paragraphs.append(' '.join(current_paragraph))
                    current_paragraph = []
            else:
                # Skip lines that look like placeholders
                line_lower = line.lower()
                skip_patterns = [
                    '[date]', '[your name]', '[your address]', '[email]', '[phone]',
                    '[tu nombre]', '[tu dirección]', '[correo]', '[teléfono]', 'none'
                ]
                
                # Skip if line is just a section label (standalone)
                if re.match(r'^(\*\*)?(SECCI[ÓO]N|SECTION)\s*\d+(\*\*)?\s*$', line.strip(), re.IGNORECASE):
                    continue
                    
                if not any(pattern in line_lower for pattern in skip_patterns):
                    current_paragraph.append(line)
        
        if current_paragraph:
            paragraphs.append(' '.join(current_paragraph))
        
        # If we only have 1 paragraph but it's long, try to split it intelligently
        if len(paragraphs) == 1 and len(paragraphs[0]) > 500:
            # Try to split by section markers first
            single_text = paragraphs[0]
            
            # Remove section labels if they exist
            single_text = re.sub(r'\*\*SECCI[ÓO]N\s*\d+\*\*', '', single_text, flags=re.IGNORECASE)
            single_text = re.sub(r'SECCI[ÓO]N\s*\d+', '', single_text, flags=re.IGNORECASE)
            
            # Try to split by sentence patterns that indicate new paragraphs
            # Look for patterns like "La oferta destaca" (start of paragraph 2)
            # or "Más allá de la tecnología" (start of paragraph 3)
            # or "Estoy convencido" (start of paragraph 4)
            
            # Split by common paragraph starters
            paragraph_starters = [
                r'(\.\s+)(La oferta destaca|Mi experiencia|He liderado|En este proyecto)',
                r'(\.\s+)(Más allá de la tecnología|Su búsqueda|Además)',
                r'(\.\s+)(Estoy convencido|Como parte de|Agradezco)',
            ]
            
            # Try to split intelligently
            splits = []
            for pattern in paragraph_starters:
                matches = list(re.finditer(pattern, single_text, re.IGNORECASE))
                if matches:
                    splits.extend([m.start() + len(m.group(1)) for m in matches])
            
            if splits:
                splits = sorted(set(splits))
                # Split the text at these points
                prev = 0
                new_paragraphs = []
                for split_point in splits:
                    if split_point > prev:
                        new_paragraphs.append(single_text[prev:split_point].strip())
                        prev = split_point
                if prev < len(single_text):
                    new_paragraphs.append(single_text[prev:].strip())
                
                if len(new_paragraphs) >= 2:
                    paragraphs = [p for p in new_paragraphs if p]
        
        # Ensure we have at least 4 paragraphs (split further if needed)
        if len(paragraphs) < 4 and len(paragraphs) > 0:
            # If we have fewer than 4 paragraphs, try to split the longest ones
            # Split by sentences
            all_paragraphs = []
            for para in paragraphs:
                sentences = re.split(r'(?<=[.!?])\s+', para)
                if len(sentences) > 4:
                    # Split into chunks of 2-3 sentences
                    chunk_size = max(2, len(sentences) // 2)
                    for i in range(0, len(sentences), chunk_size):
                        chunk = ' '.join(sentences[i:i+chunk_size]).strip()
                        if chunk:
                            all_paragraphs.append(chunk)
                else:
                    all_paragraphs.append(para)
            
            paragraphs = all_paragraphs[:4]  # Limit to 4 paragraphs
        
        # Wrap each paragraph in <p> tags
        formatted = '\n'.join([f'<p>{p}</p>' for p in paragraphs if p])
        
        return formatted
    
    def _render_template(
        self,
        portfolio: PortfolioData,
        cover_letter_content: str,
        language: str,
        role: Optional[str] = None,
        company: Optional[str] = None
    ) -> str:
        """Render cover letter HTML template."""
        template = self.env.get_template("cover_letter_template.html")
        
        # Get current date (Spanish month names)
        if language == "en":
            current_date = datetime.now().strftime("%B %d, %Y")
        else:
            month_names_es = {
                1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
                7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
            }
            now = datetime.now()
            current_date = f"{now.day} de {month_names_es[now.month]} de {now.year}"
        
        html = template.render(
            data=portfolio,
            cover_letter_content=cover_letter_content,
            language=language,
            job_role=role,
            company=company,
            current_date=current_date
        )
        
        return html
    
    def _generate_pdf(self, html_content: str) -> bytes:
        """Generate PDF from HTML content."""
        html = WeasyHTML(string=html_content)
        
        # Configure PDF settings (A4, portrait, margins)
        page_css = CSS(string="""
            @page {
                size: A4;
                margin: 18px;
            }
        """)
        
        # Generate PDF
        pdf_bytes = html.write_pdf(stylesheets=[page_css])
        
        return pdf_bytes

