# CV Generator API

API para generar CVs y cartas de presentación en PDF dinámicamente, migrado desde TypeScript a Python con FastAPI e integración con LLM.

## Características

- ✅ **Generación de CV en PDF desde datos YAML** (MVP - modo estático)
- ✅ **Generación dinámica de CV con LLM** basada en ofertas de trabajo
- ✅ **Generación de cartas de presentación** personalizadas con LLM
- ✅ **Soporte para múltiples idiomas** (Español/Inglés) con detección automática
- ✅ **Template HTML optimizado** para ATS y formato A4
- ✅ **API REST con FastAPI** y documentación automática
- ✅ **Interfaz web con Streamlit** para uso interactivo
- ✅ **Integración con Ollama** para generación de contenido inteligente
- ✅ **Búsqueda web opcional** (DuckDuckGo) para información de empresas
- ✅ **Optimizaciones de performance**: cache, paralelización, prompts eficientes

## Requisitos

- Python 3.9+
- **Ollama** instalado y ejecutándose localmente (o configuración para instancia remota)
- **WeasyPrint >=66.0** (requiere dependencias del sistema):
  - **macOS**: `brew install pango gdk-pixbuf libffi glib`
  - **Ubuntu/Debian**: `sudo apt-get install python3-dev python3-pip python3-cffi python3-brotli libpango-1.0-0 libharfbuzz0b libpangoft2-1.0-0`
  - **Fedora**: `sudo dnf install python3-devel python3-pip python3-cffi python3-brotli pango`

## Instalación

1. Clonar el repositorio:
```bash
git clone <repo-url>
cd cv-generator
```

2. Crear un entorno virtual:
```bash
python3 -m venv .venv-cv-generator
source .venv-cv-generator/bin/activate  # En Windows: .venv-cv-generator\Scripts\activate
```

3. Instalar dependencias:
```bash
pip install -r requirements.txt
```

4. Configurar variables de entorno:
```bash
cp .env.example .env
# Editar .env con tus configuraciones (ver sección de Configuración)
```

5. Instalar y configurar Ollama:
```bash
# macOS/Linux
curl -fsSL https://ollama.com/install.sh | sh

# Iniciar Ollama
ollama serve

# Descargar modelo (recomendado: llama3:8b)
ollama pull llama3:8b
```

## Configuración

### Variables de Entorno (.env)

```bash
# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434  # URL base de Ollama (default: localhost)
OLLAMA_MODEL=llama3:8b                   # Modelo a usar (default: llama3:8b)
OLLAMA_API_KEY=                          # API key (opcional, solo para instancias remotas)

# Web Search Configuration (opcional)
ENABLE_WEB_SEARCH=true                    # Habilitar búsqueda web con DuckDuckGo (default: true)

# Personal Information (opcional)
PHONE_NUMBER=+XX XXX XXX XXX              # Número de teléfono (sobrescribe portfolio.yaml)
```

### Portfolio Data

El sistema utiliza `app/data/portfolio.yaml` como base de conocimiento para la generación dinámica de CVs. Este archivo contiene:

- Información personal y de contacto
- Resumen profesional
- Experiencia laboral completa (empresas, posiciones, proyectos)
- Educación formal
- Skills showcase
- Tecnologías y competencias

**Importante**: El LLM solo utiliza información de este archivo. No inventa datos.

## Uso

### Ejecutar el servidor

#### Opción 1: Usando el script de inicio (recomendado)

```bash
./scripts/start_server.sh
```

Este script:
- Libera el puerto 8000 automáticamente si está en uso
- Configura las variables de entorno necesarias para WeasyPrint
- Inicia el servidor con auto-reload habilitado

#### Opción 2: Manualmente

```bash
# Activar entorno virtual
source .venv-cv-generator/bin/activate

# Configurar variables de entorno para WeasyPrint (macOS)
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# Iniciar servidor
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

El servidor estará disponible en `http://localhost:8000`

