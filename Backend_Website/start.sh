#!/bin/bash

echo "🚀 Starting FastAPI Application..."

# Stop on error
set -e

# Config
VENV_NAME="venv"
APP_MODULE="main:app"
HOST="0.0.0.0"
PORT="8000"
REQUIREMENTS_FILE="requirements.txt"

# Check Python
if ! command -v python3 &> /dev/null
then
    echo "❌ Python3 is not installed. Please install Python first."
    exit 1
fi

# Create venv if not exists
if [ ! -d "$VENV_NAME" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv $VENV_NAME
fi

# Activate venv (Scripts/ on Windows Git Bash, bin/ on Linux/macOS)
echo "🔑 Activating virtual environment..."
if [ -f "$VENV_NAME/Scripts/activate" ]; then
    source "$VENV_NAME/Scripts/activate"
else
    source "$VENV_NAME/bin/activate"
fi

# Install dependencies
if [ -f "$REQUIREMENTS_FILE" ]; then
    echo "📥 Installing dependencies..."
    pip install -r $REQUIREMENTS_FILE
else
    echo "⚠️ requirements.txt not found. Skipping install."
fi

# Run FastAPI
echo "🔥 Starting Uvicorn server..."
uvicorn $APP_MODULE \
  --host $HOST \
  --port $PORT \
  --reload