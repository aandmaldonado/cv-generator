"""Tests for FastAPI endpoints."""

import pytest
from httpx import AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_root_endpoint():
    """Test root endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json()["message"] == "CV Generator API"


@pytest.mark.asyncio
async def test_health_endpoint():
    """Test health endpoint."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_generate_cv_en():
    """Test CV generation for English."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/cv/generate",
            json={"language": "en"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "CV_Alvaro_Maldonado_en.pdf" in response.headers["content-disposition"]
        assert len(response.content) > 0  # PDF should have content


@pytest.mark.asyncio
async def test_generate_cv_es():
    """Test CV generation for Spanish."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/cv/generate",
            json={"language": "es"}
        )
        assert response.status_code == 200
        assert response.headers["content-type"] == "application/pdf"
        assert "CV_Alvaro_Maldonado_es.pdf" in response.headers["content-disposition"]
        assert len(response.content) > 0  # PDF should have content


@pytest.mark.asyncio
async def test_generate_cv_invalid_language():
    """Test CV generation with invalid language."""
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/api/v1/cv/generate",
            json={"language": "fr"}
        )
        assert response.status_code == 422  # Validation error