### Documentación de la API

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Endpoints

#### POST `/api/v1/cv/generate` (MVP - Modo Estático)

Genera un CV en PDF estático desde datos YAML para el idioma especificado.

**Request Body:**
```json
{
  "language": "en"
}
```

**Parámetros:**
- `language`: Idioma del CV (`en` para inglés, `es` para español)

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="CV_Alvaro_Maldonado_{lang}.pdf"`

**Ejemplo con cURL:**
```bash
# CV en inglés
curl -X POST "http://localhost:8000/api/v1/cv/generate" \
  -H "Content-Type: application/json" \
  -d '{"language": "en"}' \
  --output cv_en.pdf

# CV en español
curl -X POST "http://localhost:8000/api/v1/cv/generate" \
  -H "Content-Type: application/json" \
  -d '{"language": "es"}' \
  --output cv_es.pdf
```

#### POST `/api/v1/cv/generate/dynamic` (Generación Dinámica con LLM)

Genera un CV en PDF personalizado usando LLM basado en la descripción del trabajo. El idioma y el rol se detectan automáticamente.

**Request Body:**
```json
{
  "job_description": "We are looking for a Senior Backend Developer with experience in Java, Spring Boot, and Microservices..."
}
```

O con una URL:
```json
{
  "job_description": "https://example.com/job-posting"
}
```

**Parámetros:**
- `job_description`: Descripción del trabajo como texto o URL. Si se proporciona una URL, el sistema la obtendrá y parseará automáticamente. El idioma y el rol se detectan automáticamente.

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="CV_Dynamic_Alvaro_Maldonado.pdf"`

**Ejemplo con cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/cv/generate/dynamic" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "We are looking for a Senior Backend Developer with Java and Spring Boot experience..."
  }' \
  --output cv_dynamic.pdf
```

**Características:**
- ✅ Detección automática de idioma
- ✅ Detección automática de rol
- ✅ Adaptación de perfil profesional
- ✅ Selección inteligente de experiencias relevantes
- ✅ Adaptación de logros y tecnologías
- ✅ Habilidades clave adaptadas al trabajo
- ✅ Formato optimizado para ATS
- ✅ Máximo 2 páginas

#### POST `/api/v1/cover-letter/generate` (Carta de Presentación)

Genera una carta de presentación personalizada usando LLM basado en la descripción del trabajo. Si se proporciona el nombre de la empresa, se investiga información adicional para adaptar la carta a la cultura empresarial.

**Request Body:**
```json
{
  "job_description": "We are looking for a Senior Backend Developer...",
  "company": "Tech Corp"
}
```

**Parámetros:**
- `job_description`: Descripción del trabajo como texto o URL (requerido)
- `company`: Nombre de la empresa (opcional). Si se proporciona, se investigará información de la empresa usando DuckDuckGo para adaptar mejor la carta.

**Response:**
- Content-Type: `application/pdf`
- Content-Disposition: `attachment; filename="Cover_Letter_Alvaro_Maldonado.pdf"`

**Ejemplo con cURL:**
```bash
curl -X POST "http://localhost:8000/api/v1/cover-letter/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "job_description": "We are looking for a Senior Backend Developer...",
    "company": "Google"
  }' \
  --output cover_letter.pdf
```

**Características:**
- ✅ Detección automática de idioma
- ✅ Investigación opcional de información de empresa (DuckDuckGo)
- ✅ Saludo personalizado según empresa
- ✅ Menciona 2-3 experiencias más relevantes
- ✅ Adaptado a la cultura empresarial (si se proporciona empresa)
- ✅ Máximo 1 página

#### GET `/` y GET `/health`

Endpoints de health check.

### Interfaz Web con Streamlit

La aplicación incluye una interfaz web interactiva construida con Streamlit:

```bash
# Primero, asegúrate de que el servidor FastAPI esté ejecutándose
./scripts/start_server.sh

