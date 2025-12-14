"""Service for loading CV data from YAML files."""

import yaml
from pathlib import Path
from typing import Optional
from app.models.cv_models import CVData


class CVDataLoader:
    """Service to load and validate CV data from YAML files."""
    
    def __init__(self, data_dir: Optional[Path] = None):
        """
        Initialize the CV data loader.
        
        Args:
            data_dir: Directory containing YAML files. Defaults to app/data/
        """
        if data_dir is None:
            # Get the app directory (parent of services)
            app_dir = Path(__file__).parent.parent
            data_dir = app_dir / "data"
        self.data_dir = data_dir
    
    def load_cv_data(self, language: str) -> CVData:
        """
        Load CV data for a specific language.
        
        Args:
            language: Language code ('en' or 'es')
            
        Returns:
            CVData: Validated CV data
            
        Raises:
            FileNotFoundError: If the YAML file doesn't exist
            ValueError: If the language is not supported or data is invalid
        """
        # Validate language
        if language not in ["en", "es"]:
            raise ValueError(f"Unsupported language: {language}. Supported: 'en', 'es'")
        
        # Determine filename
        filename = f"cv-data-{language}.yaml"
        filepath = self.data_dir / filename
        
        # Check if file exists
        if not filepath.exists():
            raise FileNotFoundError(
                f"CV data file not found: {filepath}. "
                f"Expected file at: {filepath.absolute()}"
            )
        
        # Load YAML
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML format in {filepath}: {e}")
        except Exception as e:
            raise ValueError(f"Error reading file {filepath}: {e}")
        
        # Validate and parse with Pydantic
        try:
            cv_data = CVData(**data)
            return cv_data
        except Exception as e:
            raise ValueError(
                f"Invalid CV data structure in {filepath}. "
                f"Validation error: {e}"
            )


# Singleton instance
_data_loader: Optional[CVDataLoader] = None


def get_data_loader(data_dir: Optional[Path] = None) -> CVDataLoader:
    """
    Get or create the CV data loader singleton.
    
    Args:
        data_dir: Optional directory for YAML files
        
    Returns:
        CVDataLoader: The data loader instance
    """
    global _data_loader
    if _data_loader is None:
        _data_loader = CVDataLoader(data_dir)
    return _data_loader

