"""Streamlit interface for CV Generator API."""

import streamlit as st
import httpx
import os
import base64
from io import BytesIO
from typing import Optional

# Configuration
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
CV_API_ENDPOINT = f"{API_BASE_URL}/api/v1/cv/generate/dynamic"
COVER_LETTER_API_ENDPOINT = f"{API_BASE_URL}/api/v1/cover-letter/generate"

# Page configuration
st.set_page_config(
    page_title="CV Generator",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 1rem;
    }
    .info-box {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1f77b4;
        margin-bottom: 1rem;
    }
    .success-box {
        background-color: #d4edda;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #28a745;
        margin-top: 1rem;
    }
</style>
""", unsafe_allow_html=True)

def generate_cv(job_description: str) -> Optional[bytes]:
    """
    Call the CV generation API.
    
    Args:
        job_description: Job description text or URL (language and role will be auto-detected)
        
    Returns:
        PDF bytes if successful, None otherwise
    """
    try:
        payload = {
            "job_description": job_description
        }
        
        with httpx.Client(timeout=300.0) as client:  # 5 minutes timeout
            response = client.post(CV_API_ENDPOINT, json=payload)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as e:
        st.error(f"Error al comunicarse con la API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return None

def extract_company_name(text: str) -> Optional[str]:
    """
    Extract company name from job description text.
    
    Args:
        text: Job description text
        
    Returns:
        Optional[str]: Extracted company name or None
    """
    import re
    
    # Common programming language keywords that should NOT be considered company names
    programming_languages = ['java', 'python', 'javascript', 'typescript', 'c++', 'c#', 'go', 'rust', 
                            'kotlin', 'swift', 'php', 'ruby', 'scala', 'html', 'css', 'sql', 'bash']
    
    # Common patterns for company names (more specific patterns)
    patterns = [
        # Patterns like "Company: Tech Corp", "Empresa: Tech Corp"
        r'(?:company|empresa|at|en)\s*(?:name)?[:\s]+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s&.,-]{2,25}?)(?:\s+(?:is|está|we|somos|buscamos|looking)|,|\.|$)',
        # Patterns like "About Microsoft", "En Google"
        r'(?:about|en|at|para|in)\s+([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ\s&.,-]{2,25}?)(?:\s+(?:we|we\'re|somos|estamos|buscamos)|$)',
        # Patterns like "Microsoft is looking", "Google busca"
        r'([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ]+){0,2}?)\s+(?:is\s+looking|está\s+buscando|buscamos|we\s+are)',
        # Common company name patterns (capitalized words with suffixes)
        r'([A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ]+(?:\s+[A-ZÁÉÍÓÚÑ][a-zA-ZáéíóúñÁÉÍÓÚÑ]+){0,2}?)\s+(?:Inc|Corp|Ltd|S\.A\.|S\.L\.|Tech|Technologies|Systems|Solutions|Group)',
    ]
    
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            company = matches[0].strip()
            # Clean up company name - remove trailing common words
            company = re.sub(r'\s+(inc|corp|ltd|s\.a\.|s\.l\.|tech|technologies|systems|solutions|group)$', '', company, flags=re.IGNORECASE)
            # Remove leading articles
            company = re.sub(r'^(the|la|el|las|los)\s+', '', company, flags=re.IGNORECASE)
            # Clean up multiple spaces
            company = re.sub(r'\s+', ' ', company).strip()
            # Validate length and doesn't contain common unwanted words
            unwanted_words = ['looking', 'buscando', 'developer', 'engineer', 'inglés', 'spanish', 'experience', 'experiencia']
            
            # Check if it's a programming language (single word and matches language list)
            company_lower = company.lower()
            if company_lower in programming_languages:
                continue  # Skip if it's a programming language
            
            if (3 <= len(company) <= 50 and 
                not any(word.lower() in company_lower for word in unwanted_words) and
                not company_lower.startswith('is ') and
                not company_lower.startswith('está ') and
                company_lower != 'java'):  # Explicitly exclude 'java'
                return company
    
    return None

def generate_cover_letter(job_description: str, company: Optional[str] = None) -> Optional[bytes]:
    """
    Call the cover letter generation API.
    
    Args:
        job_description: Job description text or URL (language and role will be auto-detected)
        company: Company name (optional, for company research)
        
    Returns:
        PDF bytes if successful, None otherwise
    """
    try:
        payload = {
            "job_description": job_description
        }
        
        if company:
            payload["company"] = company
        
        with httpx.Client(timeout=300.0) as client:  # 5 minutes timeout
            response = client.post(COVER_LETTER_API_ENDPOINT, json=payload)
            response.raise_for_status()
            return response.content
    except httpx.HTTPError as e:
        st.error(f"Error al comunicarse con la API: {str(e)}")
        return None
    except Exception as e:
        st.error(f"Error inesperado: {str(e)}")
        return None

def main():
    """Main Streamlit app."""
    
    # Header
    st.markdown('<div class="main-header">📄 CV Generator</div>', unsafe_allow_html=True)
    
    # Sidebar - Info
    with st.sidebar:
        st.header("ℹ️ Información")
        st.markdown("""
        Esta herramienta genera:
        - **CV personalizado** basado en la descripción del trabajo
        - **Carta de presentación** (opcional) adaptada a la cultura de la empresa
        
        El sistema detecta automáticamente:
        - El idioma de la oferta (español/inglés)
        - El rol al que se postula
        
        **Nota:** La generación puede tardar 30-60 segundos ya que usa un LLM.
        """)
        
        st.divider()
        
        st.header("🔧 Configuración")
        api_url = st.text_input(
            "URL de la API",
            value=API_BASE_URL,
            help="URL base del servidor FastAPI"
        )
        
        if api_url != API_BASE_URL:
            st.info(f"Usando: {api_url}")
        
        st.divider()
        
        # Verificar estado del servidor
        st.header("🔍 Estado del Servidor")
        try:
            with httpx.Client(timeout=2.0) as client:
                response = client.get(f"{api_url}/health")
                if response.status_code == 200:
                    st.success("✅ Servidor FastAPI está ejecutándose")
                else:
                    st.warning(f"⚠️  Servidor responde con código: {response.status_code}")
        except httpx.ConnectError:
            st.error("❌ Servidor FastAPI no está ejecutándose")
            st.info("💡 Ejecuta: `./scripts/start_server.sh` en otra terminal para iniciar el servidor")
            st.code("cd /Users/almapi/Documents/GitHub/cv-generator\n./scripts/start_server.sh", language="bash")
        except Exception as e:
            st.warning(f"⚠️  No se pudo verificar el estado: {str(e)}")
    
    # Checkbox for cover letter (outside form to be reactive)
    want_cover_letter = st.checkbox(
        "📄 También generar carta de presentación",
        help="Si está marcado, se generará una carta de presentación adaptada a la cultura de la empresa usando DuckDuckGo."
    )
    
    # Company input (only if cover letter is checked) - outside form to be reactive
    company = None
    if want_cover_letter:
        # Show input for manual company entry
        company = st.text_input(
            "Nombre de la empresa",
            placeholder="Ej: Google, Microsoft, Tech Corp, etc.",
            help="Ingresa el nombre de la empresa manualmente. Si se proporciona, el sistema investigará información de la empresa usando DuckDuckGo para adaptar mejor la carta a su cultura."
        )
    
    # Main form
    with st.form("cv_generation_form"):
        st.header("Generar CV Personalizado")
        
        # Job description textarea
        job_description = st.text_area(
            "Descripción del trabajo *",
            placeholder="Pega aquí la descripción del trabajo o una URL con la oferta...",
            height=300,
            help="Pega el texto completo de la oferta o una URL. El sistema detectará automáticamente el idioma y el rol."
        )
        
        # Submit button
        submitted = st.form_submit_button(
            "🚀 Generar",
            use_container_width=True,
            type="primary"
        )
    
    # Handle form submission
    if submitted:
        if not job_description.strip():
            st.error("⚠️ Por favor, ingresa la descripción del trabajo")
            return
        
        # Generate CV
        with st.spinner("⏳ Generando CV personalizado... Esto puede tardar 30-60 segundos."):
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Simulate progress (API call is blocking)
            status_text.text("🔄 Analizando descripción del trabajo...")
            progress_bar.progress(20)
            
            status_text.text("🌐 Detectando idioma...")
            progress_bar.progress(35)
            
            status_text.text("🎯 Extrayendo rol...")
            progress_bar.progress(50)
            
            status_text.text("🤖 Generando CV con LLM...")
            progress_bar.progress(65)
            
            status_text.text("📝 Adaptando contenido...")
            progress_bar.progress(80)
            
            # Make API call for CV
            cv_pdf_bytes = generate_cv(job_description=job_description)
            
            progress_bar.progress(100)
            status_text.empty()
        
        # Handle CV result
        if cv_pdf_bytes:
            st.markdown('<div class="success-box">✅ CV generado exitosamente</div>', unsafe_allow_html=True)
            
            # Create download button for CV
            cv_filename = f"CV_Alvaro_Maldonado.pdf"
            
            st.download_button(
                label="📥 Descargar CV",
                data=cv_pdf_bytes,
                file_name=cv_filename,
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="cv_download"
            )
            
            # Show CV PDF preview
            st.divider()
            st.header("Vista previa del CV")
            
            # Embed PDF using base64 encoding
            base64_cv = base64.b64encode(cv_pdf_bytes).decode('utf-8')
            cv_display = f'<iframe src="data:application/pdf;base64,{base64_cv}" width="100%" height="800px" type="application/pdf"></iframe>'
            st.markdown(cv_display, unsafe_allow_html=True)
            
            st.info("💡 Si la vista previa no funciona, descarga el PDF usando el botón de arriba.")
        else:
            st.error("❌ Error al generar el CV. Por favor, verifica que el servidor esté ejecutándose.")
        
        # Generate Cover Letter if requested
        if want_cover_letter:
            st.divider()
            
            with st.spinner("⏳ Generando carta de presentación... Esto puede tardar 30-60 segundos adicionales."):
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                # Simulate progress
                status_text.text("🔍 Investigando información de la empresa con DuckDuckGo...")
                progress_bar.progress(25)
                
                status_text.text("🤖 Generando carta con LLM...")
                progress_bar.progress(50)
                
                status_text.text("📝 Adaptando a la cultura de la empresa...")
                progress_bar.progress(75)
                
                # Make API call for cover letter
                cover_letter_pdf_bytes = generate_cover_letter(
                    job_description=job_description,
                    company=company.strip() if company and company.strip() else None
                )
                
                progress_bar.progress(100)
                status_text.empty()
            
            # Handle Cover Letter result
            if cover_letter_pdf_bytes:
                st.markdown('<div class="success-box">✅ Carta de presentación generada exitosamente</div>', unsafe_allow_html=True)
                
                # Create download button for cover letter
                cover_letter_filename = f"Cover_Letter_Alvaro_Maldonado.pdf"
                
                st.download_button(
                    label="📥 Descargar Carta de Presentación",
                    data=cover_letter_pdf_bytes,
                    file_name=cover_letter_filename,
                    mime="application/pdf",
                    use_container_width=True,
                    type="primary",
                    key="cover_letter_download"
                )
                
                # Show Cover Letter PDF preview
                st.divider()
                st.header("Vista previa de la Carta de Presentación")
                
                # Embed PDF using base64 encoding
                base64_cl = base64.b64encode(cover_letter_pdf_bytes).decode('utf-8')
                cl_display = f'<iframe src="data:application/pdf;base64,{base64_cl}" width="100%" height="800px" type="application/pdf"></iframe>'
                st.markdown(cl_display, unsafe_allow_html=True)
                
                st.info("💡 Si la vista previa no funciona, descarga el PDF usando el botón de arriba.")
            else:
                st.error("❌ Error al generar la carta de presentación. Por favor, verifica que el servidor esté ejecutándose.")

if __name__ == "__main__":
    main()

