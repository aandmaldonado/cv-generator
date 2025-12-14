"""Pydantic models for CV data structures."""

from typing import List, Optional
from pydantic import BaseModel, Field


class CVContact(BaseModel):
    """Contact information model."""
    
    email: str
    phone: Optional[str] = None
    portfolio: str
    linkedin: str
    github: str


class CVExperience(BaseModel):
    """Experience entry model."""
    
    role: str
    company: str
    city: Optional[str] = None
    period: str
    bullets: List[str]
    technologies: List[str]


class TechSkillCategory(BaseModel):
    """Technical skills category model."""
    
    category: str
    skills: List[str]


class CVEducation(BaseModel):
    """Education entry model."""
    
    degree: str
    university: str
    city: Optional[str] = None
    period: str


class CVLanguage(BaseModel):
    """Language proficiency model."""
    
    language: str
    level: str


class CVData(BaseModel):
    """Complete CV data model."""
    
    fullName: str = Field(alias="fullName")
    degree: str
    contact: CVContact
    profile: str
    keySkills: List[str] = Field(alias="keySkills")
    experience: List[CVExperience]
    techSkills: List[TechSkillCategory] = Field(alias="techSkills")
    education: List[CVEducation]
    languages: List[CVLanguage]
    footer: str
    
    class Config:
        """Pydantic config."""
        
        populate_by_name = True

