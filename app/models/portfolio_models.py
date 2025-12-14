"""Pydantic models for portfolio.yaml data structures."""

from typing import List, Optional, Dict, Any, Union, TYPE_CHECKING
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from typing import ForwardRef


class PersonalInfo(BaseModel):
    """Personal information model."""
    
    name: str
    nationality: Optional[str] = None
    marital_status: Optional[str] = None
    children: Optional[str] = None
    age: Optional[str] = None
    title: str
    phone: Optional[str] = None
    email: str
    location: Optional[str] = None
    website: str
    linkedin: str
    github: str


class ProfessionalSummary(BaseModel):
    """Professional summary model."""
    
    short: str
    detailed: str
    motivation_for_change: Optional["MotivationForChange"] = None
    faqs: Optional[List[str]] = None
    philosophy_and_interests: Optional[List["PhilosophyItem"]] = None


class Project(BaseModel):
    """Project model from portfolio."""
    
    id: str
    name: str
    company_ref: str
    role: str
    duration: str
    description: str
    key_responsibilities: Optional[List[str]] = None
    key_challenges: Optional[List[str]] = None
    technologies: List[str]
    hardware: Optional[List[str]] = None
    achievements: List[str]
    business_impact: str
    tags: List[str]
    faqs: Optional[List[str]] = None


class CompanyPosition(BaseModel):
    """Company position model."""
    
    role: str
    duration: str
    location: Optional[str] = None
    projects_worked_on: List[str]


class Job(BaseModel):
    """Job model from portfolio."""
    
    company: str
    role: str
    duration: str
    location: str
    description: str
    key_responsibilities: Optional[List[str]] = None
    key_challenges: Optional[List[str]] = None
    technologies: List[str]
    hardware: Optional[List[str]] = None
    achievements: List[str]
    tags: List[str]


class Company(BaseModel):
    """Company model."""
    
    id: str
    name: str
    positions: List[CompanyPosition]


class SkillShowcase(BaseModel):
    """Skill showcase model."""
    
    description: str
    key_technologies: Optional[List[str]] = Field(None, alias="key_technologies")
    key_skills: Optional[List[str]] = Field(None, alias="key_skills")
    
    class Config:
        populate_by_name = True


class EducationSummary(BaseModel):
    """Education summary model."""
    
    short: str
    detailed: str
    faqs: Optional[List[str]] = None


class EducationEntry(BaseModel):
    """Education entry model."""
    
    degree: str
    institution: str
    period: str
    details: Optional[str] = None
    knowledge_acquired: Optional[List[str]] = None
    tools_technologies: Optional[List[str]] = None
    tags: Optional[List[str]] = None


class SkillCategory(BaseModel):
    """Skill category model."""
    
    category: str
    items: List[str]


class ExpertiseLevel(BaseModel):
    """Expertise level model."""
    
    level: str
    years: Optional[Union[int, str]] = None  # Can be int (5) or string ("15+")
    note: Optional[str] = None


class LanguageInfo(BaseModel):
    """Language information model."""
    
    name: str
    level: str
    details: Optional[str] = None
    context_of_use: Optional[List[str]] = None


class Availability(BaseModel):
    """Availability model."""
    
    status: str
    notice_period: Optional[str] = None
    remote_work: Optional[str] = None
    interview_scheduling: Optional[str] = None
    faqs: Optional[List[str]] = None


class WorkPermit(BaseModel):
    """Work permit model."""
    
    status: str
    target_country: Optional[str] = None
    faqs: Optional[List[str]] = None


class SalaryExpectations(BaseModel):
    """Salary expectations model."""
    
    notes: str
    faqs: Optional[List[str]] = None


class MotivationForChange(BaseModel):
    """Motivation for change model."""
    
    description: str = Field(alias="description")
    faqs: Optional[List[str]] = Field(None, alias="faqs")
    
    class Config:
        populate_by_name = True


class ProfessionalConditions(BaseModel):
    """Professional conditions model."""
    
    availability: Availability
    work_permit: WorkPermit
    salary_expectations: SalaryExpectations
    motivation_for_change: MotivationForChange


class PhilosophyItem(BaseModel):
    """Philosophy and interests item model."""
    
    title: str
    description: str
    faqs: Optional[List[str]] = None


class CVSkillProfileCategory(BaseModel):
    """CV skill profile category model."""
    
    category: str
    items: List[str]


class PortfolioData(BaseModel):
    """Complete portfolio data model."""
    
    personal_info: PersonalInfo
    professional_summary: ProfessionalSummary
    jobs: Optional[List[Job]] = None  # New structure: list of jobs
    projects: Optional[Dict[str, Project]] = None  # Legacy structure: projects dict
    companies: Optional[Dict[str, Company]] = None  # Legacy structure: companies dict
    skills_showcase: Optional[Dict[str, SkillShowcase]] = None
    education_summary: Optional[EducationSummary] = None
    education: List[EducationEntry]
    skills: List[SkillCategory]
    expertise_levels: Optional[Dict[str, ExpertiseLevel]] = None
    languages: List[LanguageInfo]
    professional_conditions: Optional[ProfessionalConditions] = None
    philosophy_and_interests: Optional[List[PhilosophyItem]] = None  # Can also be in professional_summary
    cv_skill_profiles: Optional[Dict[str, List[CVSkillProfileCategory]]] = None
