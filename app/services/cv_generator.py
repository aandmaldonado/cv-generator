"""Service for generating CV HTML from templates."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from app.models.cv_models import CVData
from app.utils.template_helpers import (
    register_jinja_filters,
    calculate_years_of_experience,
    group_skills_by_category,
    convert_quotes_to_bold,
)


class CVGenerator:
    """Service to generate CV HTML from Jinja2 templates."""
    
    def __init__(self, template_dir: Path = None):
        """
        Initialize the CV generator.
        
        Args:
            template_dir: Directory containing Jinja2 templates. Defaults to app/templates/
        """
        if template_dir is None:
            # Get the app directory (parent of services)
            app_dir = Path(__file__).parent.parent
            template_dir = app_dir / "templates"
        
        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Register custom filters
        register_jinja_filters(self.env)
    
    def generate_html(self, data: CVData, language: str) -> str:
        """
        Generate CV HTML from template.
        
        Args:
            data: CV data model
            language: Language code ('en' or 'es')
            
        Returns:
            str: Rendered HTML string
        """
        # Prepare template data
        template_data = {
            "data": data,
            "language": language,
        }
        
        # Calculate years of experience and replace in profile
        years = calculate_years_of_experience()
        profile_text = data.profile.replace("{year}", str(years))
        
        # Apply quotes to bold conversion
        profile_text = convert_quotes_to_bold(profile_text)
        
        # Convert profile to list format for template processing
        template_data["profile_text"] = profile_text
        
        # Group skills by category for template
        skills_list = [{"category": cat.category, "skills": cat.skills} for cat in data.techSkills]
        grouped_skills = group_skills_by_category(skills_list)
        template_data["grouped_skills"] = grouped_skills
        
        # Load and render template
        template = self.env.get_template("cv_template.html")
        html = template.render(**template_data)
        
        return html

