"""Service for web research on companies and roles."""

import os
from typing import Optional, Dict, Any
from urllib.parse import quote_plus
from duckduckgo_search import DDGS
import warnings
warnings.filterwarnings('ignore', message='.*duckduckgo_search.*has been renamed.*')
import httpx
from bs4 import BeautifulSoup
from pydantic import BaseModel


class CompanyResearch(BaseModel):
    """Company research information."""
    
    company_name: str
    role: Optional[str] = None
    overview: str
    industry: Optional[str] = None
    values_culture: Optional[str] = None
    recent_projects: Optional[str] = None
    size_location: Optional[str] = None
    role_context: Optional[str] = None
    sources: list[str] = []


class WebResearchService:
    """Service for researching companies and roles from the web."""
    
    def __init__(self, enabled: bool = True):
        """
        Initialize web research service.
        
        Args:
            enabled: If False, skips web search and returns minimal info (for speed)
        """
        self.cache: Dict[str, CompanyResearch] = {}
        # Check if web search is enabled via environment variable
        self.enabled = enabled and os.getenv("ENABLE_WEB_SEARCH", "true").lower() == "true"
    
    async def research_company(
        self,
        company_name: str,
        role: Optional[str] = None,
        timeout: float = 15.0  # 15 second timeout for entire research
    ) -> CompanyResearch:
        """
        Research company information from the web.
        
        Args:
            company_name: Company name
            role: Target role (optional)
            timeout: Maximum time to wait for research (seconds)
            
        Returns:
            CompanyResearch: Structured company information
        """
        # Check cache
        cache_key = f"{company_name}:{role or ''}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # If web search is disabled, return minimal info quickly
        if not self.enabled:
            research = CompanyResearch(
                company_name=company_name,
                role=role,
                overview=f"{company_name} is a technology company.",
                industry=None,
                values_culture=None,
                recent_projects=None,
                size_location=None,
                role_context=None,
                sources=[]
            )
            # Cache minimal result
            self.cache[cache_key] = research
            return research
        
        # Perform web search (with quick fallback and timeout)
        import asyncio
        try:
            # Run search in executor to avoid blocking (DDGS is not async)
            loop = asyncio.get_event_loop()
            search_results = await asyncio.wait_for(
                loop.run_in_executor(None, self._search_company, company_name, role),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            # Quick fallback if search times out - don't wait forever
            print(f"Warning: Company research timed out after {timeout}s")
            search_results = []
        except Exception as e:
            # Quick fallback on any error
            print(f"Warning: Company research failed: {e}")
            search_results = []
        
        # Extract information from search results (quick extraction)
        overview = self._extract_overview(search_results, company_name)
        industry = self._extract_industry(search_results)
        values_culture = self._extract_values_culture(search_results)
        recent_projects = self._extract_recent_projects(search_results)
        size_location = self._extract_size_location(search_results)
        role_context = self._extract_role_context(search_results, role)
        sources = [result.get("href", "") for result in search_results[:3]]  # Reduced from 5 to 3
        
        research = CompanyResearch(
            company_name=company_name,
            role=role,
            overview=overview,
            industry=industry,
            values_culture=values_culture,
            recent_projects=recent_projects,
            size_location=size_location,
            role_context=role_context,
            sources=sources
        )
        
        # Cache result
        self.cache[cache_key] = research
        
        return research
    
    def _search_company(
        self,
        company_name: str,
        role: Optional[str] = None,
        max_results: int = 5  # Reduced from 10 to 5 for speed
    ) -> list[Dict[str, Any]]:
        """
        Search for company information using DuckDuckGo.
        
        Args:
            company_name: Company name
            role: Target role (optional)
            max_results: Maximum search results (reduced for speed)
            
        Returns:
            List of search results
        """
        try:
            # Build search query (simplified for speed)
            if role:
                query = f"{company_name} {role}"
            else:
                query = f"{company_name} company"
            
            # Search with reduced results for speed
            # Note: timeout is handled at async level via asyncio.wait_for
            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=max_results))
            
            return results
        except Exception as e:
            # Fallback if DuckDuckGo fails - return empty list quickly
            print(f"Warning: DuckDuckGo search failed: {e}")
            return []
    
    def _extract_overview(
        self,
        search_results: list[Dict[str, Any]],
        company_name: str
    ) -> str:
        """Extract company overview from search results."""
        overview_parts = []
        
        for result in search_results[:3]:
            title = result.get("title", "")
            body = result.get("body", "")
            
            if company_name.lower() in title.lower() or company_name.lower() in body.lower():
                overview_parts.append(body[:200])  # Limit length
        
        if overview_parts:
            return " ".join(overview_parts)[:500]
        
        return f"{company_name} is a technology company."
    
    def _extract_industry(self, search_results: list[Dict[str, Any]]) -> Optional[str]:
        """Extract industry information."""
        industries = [
            "fintech", "banking", "finance",
            "retail", "e-commerce",
            "healthcare", "health tech",
            "education", "edtech",
            "ai", "machine learning", "startup",
            "telecom", "telecommunications",
            "software", "saas", "b2b", "b2c"
        ]
        
        for result in search_results:
            text = f"{result.get('title', '')} {result.get('body', '')}".lower()
            for industry in industries:
                if industry in text:
                    return industry.title()
        
        return None
    
    def _extract_values_culture(
        self,
        search_results: list[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract company values and culture."""
        keywords = ["culture", "values", "mission", "vision", "team"]
        
        for result in search_results:
            body = result.get("body", "").lower()
            if any(keyword in body for keyword in keywords):
                return result.get("body", "")[:300]
        
        return None
    
    def _extract_recent_projects(
        self,
        search_results: list[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract recent projects or news."""
        keywords = ["project", "launch", "release", "announcement", "new"]
        
        for result in search_results:
            body = result.get("body", "").lower()
            if any(keyword in body for keyword in keywords):
                return result.get("body", "")[:300]
        
        return None
    
    def _extract_size_location(
        self,
        search_results: list[Dict[str, Any]]
    ) -> Optional[str]:
        """Extract company size and location."""
        keywords = ["employees", "headquarters", "location", "office", "remote"]
        
        for result in search_results:
            body = result.get("body", "")
            if any(keyword in body.lower() for keyword in keywords):
                return body[:300]
        
        return None
    
    def _extract_role_context(
        self,
        search_results: list[Dict[str, Any]],
        role: Optional[str]
    ) -> Optional[str]:
        """Extract context about the role in the company."""
        if not role:
            return None
        
        for result in search_results:
            body = result.get("body", "")
            if role.lower() in body.lower():
                return body[:300]
        
        return None
    
    def format_company_info(self, research: CompanyResearch) -> str:
        """
        Format company research into text for LLM prompts.
        
        Args:
            research: Company research data
            
        Returns:
            str: Formatted company information
        """
        parts = []
        
        parts.append(f"Company: {research.company_name}")
        
        if research.industry:
            parts.append(f"Industry: {research.industry}")
        
        if research.overview:
            parts.append(f"Overview: {research.overview}")
        
        if research.values_culture:
            parts.append(f"Culture & Values: {research.values_culture}")
        
        if research.recent_projects:
            parts.append(f"Recent Projects: {research.recent_projects}")
        
        if research.size_location:
            parts.append(f"Size & Location: {research.size_location}")
        
        if research.role and research.role_context:
            parts.append(f"Role Context ({research.role}): {research.role_context}")
        
        return "\n".join(parts)

