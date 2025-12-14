#!/bin/bash
# Script to start CV Generator API server

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Kill any existing uvicorn processes on port 8000
echo "🔍 Checking for existing processes on port 8000..."
if lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  Found process(es) using port 8000, killing them..."
    pkill -f "uvicorn.*8000" || lsof -ti:8000 | xargs kill -9 2>/dev/null
    sleep 2
    echo "✅ Port 8000 is now free"
else
    echo "✅ Port 8000 is available"
fi

# Activate virtual environment
source .venv-cv-generator/bin/activate

# Set environment variables for WeasyPrint on macOS
export PKG_CONFIG_PATH="/opt/homebrew/lib/pkgconfig:$PKG_CONFIG_PATH"
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# Start uvicorn server with --reload for auto-reload on code changes
echo ""
echo "🚀 Starting CV Generator API server (with --reload enabled)..."
echo "📚 Documentation: http://localhost:8000/docs"
echo "🔍 Health check: http://localhost:8000/health"
echo "🔄 Auto-reload: Enabled (code changes will restart server automatically)"
echo ""
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

