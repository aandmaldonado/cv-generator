"""Helper functions for Jinja2 templates."""

import re
from datetime import datetime
from typing import Dict, List, Any
from jinja2 import Environment


def convert_quotes_to_bold(text: str) -> str:
    """
    Convert text between single quotes to bold HTML tags.
    
    Example: "This is 'important' text" -> "This is <strong>important</strong> text"
    
    Args:
        text: Input text with single quotes
        
    Returns:
        str: Text with quotes converted to <strong> tags
    """
    if not text:
        return ""
    return re.sub(r"'([^']*)'", r"<strong>\1</strong>", str(text))


def calculate_years_of_experience() -> int:
    """
    Calculate years of experience since 2010.
    
    Returns:
        int: Years of experience
    """
    current_year = datetime.now().year
    return current_year - 2010


def group_skills_by_category(skills: List[Dict[str, Any]]) -> Dict[str, List[str]]:
    """
    Group skills by category.
    
    Args:
        skills: List of skill dictionaries with 'category' and 'skills' keys
        
    Returns:
        Dict[str, List[str]]: Dictionary mapping category to list of skills
    """
    grouped: Dict[str, List[str]] = {}
    
    for skill in skills:
        category = skill.get("category", "")
        skill_names = skill.get("skills", [])
        
        if category:
            if category not in grouped:
                grouped[category] = []
            # Join skills in the same category as a comma-separated string
            grouped[category].extend(skill_names)
    
    return grouped


def register_jinja_filters(env: Environment) -> None:
    """
    Register helper functions as Jinja2 filters.
    
    Args:
        env: Jinja2 Environment instance
    """
    env.filters['convert_quotes_to_bold'] = convert_quotes_to_bold

