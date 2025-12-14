"""Service for generating PDF from HTML."""

from io import BytesIO
from weasyprint import HTML as WeasyHTML, CSS
from app.services.cv_generator import CVGenerator
from app.models.cv_models import CVData


class PDFGenerator:
    """Service to generate PDF from HTML using WeasyPrint."""
    
    def __init__(self, cv_generator: CVGenerator = None):
        """
        Initialize the PDF generator.
        
        Args:
            cv_generator: CV generator instance. If None, creates a new one.
        """
        if cv_generator is None:
            cv_generator = CVGenerator()
        self.cv_generator = cv_generator
    
    def generate_pdf(self, data: CVData, language: str) -> bytes:
        """
        Generate PDF from CV data.
        
        Args:
            data: CV data model
            language: Language code ('en' or 'es')
            
        Returns:
            bytes: PDF file as bytes
        """
        # Generate HTML first
        html_content = self.cv_generator.generate_html(data, language)
        
        # Create HTML object
        html = WeasyHTML(string=html_content)
        
        # Configure PDF settings (A4, portrait, margins)
        # WeasyPrint uses CSS for page settings
        page_css = CSS(string="""
            @page {
                size: A4;
                margin: 18px;
            }
        """)
        
        # Generate PDF
        pdf_bytes = html.write_pdf(stylesheets=[page_css])
        
        return pdf_bytes