# En otra terminal, inicia Streamlit
./scripts/run_streamlit.sh
```

La interfaz web estará disponible en `http://localhost:8501` y te permitirá:

- ✅ Ingresar descripción del trabajo (texto o URL)
- ✅ Generar CV personalizado dinámicamente
- ✅ Opción de generar carta de presentación
- ✅ Campo para nombre de empresa (si se genera carta)
- ✅ Descarga directa de PDFs
- ✅ Vista previa de PDFs generados

### Ejemplos con Python

```python
import requests

# Generar CV estático
response = requests.post(
    "http://localhost:8000/api/v1/cv/generate",
    json={"language": "es"}
)
with open("cv_es.pdf", "wb") as f:
    f.write(response.content)

# Generar CV dinámico
response = requests.post(
    "http://localhost:8000/api/v1/cv/generate/dynamic",
    json={
        "job_description": "We are looking for a Senior Backend Developer..."
    }
)
with open("cv_dynamic.pdf", "wb") as f:
    f.write(response.content)

# Generar carta de presentación
response = requests.post(
    "http://localhost:8000/api/v1/cover-letter/generate",
    json={
        "job_description": "We are looking for a Senior Backend Developer...",
        "company": "Tech Corp"
    }
)
with open("cover_letter.pdf", "wb") as f:
    f.write(response.content)
```

## Estructura del Proyecto

```
cv-generator/
├── app/
│   ├── __init__.py
│   ├── main.py                          # FastAPI application
│   ├── models/
│   │   ├── __init__.py
│   │   ├── cv_models.py                 # Pydantic models para CV
│   │   ├── portfolio_models.py          # Pydantic models para portfolio.yaml
│   │   └── request_models.py            # Request models
│   ├── services/
│   │   ├── __init__.py
│   │   ├── cv_data_loader.py            # YAML loader (MVP)
│   │   ├── cv_generator.py              # HTML generator (MVP)
│   │   ├── pdf_generator.py             # PDF generator
│   │   ├── cv_customizer.py             # Generación dinámica con LLM
│   │   ├── cover_letter_generator.py    # Generación de cartas con LLM
│   │   ├── llm_service.py               # Servicio de integración con Ollama
│   │   ├── job_analyzer.py              # Análisis de ofertas de trabajo
│   │   ├── portfolio_loader.py          # Cargador de portfolio.yaml
│   │   ├── experience_retriever.py      # Retrieval de experiencias relevantes
│   │   └── web_research_service.py      # Búsqueda web (DuckDuckGo)
│   ├── templates/
│   │   ├── cv_template.html             # Template Jinja2 para CV
│   │   └── cover_letter_template.html   # Template Jinja2 para carta
│   ├── data/
│   │   ├── cv-data-es.yaml              # Datos en español (MVP)
│   │   ├── cv-data-en.yaml              # Datos en inglés (MVP)
│   │   └── portfolio.yaml                # Portfolio completo (base de conocimiento)
│   └── utils/
│       ├── __init__.py
│       └── template_helpers.py          # Jinja2 helpers
├── streamlit_app.py                     # Interfaz web Streamlit
├── scripts/
│   ├── start_server.sh                 # Script de inicio del servidor
│   └── run_streamlit.sh                 # Script para ejecutar Streamlit
├── .env.example                         # Ejemplo de variables de entorno
├── requirements.txt
├── README.md
└── .gitignore
```

## Testing

Ejecutar tests:

```bash
pytest
```

Con coverage:

```bash
pytest --cov=app --cov-report=html
```

## Desarrollo

### Variables de Entorno (macOS)

Si encuentras errores con WeasyPrint en macOS, asegúrate de configurar:

```bash
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
```

Estas variables están configuradas automáticamente en `scripts/start_server.sh`.

### Configuración de Ollama

