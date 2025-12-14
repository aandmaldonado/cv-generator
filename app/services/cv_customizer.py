"""Service to customize CV using LLM based on job requirements."""

import asyncio
import hashlib
import json
import re
from typing import Dict, List, Optional, Tuple
from app.models.portfolio_models import PortfolioData
from app.models.cv_models import CVData, CVExperience, CVContact, CVEducation, CVLanguage, TechSkillCategory
from app.services.portfolio_loader import PortfolioLoader
from app.services.job_analyzer import JobAnalyzer, JobRequirements
from app.services.llm_service import LLMService
from app.services.cv_generator import CVGenerator
from app.services.pdf_generator import PDFGenerator


class CVCustomizer:
    """Orchestrator for dynamic CV customization using LLM."""
    
    def __init__(self):
        """Initialize CV customizer with required services."""
        self.portfolio_loader = PortfolioLoader()
        self.job_analyzer = JobAnalyzer()
        self.llm_service = LLMService()
        # Initialize web research service (can be disabled via ENABLE_WEB_SEARCH=false)
        self.cv_generator = CVGenerator()
        self.pdf_generator = PDFGenerator()
        # Cache for translations and adaptations
        self._translation_cache: Dict[str, str] = {}
        self._adaptation_cache: Dict[str, List[str]] = {}
    
    async def generate_dynamic_cv(
        self,
        job_description: str
    ) -> bytes:
        """
        Generate dynamic CV PDF using LLM.
        
        Args:
            job_description: Job description text or URL (language and role will be auto-detected)
            
        Returns:
            bytes: PDF content
            
        Raises:
            ValueError: If job_description is not provided
            RuntimeError: If generation fails
        """
        if not job_description:
            raise ValueError("job_description is required for dynamic CV generation")
        
        try:
            # 1. Load portfolio data
            portfolio = self.portfolio_loader.load_portfolio()
            
            # 2. Analyze job description (extracts role automatically)
            job_reqs = await self.job_analyzer.analyze(job_description)
            
            # 3. Detect language from job description
            language = await self._detect_language(job_description)
            
            # 4. Get ALL professional experiences (not just top ones)
            all_experiences = self._get_all_professional_experiences(portfolio)
            
            # 5. Convert portfolio data to CVData format (with LLM translation if needed)
            cv_data = await self._portfolio_to_cv_data_with_llm(
                portfolio, all_experiences, language, job_reqs
            )
            
            # 6. Generate PDF
            pdf_content = self.pdf_generator.generate_pdf(cv_data, language)
            
            return pdf_content
            
        except Exception as e:
            raise RuntimeError(f"Failed to generate dynamic CV: {str(e)}") from e
    
    async def _portfolio_to_cv_data_with_llm(
        self,
        portfolio: PortfolioData,
        all_experiences: List,
        language: str,
        job_reqs: JobRequirements
    ) -> CVData:
        """
        Convert portfolio data to CVData format with LLM translation if needed.
        
        Args:
            portfolio: Portfolio data
            all_experiences: All professional experiences
            language: Language for CV (en/es)
            job_reqs: Job requirements
            
        Returns:
            CVData: CV data structure
        """
        # Personal info
        personal_info = portfolio.personal_info
        
        # Contact
        contact = CVContact(
            email=personal_info.email,
            phone=personal_info.phone,
            portfolio=personal_info.website,
            linkedin=personal_info.linkedin,
            github=personal_info.github
        )
        
        # Profile (adapt using structured LLM prompt for both languages - SHORT version: 3-4 lines)
        profile = await self._generate_adapted_profile(
            portfolio, job_reqs, language
        )
        
        # Key skills (ADAPTED to job requirements, categorized and prioritized)
        key_skills = await self._generate_adapted_key_skills(
            portfolio, job_reqs, language
        )
        
        # Experience - iterate over jobs (new structure)
        # Extract keywords once (used for all cache keys)
        keywords = self._extract_keywords_from_job(job_reqs)
        keywords_for_cache = ','.join(keywords[:3])
        role_context = f"{job_reqs.role or 'N/A'}|{language}|{keywords_for_cache}"
        
        # Build experience list from jobs
        position_experiences = []
        llm_tasks = []
        position_contexts = []
        
        if portfolio.jobs:
            for job_idx, job in enumerate(portfolio.jobs):
                # Skip academic jobs
                company_lower = job.company.lower()
                role_lower = job.role.lower()
                
                educational_keywords = [
                    "universidad", "university", "universitat", "université",
                    "escuela", "school", "colegio", "instituto", "institute",
                    "academy", "academia", "bootcamp", "curso", "course"
                ]
                academic_roles = ["estudiante", "student", "investigador", "researcher", "tesis", "thesis", "titulación"]
                
                if (any(keyword in company_lower for keyword in educational_keywords) or
                    any(role in role_lower for role in academic_roles)):
                    continue
                
                # Get achievements from job
                consolidated_achievements = []
                if job.achievements:
                    for achievement in job.achievements:
                        cleaned = self._clean_bullet_text(achievement)
                        if cleaned:
                            consolidated_achievements.append(cleaned)
                
                if not consolidated_achievements:
                    continue
                
                # Prepare job context
                position_idx = len(position_contexts)
                position_contexts.append({
                    'job': job,
                    'consolidated_achievements': consolidated_achievements,
                    'all_technologies': job.technologies[:10] if job.technologies else [],
                    'city': job.location
                })
                
                # Build cache key for achievements
                position_cache_key = self._get_cache_key(
                    f"job:{job.company}:{job.role}",
                    role_context
                )
                role_cache_key = self._get_cache_key(f"role_translation:{job.role}", "en") if language == "en" else None
                
                # Check cache
                cached_bullets = self._adaptation_cache.get(position_cache_key)
                cached_role = self._translation_cache.get(role_cache_key) if role_cache_key else None
                
                if cached_bullets is not None:
                    position_contexts[position_idx]['cached_bullets'] = cached_bullets
                else:
                    # Need LLM call to adapt achievements
                    llm_tasks.append(
                        ('bullets', position_idx, self._adapt_achievements_to_job(
                            consolidated_achievements, job, job_reqs, language, 
                            skip_cache=True, cache_key=position_cache_key
                        ))
                    )
                
                if language == "en":
                    if cached_role is not None:
                        position_contexts[position_idx]['cached_role'] = cached_role
                    else:
                        llm_tasks.append(
                            ('role', position_idx, self._translate_role(job.role, skip_cache=True))
                        )
        
        # Execute only uncached LLM calls in parallel
        if llm_tasks:
            llm_results = await asyncio.gather(*[task[2] for task in llm_tasks], return_exceptions=True)
        else:
            llm_results = []
        
        # Map results back to positions by index
        task_idx = 0
        for task_type, position_idx, _ in llm_tasks:
            if task_idx < len(llm_results):
                result = llm_results[task_idx]
                if task_type == 'bullets':
                    position_contexts[position_idx]['bullets_result'] = result
                elif task_type == 'role':
                    position_contexts[position_idx]['role_result'] = result
                task_idx += 1
        
        # Process results and build experience list
        experience_list = []
        for context in position_contexts:
            job = context['job']
            city = context['city']
            all_technologies = context['all_technologies']
            
            # Get bullets (from cache or LLM result)
            if 'cached_bullets' in context:
                bullets = context['cached_bullets']
            elif 'bullets_result' in context:
                bullets_result = context['bullets_result']
                if isinstance(bullets_result, Exception):
                    # Fallback: select top 5 from consolidated achievements
                    bullets = context['consolidated_achievements'][:5]
                else:
                    bullets = bullets_result if bullets_result else context['consolidated_achievements'][:5]
            else:
                # Fallback: select top 5 from consolidated achievements
                bullets = context['consolidated_achievements'][:5]
            
            # Get role translation (from cache or LLM result)
            role_translated = job.role
            if language == "en":
                if 'cached_role' in context:
                    role_translated = context['cached_role']
                elif 'role_result' in context:
                    role_result = context['role_result']
                    if not isinstance(role_result, Exception) and role_result:
                        role_translated = role_result
            
            cv_experience = CVExperience(
                role=role_translated,
                company=job.company,
                city=city,
                period=job.duration,
                bullets=bullets[:5],  # Limit to 5 bullets max
                technologies=all_technologies
            )
            experience_list.append(cv_experience)
        
        # Sort experiences chronologically (most recent first)
        experience_list.sort(key=lambda x: self._get_start_year(x.period), reverse=True)
        
        # Tech skills (from portfolio)
        tech_skills_list = []
        if portfolio.skills:
            for skill_cat in portfolio.skills:
                tech_skill = TechSkillCategory(
                    category=skill_cat.category,
                    skills=skill_cat.items[:15]  # Limit skills per category
                )
                tech_skills_list.append(tech_skill)
        
        # Education (from portfolio) - only formal degrees
        education_list = []
        # Formal degrees to include
        formal_degrees = [
            "ingeniería civil en informática",
            "máster en inteligencia artificial",
            "master en inteligencia artificial",  # English variant
        ]
        
        for edu in portfolio.education:
            # Check if this is a formal degree (case-insensitive)
            degree_lower = edu.degree.lower()
            is_formal = any(formal_deg in degree_lower for formal_deg in formal_degrees)
            
            if is_formal:
                # Infer city from institution name
                city = self._infer_education_city(edu.institution)
                
                # Translate degree if needed
                degree_text = edu.degree
                if language == "en":
                    degree_text = self._translate_degree_title(edu.degree)
                
                cv_education = CVEducation(
                    degree=degree_text,
                    university=edu.institution,
                    city=city,
                    period=edu.period
                )
                education_list.append(cv_education)
        
        # Languages (from portfolio)
        languages_list = []
        for lang in portfolio.languages:
            cv_language = CVLanguage(
                language=lang.name,
                level=lang.level
            )
            languages_list.append(cv_language)
        
        # Build CVData
        cv_data = CVData(
            fullName=personal_info.name,
            degree=personal_info.title,
            contact=contact,
            profile=profile,
            keySkills=key_skills,
            experience=experience_list,
            techSkills=tech_skills_list,
            education=education_list,
            languages=languages_list,
            footer=""  # Empty footer as per requirements
        )
        
        return cv_data
    
    def _clean_llm_response(self, response: str, response_type: str = "general") -> str:
        """
        Clean LLM response to remove introductory phrases and meta-commentary.
        
        Args:
            response: LLM response text
            response_type: Type of response (translation, bullets, role)
            
        Returns:
            str: Cleaned response
        """
        if not response:
            return ""
        
        # Remove common introductory phrases (case-insensitive)
        intro_phrases = [
            "here is the translation",
            "here's the translation",
            "here is the",
            "here's the",
            "here is the output",
            "here's the output",
            "here is the result",
            "here's the result",
            "translation:",
            "translated text:",
            "english translation:",
            "output:",
            "result:",
            "here are the translations",
            "here are the",
            "the translation is:",
            "translated:",
            "here it is:",
            "key skills:",
            "competencias clave:",
            "habilidades clave:",
        ]
        
        # Split by common separators (colon, dash after phrase)
        lines = response.split("\n")
        cleaned_lines = []
        
        for line in lines:
            line_lower = line.lower().strip()
            # Skip lines that are only introductory phrases
            if any(line_lower.startswith(phrase) for phrase in intro_phrases):
                continue
            # Remove introductory phrases from the beginning of lines
            cleaned_line = line
            for phrase in intro_phrases:
                if line_lower.startswith(phrase):
                    cleaned_line = line[len(phrase):].strip()
                    # Remove colon or dash if present
                    if cleaned_line.startswith(":") or cleaned_line.startswith("-"):
                        cleaned_line = cleaned_line[1:].strip()
                    break
            cleaned_lines.append(cleaned_line)
        
        result = "\n".join(cleaned_lines).strip()
        
        # If response_type is "role", take only first line
        if response_type == "role":
            result = result.split("\n")[0].strip()
        
        return result
    
    def _clean_profile_markdown(self, text: str) -> str:
        """
        Clean markdown formatting from profile text.
        
        Removes all markdown formatting including:
        - Section headers (##, ###, ####)
        - Section titles (**Perfil**, **Profile**, etc.)
        - Bold/italic formatting (**text**, *text*)
        
        Args:
            text: Profile text with potential markdown formatting
            
        Returns:
            str: Cleaned profile text without markdown formatting
        """
        if not text:
            return ""
        
        import re
        
        # Remove leading/trailing quotes (string quotes like "", '', etc.)
        text = text.strip().strip('"').strip("'").strip()
        
        # Remove markdown headers (##, ###, ####)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        
        # Remove markdown bold/italic section titles like "**Perfil**", "**Profile**", etc.
        # Patterns: **Perfil**, **Profile**, *Perfil*, "**Perfil** ", '"**Perfil** "', etc.
        # Match at beginning of text or after newline
        text = re.sub(r'(^|\n)\s*["\']?\s*\*\*?(Perfil|Profile|PROFILE|PERFIL)\*\*?\s*["\']?\s*:?\s*', r'\1', text, flags=re.IGNORECASE)
        
        # Remove ANY markdown bold formatting (**text**) throughout the entire text
        # This removes all **text** patterns, keeping only the text inside
        # Pattern matches **text** and captures the text inside
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        
        # Remove any orphaned ** at the end of words (like "experiencia**")
        text = re.sub(r'\*\*\s*', ' ', text)  # Remove ** followed by space
        text = re.sub(r'\*\*$', '', text)  # Remove ** at end of line
        text = re.sub(r'\*\*([^a-zA-Z])', r'\1', text)  # Remove ** before punctuation
        
        # Remove ANY markdown italic formatting (*text*) throughout the entire text
        # But be careful not to remove asterisks that are part of normal text
        # Only remove single asterisks used for emphasis (not part of **)
        text = re.sub(r'(?<!\*)\*([^*\s]+?)\*(?!\*)', r'\1', text)
        
        # Remove any leading/trailing asterisks or markdown formatting on lines
        text = re.sub(r'^\*\*?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*\*\*?$', '', text, flags=re.MULTILINE)
        
        # Remove any section markers at the beginning of lines (without markdown)
        text = re.sub(r'^(Perfil|Profile|PROFILE|PERFIL)\s*:?\s*', '', text, flags=re.MULTILINE | re.IGNORECASE)
        
        # Clean up multiple spaces (but preserve single spaces between words)
        text = re.sub(r'  +', ' ', text)
        
        # Clean up multiple newlines at the beginning
        text = re.sub(r'^\n+', '', text)
        
        # Clean up leading/trailing whitespace
        text = text.strip()
        
        return text
    
    def _translate_degree_title(self, degree: str) -> str:
        """
        Translate degree title from Spanish to English.
        
        Args:
            degree: Degree title in Spanish
            
        Returns:
            str: Translated degree title
        """
        degree_lower = degree.lower()
        if "máster en inteligencia artificial" in degree_lower or "master en inteligencia artificial" in degree_lower:
            return "Master's in Artificial Intelligence"
        elif "ingeniería civil en informática" in degree_lower:
            return "Computer Science Engineering"
        return degree
    
    def _get_all_professional_experiences(self, portfolio: PortfolioData) -> List:
        """
        Get ALL professional experiences (jobs).
        
        Args:
            portfolio: Portfolio data
            
        Returns:
            List: All professional jobs (from portfolio.jobs)
        """
        if not portfolio.jobs:
            return []
        
        # Filter out academic jobs
        professional_jobs = []
        for job in portfolio.jobs:
            # Skip academic jobs based on company name or role
            company_lower = job.company.lower()
            role_lower = job.role.lower()
            
            educational_keywords = [
                "universidad", "university", "universitat", "université",
                "escuela", "school", "colegio", "instituto", "institute",
                "academy", "academia", "bootcamp", "curso", "course"
            ]
            academic_roles = ["estudiante", "student", "investigador", "researcher", "tesis", "thesis", "titulación"]
            
            is_academic = (
                any(keyword in company_lower for keyword in educational_keywords) or
                any(role in role_lower for role in academic_roles)
            )
            
            if not is_academic:
                professional_jobs.append(job)
        
        return professional_jobs
    
    async def _generate_adapted_profile(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        language: str
    ) -> str:
        """
        Generate adapted professional profile using structured prompt approach.
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            language: Language (en/es)
            
        Returns:
            str: Adapted profile text
        """
        # Extract keywords from job requirements
        keywords = self._extract_keywords_from_job(job_reqs)
        keywords_str = ", ".join(keywords[:7])
        
        # Build job description summary
        job_description = f"""
Role: {job_reqs.role or 'N/A'}
Summary: {job_reqs.summary}
Technologies: {', '.join(job_reqs.technologies[:10])}
Requirements: {', '.join(job_reqs.requirements[:5]) if job_reqs.requirements else 'N/A'}
Industry: {', '.join(job_reqs.industry_tags[:5]) if job_reqs.industry_tags else 'N/A'}
"""
        
        # Original profile
        original_profile = portfolio.professional_summary.detailed
        
        # Build skills showcase summary
        skills_summary = ""
        if portfolio.skills_showcase:
            for skill_id, skill in portfolio.skills_showcase.items():
                skills_summary += f"\n{skill_id}: {skill.description[:200]}...\n"
                skills_summary += f"Technologies: {', '.join(skill.key_technologies[:10]) if skill.key_technologies else ''}\n"
        
        if language == "en":
            prompt = f"""### ROLE
You are an expert CV writer specializing in concise, impactful professional profiles.

### OBJECTIVE
Generate a SHORT professional profile (3-4 LINES, NOT paragraphs) for Álvaro Maldonado, STRICTLY adapted to the job requirements.

### RULES
1. **ABSOLUTE FIDELITY:** Use ONLY information from [ÁLVARO_DATABASE]. DO NOT invent anything.
2. **FOCUS:** Profile should focus on IDENTITY and OBJECTIVE only. DO NOT list specific technologies - those go in a separate "Key Skills" section.
3. **LENGTH:** Maximum 3-4 LINES. Be concise and powerful.
4. **CONTENT:** Include: role (Senior Software Engineer, Product Engineer), years of experience (15+), passion/strength (AI as strategic enabler), objective (remote role in Spain).

CRITICAL: The profile should NOT list technologies. Technologies are shown separately in "Key Skills" section.

---

### STEP 1: KEYWORDS ANALYSIS
Keywords from job: {keywords_str}

### STEP 2: PROFILE WRITING
Write a concise 3-4 LINE profile that:
- States identity: Senior Software Engineer, Product Engineer
- Mentions experience: 15+ years
- Highlights strength: AI as strategic enabler (if relevant)
- States objective: remote role in Spain (if relevant)
- Does NOT list specific technologies (Java, Python, AWS, etc.)

---

### [JOB_DESCRIPTION]:
{job_description}

### [ÁLVARO_DATABASE]:
**[ORIGINAL_PROFILE]:**
{original_profile}

---

### OUTPUT
Output ONLY the adapted profile in English (3-4 LINES max, no technologies listed):"""
            
            system = "You are an expert CV writer. Generate ONLY a concise 3-4 LINE profile focusing on identity and objective. Do NOT list technologies."
        else:
            prompt = f"""IMPORTANTE: DEBES ESCRIBIR TODO EL CONTENIDO EN ESPAÑOL. NO uses inglés en ningún momento.

### ROL
Eres un redactor experto de CVs especializado en perfiles profesionales concisos e impactantes.

### OBJETIVO
Genera un perfil profesional CORTO (3-4 LÍNEAS, NO párrafos) para Álvaro Maldonado, ESTRICTAMENTE adaptado a los requisitos del trabajo.

### REGLAS
1. **FIDELIDAD ABSOLUTA:** Usa SOLO información de [BASE_DE_DATOS_DE_ÁLVARO]. NO inventes nada.
2. **ENFOQUE:** El perfil debe enfocarse en IDENTIDAD y OBJETIVO únicamente. NO listes tecnologías específicas - esas van en una sección separada "Habilidades Clave".
3. **LONGITUD:** Máximo 3-4 LÍNEAS. Sé conciso y poderoso.
4. **CONTENIDO:** Incluye: rol (Senior Software Engineer, Product Engineer), años de experiencia (15+), pasión/fortaleza (IA como acelerador estratégico), objetivo (rol remoto en España).
5. **IDIOMA:** ESCRIBE TODO EN ESPAÑOL. NO uses inglés en ningún momento.

CRÍTICO: El perfil NO debe listar tecnologías. Las tecnologías se muestran por separado en la sección "Habilidades Clave".

---

### PASO 1: ANÁLISIS DE PALABRAS CLAVE
Palabras clave del trabajo: {keywords_str}

### PASO 2: ESCRITURA DEL PERFIL
Escribe un perfil conciso de 3-4 LÍNEAS que:
- Establezca identidad: Senior Software Engineer, Product Engineer
- Mencione experiencia: 15+ años
- Destaque fortaleza: IA como acelerador estratégico (si es relevante)
- Establezca objetivo: rol remoto en España (si es relevante)
- NO liste tecnologías específicas (Java, Python, AWS, etc.)

---

### [DESCRIPCIÓN_DEL_TRABAJO]:
{job_description}

### [BASE_DE_DATOS_DE_ÁLVARO]:
**[PERFIL_ORIGINAL]:**
{original_profile}

---

### SALIDA
Devuelve SOLO el perfil adaptado en español (3-4 LÍNEAS máx, sin tecnologías listadas):"""
            
            system = "Eres un redactor experto de CVs en español. DEBES escribir TODO en ESPAÑOL. Genera SOLO un perfil conciso de 3-4 LÍNEAS enfocado en identidad y objetivo. NO listes tecnologías. NO uses inglés en ningún momento."
        
        try:
            profile_response = await self.llm_service.generate(
                prompt=prompt,
                system=system,
                temperature=0.3,
                max_tokens=200  # Reduced for shorter profile (3-4 lines)
            )
            profile = self._clean_llm_response(profile_response, "translation")
            
            # Additional cleaning: remove markdown headers and section titles
            profile = self._clean_profile_markdown(profile)
            
            # Limit profile to 3-4 lines max
            if profile:
                profile_lines = profile.split('\n')
                profile_short = '\n'.join([line.strip() for line in profile_lines[:4] if line.strip()])
                return profile_short if profile_short else portfolio.professional_summary.short
            return portfolio.professional_summary.short
        except Exception:
            return portfolio.professional_summary.short
    
    async def _generate_adapted_key_skills(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        language: str
    ) -> List[str]:
        """
        Generate adapted key skills list using LLM with profile selection approach.
        
        This is the "gancho principal" - the key section that adapts to each job offer.
        Uses profile selection (PASO 4) to select the appropriate cv_skill_profile based on job keywords.
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            language: Language (en/es)
            
        Returns:
            List[str]: Simple list of key technologies from the selected profile
        """
        # Extract keywords from job requirements (PASO 1)
        keywords = self._extract_keywords_from_job(job_reqs)
        keywords_str = ", ".join(keywords[:10])
        
        # Build CV skill profiles JSON
        import json
        cv_skill_profiles_json = {}
        if portfolio.cv_skill_profiles:
            for profile_id, categories in portfolio.cv_skill_profiles.items():
                cv_skill_profiles_json[profile_id] = [
                    {"category": cat.category, "items": cat.items}
                    for cat in categories
                ]
        
        cv_skill_profiles_json_str = json.dumps(cv_skill_profiles_json, indent=2, ensure_ascii=False)
        
        # Build job requirements summary
        job_summary = f"""
Role: {job_reqs.role or 'N/A'}
Technologies: {', '.join(job_reqs.technologies[:15])}
Requirements: {', '.join(job_reqs.requirements[:10]) if job_reqs.requirements else 'N/A'}
"""
        
        # Check if user has Azure in portfolio (to avoid adding it if not present)
        has_azure_in_portfolio = False
        if portfolio.skills_showcase:
            for skill in portfolio.skills_showcase.values():
                if skill.key_technologies:
                    if any("azure" in tech.lower() for tech in skill.key_technologies):
                        has_azure_in_portfolio = True
                        break
        # Also check jobs
        if not has_azure_in_portfolio and portfolio.jobs:
            for job in portfolio.jobs:
                if job.technologies and "azure" in [t.lower() for t in job.technologies]:
                    has_azure_in_portfolio = True
                    break
        
        if language == "en":
            prompt = f"""### ROLE
You are an expert CV writer specializing in generating adapted key skills sections.

### OBJECTIVE
Generate a "Key Skills" section adapted to the job offer by selecting the appropriate profile from [CV_SKILL_PROFILES_JSON].

### RULES
1. **ABSOLUTE FIDELITY:** Use ONLY the items from the selected profile in [CV_SKILL_PROFILES_JSON]. DO NOT invent technologies.
2. **PROFILE SELECTION:** Classify the job offer into ONE of the available profiles.
3. **EXACT OUTPUT:** Use EXACTLY the categories and items from the selected profile. Do not add or remove anything.

---

### STEP 1: KEYWORDS IDENTIFICATION
Review the keywords identified from the job offer:
Keywords: {keywords_str}

---

### STEP 2: ANALYZE JOB DESCRIPTION
Review the job requirements to understand the role:
{job_summary}

---

### STEP 3: CLASSIFY THE OFFER
Analyze the keywords and job requirements from STEP 1 and STEP 2.

Classify the offer into ONE of these categories:
- 'ia_specialist': Job is 100% focused on AI/ML (e.g., "AI Engineer", "ML Specialist", "RAG Engineer", mentions only AI/ML technologies)
- 'java_backend_architect': Job is 100% focused on Java/Backend (e.g., "Java Developer", "Backend Engineer", "Microservices Architect", mentions only Java/Spring/Microservices)
- 'hybrid_ai_java': Job combines AI/ML AND Java/Backend (e.g., "Full Stack AI Engineer", mentions both Python/AI and Java/Spring)
- 'technical_leader': Job is focused on leadership/management (e.g., "Tech Lead", "CTO", "Engineering Manager", "Technical Director")

---

### PASO 4: COMPETENCIAS CLAVE (SELECCIÓN DE PERFIL)

1. Analiza las *keywords* de la [DESCRIPCIÓN_DEL_TRABAJO] (del PASO 1).

2. Clasifica la oferta en **una** de estas categorías: 'ia_specialist', 'java_backend_architect', 'hybrid_ai_java', o 'technical_leader'.

3. Busca el perfil de habilidades correspondiente en `[CV_SKILL_PROFILES_JSON]`.

4. **Imprime** la sección `## Competencias Clave` usando **exactamente** las categorías e ítems de ese perfil seleccionado. No añadas ni quites nada de la lista del perfil.

### STEP 4: KEY SKILLS (PROFILE SELECTION)

1. Analyze the *keywords* from [JOB_DESCRIPTION] (from STEP 1).

2. Classify the offer into **one** of these categories: 'ia_specialist', 'java_backend_architect', 'hybrid_ai_java', or 'technical_leader'.

3. Find the corresponding skill profile in `[CV_SKILL_PROFILES_JSON]`.

4. **Print** the section `## Key Skills` using **exactly** the categories and items from that selected profile. Do not add or remove anything from the profile list.

### OUTPUT FORMAT
For each category in the selected profile, output one line per category in this format:
Category Name: item1, item2, item3, ...

Example output (for ia_specialist profile):
IA/ML y GenAI: IA/ML, RAG, LLMs, LangChain, TensorFlow/PyTorch, HuggingFace, Visión por Computador, NLP
Infraestructura Cloud (IA): AWS (SageMaker, S3), GCP (Cloud Run, Cloud SQL), Docker, pgvector
Desarrollo Asistido por IA: GitHub Copilot, Cursor, Prompt Engineering

---

### [JOB_REQUIREMENTS]:
{job_summary}

### [CV_SKILL_PROFILES_JSON]:
{cv_skill_profiles_json_str}

---

### OUTPUT
Output the categories and items from the selected profile exactly as they appear in [CV_SKILL_PROFILES_JSON].
Do not include explanations, just output the formatted skills lines."""
            
            system = "You are an expert CV writer. Select the appropriate skill profile based on job keywords and output the skills exactly as defined in CV_SKILL_PROFILES_JSON. Do not modify the profile items."
        else:
            prompt = f"""IMPORTANTE: DEBES ESCRIBIR TODO EL CONTENIDO EN ESPAÑOL. NO uses inglés en ningún momento.

### ROL
Eres un redactor experto de CVs especializado en generar secciones de habilidades clave adaptadas.

### OBJETIVO
Genera una sección "Competencias Clave" adaptada a la oferta de trabajo seleccionando el perfil apropiado de [CV_SKILL_PROFILES_JSON].

### REGLAS
1. **FIDELIDAD ABSOLUTA:** Usa SOLO los ítems del perfil seleccionado en [CV_SKILL_PROFILES_JSON]. NO inventes tecnologías.
2. **SELECCIÓN DE PERFIL:** Clasifica la oferta de trabajo en UNO de los perfiles disponibles.
3. **SALIDA EXACTA:** Usa EXACTAMENTE las categorías e ítems del perfil seleccionado. No añadas ni quites nada.
4. **IDIOMA:** ESCRIBE TODO EN ESPAÑOL. NO uses inglés en ningún momento.

---

### PASO 1: IDENTIFICACIÓN DE PALABRAS CLAVE
Revisa las keywords identificadas de la oferta:
Keywords: {keywords_str}

---

### PASO 2: ANALIZAR DESCRIPCIÓN DEL TRABAJO
Revisa los requisitos del trabajo para entender el rol:
{job_summary}

---

### PASO 3: CLASIFICAR LA OFERTA
Analiza las keywords y requisitos del trabajo de los PASOS 1 y 2.

Clasifica la oferta en UNA de estas categorías:
- 'ia_specialist': El trabajo está 100% enfocado en IA/ML (ej. "Ingeniero de IA", "Especialista en ML", "Ingeniero RAG", menciona solo tecnologías de IA/ML)
- 'java_backend_architect': El trabajo está 100% enfocado en Java/Backend (ej. "Desarrollador Java", "Ingeniero Backend", "Arquitecto de Microservicios", menciona solo Java/Spring/Microservicios)
- 'hybrid_ai_java': El trabajo combina IA/ML Y Java/Backend (ej. "Ingeniero Full Stack IA", menciona tanto Python/IA como Java/Spring)
- 'technical_leader': El trabajo está enfocado en liderazgo/gestión (ej. "Tech Lead", "CTO", "Engineering Manager", "Director Técnico")

---

### PASO 4: COMPETENCIAS CLAVE (SELECCIÓN DE PERFIL)

1. Analiza las *keywords* de la [DESCRIPCIÓN_DEL_TRABAJO] (del PASO 1).

2. Clasifica la oferta en **una** de estas categorías: 'ia_specialist', 'java_backend_architect', 'hybrid_ai_java', o 'technical_leader'.

3. Busca el perfil de habilidades correspondiente en `[CV_SKILL_PROFILES_JSON]`.

4. **Imprime** la sección `## Competencias Clave` usando **exactamente** las categorías e ítems de ese perfil seleccionado. No añadas ni quites nada de la lista del perfil.

### FORMATO DE SALIDA
Para cada categoría en el perfil seleccionado, devuelve una línea por categoría en este formato:
Nombre de Categoría: item1, item2, item3, ...

Ejemplo de salida (para perfil ia_specialist):
IA/ML y GenAI: IA/ML, RAG, LLMs, LangChain, TensorFlow/PyTorch, HuggingFace, Visión por Computador, NLP
Infraestructura Cloud (IA): AWS (SageMaker, S3), GCP (Cloud Run, Cloud SQL), Docker, pgvector
Desarrollo Asistido por IA: GitHub Copilot, Cursor, Prompt Engineering

---

### [REQUISITOS_DEL_TRABAJO]:
{job_summary}

### [CV_SKILL_PROFILES_JSON]:
{cv_skill_profiles_json_str}

---

### SALIDA
Devuelve las categorías e ítems del perfil seleccionado exactamente como aparecen en [CV_SKILL_PROFILES_JSON].
No incluyas explicaciones, solo devuelve las líneas de habilidades formateadas."""
            
            system = "Eres un redactor experto de CVs en español. DEBES escribir TODO en ESPAÑOL. Selecciona el perfil de habilidades apropiado basándote en keywords del trabajo y devuelve las habilidades exactamente como están definidas en CV_SKILL_PROFILES_JSON. No modifiques los ítems del perfil. NO uses inglés en ningún momento."
        
        try:
            # PHASE 1: Classification (deterministic, very low temperature)
            classification_prompt = f"""You are a classification tool. Your ONLY job is to classify the job offer into ONE category.

### CATEGORIES:
1. 'ia_specialist': Job is 100% AI/ML focused (mentions only AI/ML technologies, no Java/Backend)
2. 'java_backend_architect': Job is 100% Java/Backend focused (mentions only Java/Spring/Microservices, no AI/ML)
3. 'hybrid_ai_java': Job combines AI/ML AND Java/Backend (mentions both Python/AI and Java/Spring)
4. 'technical_leader': Job is focused on leadership/management (mentions Tech Lead, CTO, Engineering Manager, Technical Director)

### JOB DESCRIPTION:
Role: {job_reqs.role or 'N/A'}
Technologies: {', '.join(job_reqs.technologies[:10])}
Summary: {job_reqs.summary[:300] if job_reqs.summary else 'N/A'}

### YOUR TASK:
Classify this job into ONE category. Output ONLY the category name (e.g., 'ia_specialist').
Do NOT output anything else. Do NOT explain. Just the category name."""

            classification_response = await self.llm_service.generate(
                prompt=classification_prompt,
                system="You are a classification tool. Output ONLY the category name. Do not explain.",
                temperature=0.0,  # MINIMUM temperature for maximum determinism
                max_tokens=20
            )
            
            # Extract profile ID from classification
            profile_id = self._extract_profile_id(classification_response, cv_skill_profiles_json)
            
            if not profile_id:
                # Fallback: use hybrid_ai_java as default (safest option)
                profile_id = 'hybrid_ai_java'
            
            # PHASE 2: Extract items from selected profile (NO LLM, just direct extraction)
            selected_profile = cv_skill_profiles_json.get(profile_id, [])
            
            if not selected_profile:
                # Fallback: return empty list
                return []
            
            # Build simple list from profile (NO generation needed)
            key_skills = []
            for category in selected_profile:
                category_name = category.get('category', '')
                items = category.get('items', [])
                if items:
                    # Format as single line: "Category: item1, item2, ..."
                    key_skills.append(f"{category_name}: {', '.join(items)}")
            
            return key_skills
            
        except Exception as e:
            # Fallback: try original method if classification fails
            try:
                # Fallback to original approach
                response = await self.llm_service.generate(
                    prompt=prompt,
                    system=system,
                    temperature=0.2,
                    max_tokens=300
                )
                
                # Clean response first to remove introductory phrases
                cleaned_response = self._clean_llm_response(response, "bullets")
                
                # Parse response: extract items from category lines
                # Format expected: "Category: item1, item2, ..." -> extract individual items
                all_items = set()  # Use set to avoid duplicates
                
                for line in cleaned_response.split('\n'):
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Skip lines that are only introductory phrases
                    line_lower = line.lower()
                    intro_phrases = [
                        "here is", "here's", "here are", "output:", "result:", "salida:",
                        "these are", "the following", "translation:", "traducción:",
                        "key skills:", "competencias clave:", "habilidades clave:",
                        "example output", "ejemplo de salida"
                    ]
                    if any(line_lower.startswith(phrase) for phrase in intro_phrases):
                        continue
                    
                    # Check if line matches format "Category: item1, item2, ..."
                    if ':' in line and not line.startswith('#'):
                        # Remove any leading dashes, bullets, or numbers
                        line = line.lstrip('- •*123456789. ')
                        
                        # Extract category and items
                        parts = line.split(':', 1)
                        if len(parts) == 2:
                            category = parts[0].strip()
                            items_str = parts[1].strip()
                            
                            # Split items by comma and clean each
                            items = [item.strip() for item in items_str.split(',') if item.strip()]
                            for item in items:
                                if item and len(item) > 1:  # Minimum 2 characters
                                    all_items.add(item)
                
                # Convert to list (simple list of items, no categories)
                key_skills = list(all_items)
                
                # Fallback if LLM returns empty or malformed response
                if not key_skills:
                    # Fallback to simple algorithmic approach (original logic)
                    print("Warning: LLM key skills generation returned empty, using fallback")
                    return await self._generate_adapted_key_skills_fallback(
                        portfolio, job_reqs, language
                    )
                
                # Return all items from profile (no limit, as profiles are pre-curated)
                return key_skills
                
            except Exception as fallback_error:
                # Final fallback on error
                print(f"Warning: LLM key skills generation failed: {fallback_error}, using algorithmic fallback")
                return await self._generate_adapted_key_skills_fallback(
                    portfolio, job_reqs, language
                )
    
    async def _generate_adapted_key_skills_fallback(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        language: str
    ) -> List[str]:
        """
        Fallback method for generating key skills (original algorithmic approach).
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            language: Language (en/es)
            
        Returns:
            List[str]: Categorized key skills
        """
        # Collect all technologies from portfolio
        all_technologies = set()
        if portfolio.jobs:
            for job in portfolio.jobs:
                if job.technologies:
                    all_technologies.update(job.technologies)
        
        # Get job technologies (normalized to lowercase for matching)
        job_techs_lower = [tech.lower() for tech in job_reqs.technologies]
        
        # Categorize technologies
        backend_techs = []
        cloud_techs = []
        ai_ml_techs = []
        devops_techs = []
        database_techs = []
        testing_techs = []
        other_techs = []
        
        # Define technology categories
        backend_keywords = ["java", "spring", "python", "fastapi", "javascript", "node", "backend"]
        cloud_keywords = ["aws", "gcp", "azure", "cloud", "s3", "ec2", "lambda", "sagemaker", "cloud run", "cloud sql"]
        ai_ml_keywords = ["ai", "ml", "tensorflow", "pytorch", "llm", "rag", "nlp", "computer vision", "opencv", "gemini", "huggingface"]
        devops_keywords = ["docker", "kubernetes", "jenkins", "ci/cd", "github actions", "devops", "terraform", "ansible"]
        database_keywords = ["sql", "oracle", "postgresql", "mongodb", "database", "jpa", "hibernate"]
        testing_keywords = ["junit", "mockito", "spock", "testing", "test", "karate", "tdd"]
        
        # Match portfolio technologies to categories and job requirements
        for tech in all_technologies:
            tech_lower = tech.lower()
            
            # Check if technology matches job requirements (priority)
            matches_job = any(job_tech in tech_lower or tech_lower in job_tech for job_tech in job_techs_lower)
            
            # Categorize (prioritize technologies that match job requirements)
            if any(keyword in tech_lower for keyword in backend_keywords):
                if matches_job or not backend_techs:  # Prioritize job matches
                    backend_techs.append(tech)
            elif any(keyword in tech_lower for keyword in cloud_keywords):
                if matches_job or not cloud_techs:
                    cloud_techs.append(tech)
            elif any(keyword in tech_lower for keyword in ai_ml_keywords):
                if matches_job or not ai_ml_techs:
                    ai_ml_techs.append(tech)
            elif any(keyword in tech_lower for keyword in devops_keywords):
                if matches_job or not devops_techs:
                    devops_techs.append(tech)
            elif any(keyword in tech_lower for keyword in database_keywords):
                if matches_job or not database_techs:
                    database_techs.append(tech)
            elif any(keyword in tech_lower for keyword in testing_keywords):
                if matches_job or not testing_techs:
                    testing_techs.append(tech)
            elif matches_job:  # Other techs that match job requirements
                other_techs.append(tech)
        
        # Build simple list of technologies (no categories, like experience section)
        key_skills = []
        
        # Prioritize technologies that match job requirements
        # Collect all technologies in priority order (job matches first)
        prioritized_techs = []
        
        # Check if user has Azure in portfolio
        has_azure_in_portfolio = False
        if portfolio.skills_showcase:
            for skill in portfolio.skills_showcase.values():
                if skill.key_technologies:
                    if any("azure" in tech.lower() for tech in skill.key_technologies):
                        has_azure_in_portfolio = True
                        break
        # Also check jobs
        if not has_azure_in_portfolio and portfolio.jobs:
            for job in portfolio.jobs:
                if job.technologies and "azure" in [t.lower() for t in job.technologies]:
                    has_azure_in_portfolio = True
                    break
        
        # Remove Azure (Valorable) from cloud_techs if not in portfolio
        if not has_azure_in_portfolio:
            cloud_techs = [tech for tech in cloud_techs if "azure" not in tech.lower()]
        
        # First: technologies that match job requirements (prioritize these)
        all_categorized_techs = backend_techs + cloud_techs + ai_ml_techs + devops_techs + database_techs + testing_techs + other_techs
        
        for tech in all_categorized_techs:
            if tech and tech not in prioritized_techs:
                # Check if matches job
                tech_lower = tech.lower()
                matches_job = any(job_tech in tech_lower or tech_lower in job_tech 
                                 for job_tech in job_techs_lower) if job_techs_lower else False
                if matches_job:
                    prioritized_techs.insert(0, tech)  # Add at beginning
                else:
                    prioritized_techs.append(tech)
        
        # If we don't have enough prioritized techs, add from all_technologies
        if len(prioritized_techs) < 10:
            for tech in all_technologies:
                if tech not in prioritized_techs:
                    prioritized_techs.append(tech)
        
        # Post-process: Filter and prioritize based on job requirements
        prioritized_techs = self._filter_and_prioritize_skills(prioritized_techs, job_reqs)
        
        # Limit to top 10-12 technologies
        return prioritized_techs[:12] if prioritized_techs else list(all_technologies)[:10]
    
    def _filter_and_prioritize_skills(
        self,
        skills: List[str],
        job_reqs: JobRequirements
    ) -> List[str]:
        """
        Filter and prioritize skills based on job requirements.
        
        Removes skills that are not relevant to the job offer (e.g., AI/ML skills
        when job is for backend Java development).
        
        Args:
            skills: List of technologies/skills
            job_reqs: Job requirements
            
        Returns:
            List[str]: Filtered and prioritized skills list
        """
        if not skills:
            return []
        
        # Normalize job requirements for matching
        job_techs_lower = [tech.lower() for tech in job_reqs.technologies]
        job_role_lower = job_reqs.role.lower() if job_reqs.role else ""
        job_summary_lower = job_reqs.summary.lower() if job_reqs.summary else ""
        
        # Determine job focus areas
        job_focus = {
            "backend": any(keyword in job_role_lower + " " + job_summary_lower for keyword in 
                          ["backend", "back-end", "java", "spring", "microservices", "microservicios", "api", "rest"]),
            "frontend": any(keyword in job_role_lower + " " + job_summary_lower for keyword in 
                           ["frontend", "front-end", "react", "angular", "vue", "ui", "ux"]),
            "ai_ml": any(keyword in job_role_lower + " " + job_summary_lower for keyword in 
                        ["ai", "ml", "machine learning", "deep learning", "neural", "tensorflow", "pytorch", "nlp", "computer vision", "vision", "inteligencia artificial"]),
            "cloud": any(keyword in job_role_lower + " " + job_summary_lower for keyword in 
                        ["aws", "gcp", "azure", "cloud", "s3", "ec2", "lambda"]),
            "devops": any(keyword in job_role_lower + " " + job_summary_lower for keyword in 
                         ["devops", "docker", "kubernetes", "ci/cd", "jenkins", "terraform"]),
        }
        
        # Define technology categories with their focus areas
        ai_ml_techs = ["python", "tensorflow", "pytorch", "opencv", "nlp", "rag", "llm", "gemini", "huggingface", 
                      "computer vision", "visión por computador", "cnn", "deep learning", "keras", "scikit-learn"]
        frontend_techs = ["react", "angular", "vue", "javascript", "typescript", "html", "css"]
        
        # Categorize skills
        matching_skills = []  # Skills that match job requirements
        relevant_skills = []  # Skills relevant to job focus
        irrelevant_skills = []  # Skills not relevant to job
        
        for skill in skills:
            skill_lower = skill.lower()
            
            # Check if directly matches job technologies
            matches_job = any(job_tech in skill_lower or skill_lower in job_tech 
                            for job_tech in job_techs_lower)
            
            # Check if skill is AI/ML related
            is_ai_ml = any(ai_tech in skill_lower for ai_tech in ai_ml_techs)
            
            # Check if skill is frontend related
            is_frontend = any(frontend_tech in skill_lower for frontend_tech in frontend_techs)
            
            # Filter logic:
            # 1. If job focuses on backend (Java, Spring, etc.) and NOT on AI/ML, exclude AI/ML skills
            if job_focus["backend"] and not job_focus["ai_ml"] and is_ai_ml:
                irrelevant_skills.append(skill)
                continue
            
            # 2. If job focuses on backend and NOT on frontend, exclude frontend skills
            if job_focus["backend"] and not job_focus["frontend"] and is_frontend:
                irrelevant_skills.append(skill)
                continue
            
            # 3. If job focuses on frontend and NOT on backend, exclude backend-specific skills
            if job_focus["frontend"] and not job_focus["backend"]:
                backend_only_techs = ["java", "spring boot", "spring", "microservices", "microservicios"]
                if any(backend_tech in skill_lower for backend_tech in backend_only_techs):
                    # Only exclude if not directly matching job requirements
                    if not matches_job:
                        irrelevant_skills.append(skill)
                        continue
            
            # Prioritize matching skills
            if matches_job:
                matching_skills.append(skill)
            elif is_ai_ml and job_focus["ai_ml"]:
                relevant_skills.append(skill)
            elif is_frontend and job_focus["frontend"]:
                relevant_skills.append(skill)
            elif job_focus["backend"] and any(keyword in skill_lower for keyword in 
                                              ["java", "spring", "microservices", "microservicios", "backend", "api"]):
                relevant_skills.append(skill)
            elif job_focus["cloud"] and any(keyword in skill_lower for keyword in 
                                            ["aws", "gcp", "azure", "cloud"]):
                relevant_skills.append(skill)
            elif job_focus["devops"] and any(keyword in skill_lower for keyword in 
                                            ["docker", "kubernetes", "jenkins", "ci/cd", "devops"]):
                relevant_skills.append(skill)
            else:
                # Other skills - keep if they match or if we don't have many skills yet
                if len(matching_skills) + len(relevant_skills) < 8:
                    relevant_skills.append(skill)
        
        # Combine: matching first, then relevant
        prioritized = matching_skills + relevant_skills
        
        # Remove duplicates while preserving order
        seen = set()
        result = []
        for skill in prioritized:
            if skill.lower() not in seen:
                seen.add(skill.lower())
                result.append(skill)
        
        return result if result else skills  # Fallback to original if all filtered out
    
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
    
    def _extract_keywords_from_job(self, job_reqs: JobRequirements) -> List[str]:
        """
        Extract main keywords from job requirements.
        
        Args:
            job_reqs: Job requirements
            
        Returns:
            List[str]: Main keywords (5-7 items)
        """
        keywords = []
        
        # Add role if present
        if job_reqs.role:
            keywords.append(job_reqs.role)
        
        # Add technologies (top 5)
        keywords.extend(job_reqs.technologies[:5])
        
        # Add industry tags
        if job_reqs.industry_tags:
            keywords.extend(job_reqs.industry_tags[:3])
        
        # Extract keywords from summary
        if job_reqs.summary:
            summary_lower = job_reqs.summary.lower()
            # Common technical keywords
            tech_keywords = [
                "ai", "machine learning", "deep learning", "nlp", "computer vision",
                "python", "java", "aws", "gcp", "azure", "microservices", "docker",
                "kubernetes", "leadership", "architecture", "backend", "frontend"
            ]
            for kw in tech_keywords:
                if kw in summary_lower and kw not in keywords:
                    keywords.append(kw)
        
        # Return unique keywords (max 7)
        seen = set()
        unique_keywords = []
        for kw in keywords:
            kw_lower = kw.lower()
            if kw_lower not in seen and len(unique_keywords) < 7:
                seen.add(kw_lower)
                unique_keywords.append(kw)
        
        return unique_keywords
    
    def _get_cache_key(self, text: str, context: Optional[str] = None) -> str:
        """
        Generate cache key from text and optional context.
        
        Args:
            text: Input text
            context: Optional context string
            
        Returns:
            str: MD5 hash of the cache key
        """
        cache_input = f"{text}|{context or ''}"
        return hashlib.md5(cache_input.encode('utf-8')).hexdigest()
    
    async def _translate_role(self, role: str, skip_cache: bool = False) -> str:
        """
        Translate job role from Spanish to English with caching.
        
        Args:
            role: Role in Spanish
            skip_cache: If True, skip cache check (used when already checked externally)
            
        Returns:
            str: Translated role in English
        """
        # Check cache (unless already checked externally)
        if not skip_cache:
            cache_key = self._get_cache_key(f"role_translation:{role}", "en")
            if cache_key in self._translation_cache:
                return self._translation_cache[cache_key]
        
        cache_key = self._get_cache_key(f"role_translation:{role}", "en")
        try:
            role_translated_result = await self.llm_service.generate(
                prompt=f'Translate to English: "{role}"',
                system="Translator. Output ONLY the English title, nothing else.",
                temperature=0.2,
                max_tokens=30
            )
            role_translated = self._clean_llm_response(role_translated_result, "role").strip().strip('"').strip("'") if role_translated_result else role
            # Fallback if translation failed
            if not role_translated or len(role_translated) > 100:
                role_translated = role
            
            # Cache result
            self._translation_cache[cache_key] = role_translated
            return role_translated
        except Exception:
            return role
    
    async def _adapt_achievements_to_job(
        self,
        consolidated_achievements: List[str],
        job,
        job_reqs: JobRequirements,
        language: str,
        skip_cache: bool = False,
        cache_key: Optional[str] = None
    ) -> List[str]:
        """
        Adapt achievements/bullets to highlight relevance to job requirements.
        If not technically relevant, emphasize leadership, problem-solving, etc.

        Args:
            consolidated_achievements: List of achievement strings to adapt
            job: Job from portfolio
            job_reqs: Job requirements
            language: Language (en/es)
            skip_cache: If True, skip cache check (used when already checked externally)
            cache_key: Pre-computed cache key (optional, for optimization)
            
        Returns:
            List[str]: Adapted bullets (max 5)
        """
        original_bullets = consolidated_achievements[:5]
        # Clean original bullets to remove any leading bullet characters
        original_bullets = [self._clean_bullet_text(bullet) for bullet in original_bullets]
        
        # Extract keywords once (used for cache key and prompt)
        keywords = self._extract_keywords_from_job(job_reqs)
        
        # Build cache key for this adaptation (unless provided)
        if cache_key is None:
            cache_context = f"{job_reqs.role or 'N/A'}|{language}|{','.join(keywords[:3])}"
            cache_key = self._get_cache_key(f"adaptation:{job.company}:{job.role}", cache_context)
        
        # Check cache (unless already checked externally)
        if not skip_cache:
            if cache_key in self._adaptation_cache:
                return self._adaptation_cache[cache_key]
        
        # Build keywords string for prompt
        keywords_str = ", ".join(keywords[:7])
        
        # Build job requirements summary
        job_summary = f"""
Role: {job_reqs.role or 'N/A'}
Summary: {job_reqs.summary}
Technologies: {', '.join(job_reqs.technologies[:10])}
Requirements: {', '.join(job_reqs.requirements[:5]) if job_reqs.requirements else 'N/A'}
Industry: {', '.join(job_reqs.industry_tags[:5]) if job_reqs.industry_tags else 'N/A'}
"""
        
        # CRITICAL: Build STRICT job context with ONLY allowed technologies
        allowed_technologies = job.technologies if job.technologies else []
        allowed_techs_str = ', '.join(allowed_technologies) if allowed_technologies else 'None specified'
        
        # Build job context with explicit technology constraint
        job_context = f"""
Company: {job.company}
Role: {job.role}
Duration: {job.duration}
Location: {job.location}

**CRITICAL CONSTRAINT: ONLY THESE TECHNOLOGIES ARE ALLOWED:**
{allowed_techs_str}

**YOU MUST NOT MENTION ANY TECHNOLOGY NOT IN THE ABOVE LIST.**

Description: {job.description[:200] if job.description else 'N/A'}
"""
        
        # Original achievements
        bullets_text = "\n".join([f"- {bullet}" for bullet in original_bullets])
        
        if language == "en":
            prompt = f"""You are a CV writer. Your ONLY job is to adapt achievements while maintaining ABSOLUTE fidelity to the provided job data.

### STRICT RULES (VIOLATION = FAILURE):
1. **TECHNOLOGY CONSTRAINT:** You may ONLY mention technologies from this list: {allowed_techs_str}
   - If a keyword from job requirements matches, GREAT. Use it.
   - If a keyword does NOT appear in the allowed list, DO NOT mention it. Focus on transferable skills instead.
   
2. **FIDELITY CHECK:** After writing each bullet, verify:
   - Did I mention any technology NOT in the allowed list? If YES, rewrite that bullet.
   - Did I invent any achievement not in [ORIGINAL_ACHIEVEMENTS]? If YES, remove it.

3. **ADAPTATION STRATEGY:**
   - If achievement matches job keywords AND technology is in allowed list: Emphasize matching tech/skill/impact
   - If achievement matches keywords BUT technology NOT in allowed list: Focus on TRANSFERABLE skills only (leadership, problem-solving, business impact)
   - If achievement doesn't match: Rewrite to emphasize TRANSFERABLE skills
   - NEVER add technologies to match keywords if they're not in the allowed list

### YOUR PROCESS:
Step 1: Read [JOB_CONTEXT] and note the ALLOWED TECHNOLOGIES list.
Step 2: Read [ORIGINAL_ACHIEVEMENTS]
Step 3: For each achievement:
   a) Check if keywords from job requirements match
   b) If match AND technology is in allowed list → Emphasize it
   c) If match BUT technology NOT in allowed list → Focus on transferable skills only
   d) If no match → Rewrite to emphasize transferable skills
Step 4: Select top 3-5 bullets
Step 5: VERIFY each bullet: Does it mention any tech NOT in allowed list? If YES, remove that tech or rewrite.

### [JOB_REQUIREMENTS]:
{job_summary}

### [JOB_CONTEXT]:
{job_context}

### [ORIGINAL_ACHIEVEMENTS]:
{bullets_text}

### ALLOWED TECHNOLOGIES (READ THIS CAREFULLY):
{allowed_techs_str}

### OUTPUT
Output ONLY the adapted bullets (one per line, max 5). Each bullet must pass the fidelity check."""
            
            system = "You are a precision-focused CV writer. Your output MUST pass fidelity validation. Mentioning technologies not in the allowed list is a critical error."
        else:
            prompt = f"""IMPORTANTE: DEBES ESCRIBIR TODO EL CONTENIDO EN ESPAÑOL. NO uses inglés en ningún momento.

Eres un redactor de CVs. Tu ÚNICO trabajo es adaptar logros manteniendo FIDELIDAD ABSOLUTA a los datos del trabajo proporcionado.

### REGLAS ESTRICTAS (VIOLACIÓN = FALLO):
1. **RESTRICCIÓN DE TECNOLOGÍAS:** Solo puedes mencionar tecnologías de esta lista: {allowed_techs_str}
   - Si una keyword de los requisitos coincide, GENIAL. Úsala.
   - Si una keyword NO aparece en la lista permitida, NO la menciones. Enfócate en habilidades transferibles.

2. **VERIFICACIÓN DE FIDELIDAD:** Después de escribir cada bullet, verifica:
   - ¿Mencioné alguna tecnología que NO está en la lista permitida? Si SÍ, reescribe ese bullet.
   - ¿Inventé algún logro que no está en [LOGROS_ORIGINALES]? Si SÍ, elimínalo.

3. **ESTRATEGIA DE ADAPTACIÓN:**
   - Si el logro coincide con keywords Y la tecnología está en la lista permitida: Enfatiza la tecnología/habilidad/impacto coincidente
   - Si el logro coincide con keywords PERO la tecnología NO está en la lista permitida: Enfócate SOLO en habilidades transferibles (liderazgo, resolución de problemas, impacto de negocio)
   - Si el logro no coincide: Reescribe para enfatizar habilidades transferibles
   - NUNCA añadas tecnologías para coincidir con keywords si no están en la lista permitida

### TU PROCESO:
Paso 1: Lee [CONTEXTO_DEL_TRABAJO] y anota la lista de TECNOLOGÍAS PERMITIDAS.
Paso 2: Lee [LOGROS_ORIGINALES]
Paso 3: Para cada logro:
   a) Verifica si las keywords de los requisitos coinciden
   b) Si coincide Y la tecnología está en la lista permitida → Enfatízala
   c) Si coincide PERO la tecnología NO está en la lista permitida → Enfócate solo en habilidades transferibles
   d) Si no coincide → Reescribe para enfatizar habilidades transferibles
Paso 4: Selecciona los top 3-5 bullets
Paso 5: VERIFICA cada bullet: ¿Menciona alguna tecnología NO permitida? Si SÍ, elimina esa tecnología o reescribe.

### [REQUISITOS_DEL_TRABAJO]:
{job_summary}

### [CONTEXTO_DEL_TRABAJO]:
{job_context}

### [LOGROS_ORIGINALES]:
{bullets_text}

### TECNOLOGÍAS PERMITIDAS (LEE ESTO CUIDADOSAMENTE):
{allowed_techs_str}

### SALIDA
Devuelve SOLO los bullets adaptados (uno por línea, máx. 5). Cada bullet debe pasar la verificación de fidelidad."""
            
            system = "Eres un redactor de CVs en español enfocado en la precisión. DEBES escribir TODO en ESPAÑOL. Tu salida DEBE pasar la validación de fidelidad. Mencionar tecnologías no permitidas es un error crítico. NO uses inglés en ningún momento."
        
        try:
            adapted_response = await self.llm_service.generate(
                prompt=prompt,
                system=system,
                temperature=0.2,  # LOWER temperature for more deterministic output
                max_tokens=400
            )
            
            # Clean and parse adapted bullets
            adapted_bullets = self._clean_llm_response(adapted_response, "bullets")
            bullets = []
            for line in adapted_bullets.split("\n"):
                if not line.strip():
                    continue
                # Skip lines that are only introductory phrases
                line_lower = line.strip().lower()
                if line_lower.startswith(("here", "translation", "these", "the following", "output:", "aquí", "traducción", "estos", "salida:")):
                    continue
                
                # Clean bullet: remove leading dashes, numbers, bullets (•), and other bullet characters
                cleaned = self._clean_bullet_text(line)
                if cleaned:
                    bullets.append(cleaned)
            
            # CRITICAL: Post-LLM validation against allowed technologies
            validated_bullets = self._validate_bullets_fidelity(
                bullets,
                allowed_technologies,
                original_bullets
            )
            
            # Limit to 5 and fallback to original if empty or validation failed
            if not validated_bullets or len(validated_bullets) == 0:
                result = original_bullets[:5]
            else:
                result = validated_bullets[:5]
            
            # Cache result
            self._adaptation_cache[cache_key] = result
            return result
            
        except Exception:
            # Fallback to original if LLM fails
            result = original_bullets[:5]
            # Cache fallback result as well
            self._adaptation_cache[cache_key] = result
            return result
    
    def _clean_bullet_text(self, text: str) -> str:
        """
        Clean bullet text by removing leading bullet characters, dashes, numbers.
        
        Args:
            text: Bullet text that may contain leading bullet characters
            
        Returns:
            str: Cleaned bullet text without leading bullet characters
        """
        if not text:
            return ""
        
        cleaned = text.strip()
        # Remove leading bullet characters: •, ▪, ▸, ▶, ◦, ‣, ⁃, etc.
        cleaned = re.sub(r'^[-•▪▸▶◦‣⁃]\s*', '', cleaned)
        # Remove numbered bullets like "1. ", "2. ", "1) ", etc.
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned)
        # Remove leading dashes or asterisks
        cleaned = re.sub(r'^[-*]\s*', '', cleaned)
        # Remove any double spaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        
        return cleaned.strip()
    
    def _validate_bullets_fidelity(
        self,
        bullets: List[str],
        allowed_technologies: List[str],
        original_bullets: List[str]
    ) -> List[str]:
        """
        Validate bullets against allowed technologies to prevent hallucinations.
        
        Args:
            bullets: LLM-generated bullets to validate
            allowed_technologies: List of technologies allowed for this job
            original_bullets: Original bullets as fallback
            
        Returns:
            List[str]: Validated bullets (filtered bullets or original if validation fails)
        """
        if not bullets:
            return original_bullets[:5]
        
        if not allowed_technologies:
            # No restrictions, return as-is
            return bullets[:5]
        
        # Normalize allowed technologies for comparison
        allowed_techs_lower = {tech.lower() for tech in allowed_technologies}
        
        # Common technology keywords that should be checked
        # Extended list of common tech terms
        tech_keywords = {
            'aws', 'azure', 'gcp', 'google cloud', 'python', 'java', 'go', 'golang',
            'javascript', 'typescript', 'docker', 'kubernetes', 'k8s', 'terraform',
            'ansible', 'jenkins', 'gitlab', 'github', 'spring', 'spring boot',
            'react', 'vue', 'angular', 'node.js', 'express', 'fastapi', 'django',
            'flask', 'postgresql', 'mysql', 'mongodb', 'redis', 'elasticsearch',
            'tensorflow', 'pytorch', 'scikit-learn', 'pandas', 'numpy', 'jupyter',
            'langchain', 'openai', 'huggingface', 'rag', 'llm', 'llms', 'genai',
            'machine learning', 'deep learning', 'ai', 'ml', 'nlp', 'computer vision'
        }
        
        validated_bullets = []
        for bullet in bullets:
            if not bullet:
                continue
            
            bullet_lower = bullet.lower()
            contains_forbidden = False
            forbidden_techs = []
            
            # Check for forbidden technologies
            for tech_keyword in tech_keywords:
                if tech_keyword in bullet_lower:
                    # Check if this tech is in allowed list
                    if tech_keyword not in allowed_techs_lower:
                        # Also check for partial matches (e.g., "aws s3" contains "aws")
                        is_allowed = False
                        for allowed_tech in allowed_techs_lower:
                            if tech_keyword in allowed_tech or allowed_tech in tech_keyword:
                                is_allowed = True
                                break
                        
                        if not is_allowed:
                            contains_forbidden = True
                            forbidden_techs.append(tech_keyword)
            
            # Also check direct mentions of technologies (case-insensitive)
            words = bullet_lower.split()
            for word in words:
                # Clean word (remove punctuation)
                word_clean = re.sub(r'[^\w]', '', word)
                if len(word_clean) > 2:  # Only check words longer than 2 chars
                    if word_clean in tech_keywords and word_clean not in allowed_techs_lower:
                        # Check if it's a partial match
                        is_allowed = False
                        for allowed_tech in allowed_techs_lower:
                            if word_clean in allowed_tech or allowed_tech in word_clean:
                                is_allowed = True
                                break
                        
                        if not is_allowed:
                            contains_forbidden = True
                            if word_clean not in forbidden_techs:
                                forbidden_techs.append(word_clean)
            
            if contains_forbidden:
                # Try to remove forbidden tech mentions
                cleaned_bullet = bullet
                for forbidden_tech in forbidden_techs:
                    # Remove forbidden tech mentions (case-insensitive)
                    pattern = re.compile(re.escape(forbidden_tech), re.IGNORECASE)
                    cleaned_bullet = pattern.sub('', cleaned_bullet)
                
                # Clean up extra spaces
                cleaned_bullet = re.sub(r'\s+', ' ', cleaned_bullet).strip()
                
                # Only add if bullet still has meaningful content
                if len(cleaned_bullet) > 20:  # Minimum meaningful length
                    validated_bullets.append(cleaned_bullet)
                # Otherwise, skip this bullet
            else:
                # Bullet is valid, add as-is
                validated_bullets.append(bullet)
        
        # If validation removed too many bullets, use original as fallback
        if len(validated_bullets) < 2:
            return original_bullets[:5]
        
        return validated_bullets
    
    def _extract_profile_id(self, response: str, profiles: dict) -> Optional[str]:
        """
        Extract profile ID from classification response.
        
        Args:
            response: LLM classification response
            profiles: Available skill profiles dictionary
            
        Returns:
            Optional[str]: Profile ID or None if cannot determine
        """
        if not response:
            return None
        
        response_lower = response.strip().lower()
        
        # Check for exact match first
        for profile_id in profiles.keys():
            if profile_id.lower() in response_lower:
                return profile_id
        
        # Fuzzy matching based on keywords
        if any(word in response_lower for word in ['ia_specialist', 'ai specialist', 'ml specialist']):
            return 'ia_specialist'
        elif any(word in response_lower for word in ['java_backend', 'java backend', 'backend architect']):
            return 'java_backend_architect'
        elif any(word in response_lower for word in ['hybrid', 'ai java', 'both']):
            return 'hybrid_ai_java'
        elif any(word in response_lower for word in ['technical_leader', 'tech lead', 'cto', 'engineering manager', 'leader']):
            return 'technical_leader'
        
        return None
    
    def _get_start_year(self, period: str) -> int:
        """
        Extract start year from period string for chronological sorting.
        
        Args:
            period: Period string in format "YYYY - YYYY" or "YYYY - Presente" or "YYYY"
            
        Returns:
            int: Start year (0 if cannot parse, to put at end)
        """
        if not period:
            return 0
        
        try:
            # Handle "YYYY - Presente" or "YYYY - YYYY" format
            if " - " in period:
                # Split by " - " and take first part
                start_part = period.split(" - ")[0].strip()
                # Extract year (first 4 digits)
                year_match = None
                for i in range(len(start_part)):
                    if start_part[i:i+4].isdigit() and len(start_part[i:i+4]) == 4:
                        year_match = int(start_part[i:i+4])
                        break
                if year_match:
                    return year_match
            
            # Handle single year "YYYY"
            year_match = None
            for i in range(len(period)):
                if period[i:i+4].isdigit() and len(period[i:i+4]) == 4:
                    year_match = int(period[i:i+4])
                    break
            if year_match:
                return year_match
            
            return 0  # Cannot parse, put at end
        except Exception:
            return 0  # Cannot parse, put at end
    
    def _infer_education_city(self, institution: str) -> Optional[str]:
        """
        Infer city/location from institution name.
        
        Args:
            institution: Institution name
            
        Returns:
            Optional[str]: City/location if known, None otherwise
        """
        institution_lower = institution.lower()
        
        # Known institutions with their locations
        institution_location_map = {
            "lidr.co": "España, Remoto",
            "lidl": "España, Remoto",
            "universitat politècnica de catalunya": "Barcelona, España",
            "upc": "Barcelona, España",
            "universidad de santiago de chile": "Santiago, Chile",
            "usach": "Santiago, Chile",
            "inacap": "Chile",
            "hackio": "Online",
            "thepower": "Online",
            "the power": "Online",
        }
        
        # Check for exact match or partial match
        for key, location in institution_location_map.items():
            if key in institution_lower:
                return location
        
        # If no match found, return None
        return None
    

