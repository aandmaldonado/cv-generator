"""Service to load and validate portfolio.yaml data."""

import os
import yaml
from pathlib import Path
from typing import Optional
from app.models.portfolio_models import PortfolioData


class PortfolioLoader:
    """Load and validate portfolio data from YAML."""
    
    _instance: Optional['PortfolioLoader'] = None
    _portfolio_data: Optional[PortfolioData] = None
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def load_portfolio(self) -> PortfolioData:
        """
        Load portfolio data from YAML file.
        
        Returns:
            PortfolioData: Validated portfolio data
            
        Raises:
            FileNotFoundError: If portfolio.yaml doesn't exist
            ValueError: If YAML data is invalid
        """
        if self._portfolio_data is not None:
            return self._portfolio_data
        
        portfolio_path = Path(__file__).parent.parent / "data" / "portfolio.yaml"
        
        if not portfolio_path.exists():
            raise FileNotFoundError(f"Portfolio file not found: {portfolio_path}")
        
        with open(portfolio_path, "r", encoding="utf-8") as f:
            yaml_data = yaml.safe_load(f)
        
        if yaml_data is None:
            raise ValueError("Portfolio YAML file is empty")
        
        # Override phone from environment variable if provided
        phone_from_env = os.getenv("PHONE_NUMBER")
        if phone_from_env:
            if "personal_info" not in yaml_data:
                yaml_data["personal_info"] = {}
            yaml_data["personal_info"]["phone"] = phone_from_env
        
        try:
            self._portfolio_data = PortfolioData(**yaml_data)
        except Exception as e:
            raise ValueError(f"Invalid portfolio data: {str(e)}") from e
        
        return self._portfolio_data
    
    def reload_portfolio(self) -> PortfolioData:
        """
        Force reload portfolio data (clears cache).
        
        Returns:
            PortfolioData: Validated portfolio data
        """
        self._portfolio_data = None
        return self.load_portfolio()
