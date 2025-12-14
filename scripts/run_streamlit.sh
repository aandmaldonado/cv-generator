#!/bin/bash
# Script to start Streamlit app for CV Generator

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Activate virtual environment
source .venv-cv-generator/bin/activate

# Check if FastAPI server is running
echo "🔍 Verificando que el servidor FastAPI esté ejecutándose..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo "⚠️  El servidor FastAPI no está ejecutándose en http://localhost:8000"
    echo "💡 Por favor, ejecuta primero: ./scripts/start_server.sh"
    echo ""
    read -p "¿Deseas iniciar el servidor ahora? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "🚀 Iniciando servidor FastAPI..."
        "$SCRIPT_DIR/start_server.sh" &
        sleep 3
        echo "✅ Servidor iniciado"
    else
        echo "❌ No se puede continuar sin el servidor FastAPI"
        exit 1
    fi
else
    echo "✅ Servidor FastAPI está ejecutándose"
fi

echo ""
echo "🎨 Iniciando interfaz Streamlit..."
echo "📚 La aplicación estará disponible en: http://localhost:8501"
echo ""

# Start Streamlit
streamlit run streamlit_app.py --server.port 8501 --server.address 0.0.0.0