**Local (por defecto):**
```bash
# Asegúrate de que Ollama esté corriendo
ollama serve

# Descarga un modelo
ollama pull llama3:8b

# El .env puede quedar vacío o con valores por defecto
```

**Remoto:**
```bash
# En .env
OLLAMA_BASE_URL=https://your-ollama-instance.com
OLLAMA_API_KEY=your-api-key
```

### Optimización de GPU (Apple Silicon)

Para aprovechar la GPU en Apple Silicon (M1/M2/M3/M4), asegúrate de usar el modelo Metal optimizado:

```bash
ollama pull llama3:8b
# Ollama detecta automáticamente Metal en Apple Silicon
```

### Agregar nuevos idiomas

1. Crear archivo YAML en `app/data/cv-data-{lang}.yaml`
2. Actualizar enum `Language` en `app/models/request_models.py`
3. Agregar validación en `app/services/cv_data_loader.py`

### Modificar templates

- **CV**: Editar `app/templates/cv_template.html` (Jinja2 template)
- **Carta de Presentación**: Editar `app/templates/cover_letter_template.html` (Jinja2 template)

Los estilos CSS están embebidos en los templates HTML. El servidor se recarga automáticamente con `--reload`.

### Modificar portfolio.yaml

El archivo `app/data/portfolio.yaml` contiene toda la información profesional que el LLM utiliza. Estructura:

```yaml
personal_info:
  name: "..."
  email: "..."
  # ...

professional_summary:
  short: "..."
  detailed: "..."

companies:
  - name: "..."
    positions:
      - role: "..."
        projects_worked_on: [...]

projects:
  proj_xyz:
    name: "..."
    achievements: [...]

education:
  - institution: "..."
    degree: "..."
```

**Importante**: El LLM solo utiliza datos de este archivo. No inventa información.

## Optimización y Performance

El sistema implementa varias optimizaciones para mejorar el rendimiento:

- **Cache en memoria**: Traducciones y adaptaciones se cachean automáticamente para evitar llamadas redundantes al LLM
- **Paralelización**: Llamadas al LLM se ejecutan en paralelo para múltiples experiencias usando `asyncio.gather`
- **Prompts optimizados**: Diseñados para ser concisos y eficientes, reduciendo tokens y tiempo de respuesta
- **Búsqueda web configurable**: Puede desactivarse para mayor velocidad (`ENABLE_WEB_SEARCH=false`)
- **Detección inteligente**: Idioma y rol se detectan automáticamente del `job_description`, reduciendo parámetros de entrada

### Configuración de Búsqueda Web

La búsqueda web de información de empresas es **opcional** y se puede desactivar para mayor velocidad:

```bash
# En tu .env
ENABLE_WEB_SEARCH=false  # Desactiva búsqueda web (más rápido)
# O no definir (default: true) - búsqueda web habilitada
```

**Nota:** La información de la empresa es opcional y solo enriquece la carta de presentación. El sistema funciona perfectamente sin ella.

### Tiempos de Generación

- **CV estático**: ~1-2 segundos
- **CV dinámico**: ~30-60 segundos (depende del modelo y GPU)
- **Carta de presentación**: ~20-40 segundos (sin búsqueda web) o ~40-60 segundos (con búsqueda web)

## Troubleshooting

### Ollama no responde

```bash
# Verificar que Ollama esté corriendo
curl http://localhost:11434/api/tags

# Reiniciar Ollama
ollama serve
```

### Error de WeasyPrint en macOS

```bash
# Instalar dependencias
brew install pango gdk-pixbuf libffi glib

# Configurar variables de entorno
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"
```

### Puerto 8000 en uso

```bash
# El script scripts/start_server.sh lo maneja automáticamente
# O manualmente:
lsof -ti:8000 | xargs kill -9
```

## Licencia

Ver [LICENSE](LICENSE) para más detalles.

## Contacto

Para consultas o sugerencias, contactar a [alvaro@almapi.dev](mailto:alvaro@almapi.dev)
