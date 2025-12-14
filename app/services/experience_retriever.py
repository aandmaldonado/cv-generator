"""Service to retrieve and filter relevant experiences from portfolio."""

from typing import List, Dict, Tuple
from pydantic import BaseModel
from app.models.portfolio_models import PortfolioData, Project
from app.services.job_analyzer import JobRequirements


class FilteredExperience(BaseModel):
    """Filtered experience with relevance scores."""
    
    project_id: str
    project: Project
    relevance_score: float
    matched_technologies: List[str]
    matched_tags: List[str]


class ExperienceRetriever:
    """Retrieve and filter relevant experiences from portfolio."""
    
    def filter_relevant_experiences(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        top_n: int = 5
    ) -> List[FilteredExperience]:
        """
        Filter and rank experiences by relevance to job requirements.
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            top_n: Number of top experiences to return
            
        Returns:
            List[FilteredExperience]: Top N most relevant experiences
        """
        scored_experiences = []
        
        for project_id, project in portfolio.projects.items():
            score, matched_techs, matched_tags = self._calculate_relevance_score(
                project, job_reqs
            )
            
            scored_experiences.append(
                FilteredExperience(
                    project_id=project_id,
                    project=project,
                    relevance_score=score,
                    matched_technologies=matched_techs,
                    matched_tags=matched_tags,
                )
            )
        
        # Sort by score (descending) and return top N
        scored_experiences.sort(key=lambda x: x.relevance_score, reverse=True)
        
        return scored_experiences[:top_n]
    
    def _calculate_relevance_score(
        self,
        project: Project,
        job_reqs: JobRequirements
    ) -> Tuple[float, List[str], List[str]]:
        """
        Calculate relevance score for a project.
        
        Returns:
            Tuple of (score, matched_technologies, matched_tags)
        """
        score = 0.0
        matched_techs = []
        matched_tags = []
        
        # Normalize technologies and tags for comparison
        project_techs_lower = [t.lower() for t in project.technologies]
        project_tags_lower = [t.lower() for t in project.tags]
        job_techs_lower = [t.lower() for t in job_reqs.technologies]
        job_tags_lower = [t.lower() for t in job_reqs.industry_tags]
        
        # Technology matching (weight: 0.4)
        tech_matches = 0
        for job_tech in job_techs_lower:
            # Check direct matches
            if job_tech in project_techs_lower:
                tech_matches += 1
                matched_techs.append(job_tech)
                continue
            
            # Check partial matches (e.g., "python" in "python/fastapi")
            for proj_tech in project_techs_lower:
                if job_tech in proj_tech or proj_tech in job_tech:
                    tech_matches += 1
                    matched_techs.append(job_tech)
                    break
        
        if job_techs_lower:
            tech_score = (tech_matches / len(job_techs_lower)) * 0.4
            score += tech_score
        
        # Tag/industry matching (weight: 0.3)
        tag_matches = 0
        for job_tag in job_tags_lower:
            if job_tag in project_tags_lower:
                tag_matches += 1
                matched_tags.append(job_tag)
        
        if job_tags_lower:
            tag_score = (tag_matches / len(job_tags_lower)) * 0.3 if job_tags_lower else 0
            score += tag_score
        
        # Role matching (weight: 0.2)
        if job_reqs.role:
            role_lower = job_reqs.role.lower()
            project_role_lower = project.role.lower()
            
            # Check for role keywords
            role_keywords = ["senior", "lead", "tech lead", "architect", "cto", "engineer", "developer"]
            for keyword in role_keywords:
                if keyword in role_lower and keyword in project_role_lower:
                    score += 0.2
                    break
        
        # Description keyword matching (weight: 0.1)
        if job_reqs.summary:
            job_summary_lower = job_reqs.summary.lower()
            project_desc_lower = project.description.lower()
            
            # Count matching keywords (basic word matching)
            job_words = set(job_summary_lower.split())
            project_words = set(project_desc_lower.split())
            
            # Remove common stop words
            stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with", "by"}
            job_words = {w for w in job_words if w not in stop_words and len(w) > 3}
            project_words = {w for w in project_words if w not in stop_words and len(w) > 3}
            
            if job_words:
                common_words = job_words.intersection(project_words)
                word_score = (len(common_words) / len(job_words)) * 0.1
                score += min(word_score, 0.1)  # Cap at 0.1
        
        # Normalize score to 0-1 range
        score = min(score, 1.0)
        
        return score, matched_techs, matched_tags
    
    def get_top_experiences_for_cv(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        max_projects: int = 7
    ) -> List[FilteredExperience]:
        """
        Get top experiences for CV generation.
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            max_projects: Maximum number of projects to include
            
        Returns:
            List[FilteredExperience]: Top experiences
        """
        return self.filter_relevant_experiences(portfolio, job_reqs, top_n=max_projects)
    
    def get_top_experiences_for_cover_letter(
        self,
        portfolio: PortfolioData,
        job_reqs: JobRequirements,
        max_projects: int = 3
    ) -> List[FilteredExperience]:
        """
        Get top experiences for cover letter (fewer, more focused).
        
        Args:
            portfolio: Portfolio data
            job_reqs: Job requirements
            max_projects: Maximum number of projects to include
            
        Returns:
            List[FilteredExperience]: Top experiences
        """
        return self.filter_relevant_experiences(portfolio, job_reqs, top_n=max_projects)

