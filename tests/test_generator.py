"""Tests for CV generation services."""

import pytest
from app.services.cv_data_loader import CVDataLoader
from app.services.cv_generator import CVGenerator
from app.services.pdf_generator import PDFGenerator


def test_load_cv_data_en():
    """Test loading CV data for English."""
    loader = CVDataLoader()
    data = loader.load_cv_data("en")
    
    assert data.fullName == "Álvaro Andrés Maldonado Pinto"
    assert data.degree is not None
    assert data.contact.email is not None
    assert len(data.experience) > 0
    assert len(data.education) > 0
    assert len(data.techSkills) > 0
    assert len(data.languages) > 0


def test_load_cv_data_es():
    """Test loading CV data for Spanish."""
    loader = CVDataLoader()
    data = loader.load_cv_data("es")
    
    assert data.fullName == "Álvaro Andrés Maldonado Pinto"
    assert data.degree is not None
    assert data.contact.email is not None
    assert len(data.experience) > 0
    assert len(data.education) > 0
    assert len(data.techSkills) > 0
    assert len(data.languages) > 0


def test_load_cv_data_invalid_language():
    """Test loading CV data with invalid language."""
    loader = CVDataLoader()
    with pytest.raises(ValueError, match="Unsupported language"):
        loader.load_cv_data("fr")


def test_generate_html_en():
    """Test HTML generation for English."""
    loader = CVDataLoader()
    generator = CVGenerator()
    
    data = loader.load_cv_data("en")
    html = generator.generate_html(data, "en")
    
    assert "<!DOCTYPE html>" in html
    assert "Álvaro Andrés Maldonado Pinto" in html
    assert "Profile" in html
    assert len(html) > 0


def test_generate_html_es():
    """Test HTML generation for Spanish."""
    loader = CVDataLoader()
    generator = CVGenerator()
    
    data = loader.load_cv_data("es")
    html = generator.generate_html(data, "es")
    
    assert "<!DOCTYPE html>" in html
    assert "Álvaro Andrés Maldonado Pinto" in html
    assert "Perfil" in html
    assert len(html) > 0


def test_generate_pdf_en():
    """Test PDF generation for English."""
    loader = CVDataLoader()
    pdf_generator = PDFGenerator()
    
    data = loader.load_cv_data("en")
    pdf_bytes = pdf_generator.generate_pdf(data, "en")
    
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")  # PDF magic number


def test_generate_pdf_es():
    """Test PDF generation for Spanish."""
    loader = CVDataLoader()
    pdf_generator = PDFGenerator()
    
    data = loader.load_cv_data("es")
    pdf_bytes = pdf_generator.generate_pdf(data, "es")
    
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")  # PDF magic number

