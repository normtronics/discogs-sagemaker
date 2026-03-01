#!/bin/bash

# Setup script for backend

echo "Setting up Album Recognition Backend..."

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install requirements
echo "Installing dependencies..."
pip install --upgrade pip

# Install PyTorch first (fixes "No matching distribution" on some systems)
echo "Installing PyTorch..."
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu || true

pip install -r requirements.txt

# Create necessary directories
echo "Creating directories..."
mkdir -p data/images
mkdir -p models

# Check for .env.local file
if [ ! -f ".env.local" ]; then
    echo "Warning: .env.local not found. Please create it from .env.example"
    echo "Don't forget to add your DISCOGS_API_TOKEN!"
fi

echo ""
echo "Setup complete! 🎉"
echo ""
echo "Next steps:"
echo "1. Copy .env.example to .env.local and add your Discogs API token"
echo "2. Run: python main.py"
echo "3. Download images: curl -X POST http://localhost:8000/api/download-images"
echo "4. Train model: curl -X POST http://localhost:8000/api/train"

