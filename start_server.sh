#!/bin/bash
# Startup script for agent-parser API server

set -e

echo "🚀 Starting agent-parser API server..."
echo ""
echo "Server will be available at:"
echo "  - API: http://localhost:8000"
echo "  - Swagger UI: http://localhost:8000/docs"
echo "  - ReDoc: http://localhost:8000/redoc"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Change to workspace directory
cd /workspaces/agent-parser

# Activate venv if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Start the server with auto-reload for development
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
