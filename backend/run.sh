#!/bin/bash

# Quick start script for backend

echo "Starting Album Recognition API..."

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Error: Virtual environment not found. Run setup.sh first."
    exit 1
fi

# Load environment from env.local
if [ -f ".env.local" ]; then
    export $(cat .env.local | xargs)
else
    echo "Warning: .env.local not found"
fi

# Start the server
python main.py

