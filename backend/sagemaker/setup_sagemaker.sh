#!/bin/bash
# SageMaker Setup Script
# Automates the setup process for SageMaker deployment

set -e

echo "=============================="
echo "SageMaker Setup"
echo "=============================="

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

# Check Python version
echo ""
echo "Checking Python version..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2)
    print_success "Python $PYTHON_VERSION found"
else
    print_error "Python 3 not found. Please install Python 3.9 or higher."
    exit 1
fi

# Check if in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    print_info "Not in a virtual environment. Creating one..."
    
    if [ ! -d "venv" ]; then
        python3 -m venv venv
        print_success "Virtual environment created"
    fi
    
    print_info "Activate it with: source venv/bin/activate"
    source venv/bin/activate
    print_success "Virtual environment activated"
else
    print_success "Virtual environment detected"
fi

# Install dependencies
echo ""
echo "Installing SageMaker dependencies..."
pip install -q -r sagemaker/requirements.txt
print_success "Dependencies installed"

# Check for env file
echo ""
if [ ! -f "backend/.env.local" ]; then
    print_info "Creating backend/.env.local from template..."
    
    if [ -f "sagemaker/env.example" ]; then
        cp sagemaker/env.example backend/.env.local
        print_success "Created backend/.env.local"
        print_info "Please edit backend/.env.local and add your AWS configuration"
    else
        print_error "Template file not found"
    fi
else
    print_success "backend/.env.local exists"
fi

# Check AWS credentials
echo ""
echo "Checking AWS credentials..."
if command -v aws &> /dev/null; then
    if aws sts get-caller-identity &> /dev/null; then
        ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
        print_success "AWS credentials configured (Account: $ACCOUNT_ID)"
    else
        print_error "AWS credentials not configured"
        print_info "Run: aws configure"
    fi
else
    print_info "AWS CLI not installed (optional for local testing)"
fi

# Check for training data
echo ""
echo "Checking training data..."
if [ -d "backend/data/images" ] && [ "$(ls -A backend/data/images)" ]; then
    IMAGE_COUNT=$(ls -1 backend/data/images/*.jpg 2>/dev/null | wc -l)
    print_success "Found $IMAGE_COUNT training images"
else
    print_error "No training images found in backend/data/images"
    print_info "Please download images first using the backend API"
fi

# Check for manifest file
if [ -f "data/releases_manifest_50.jsonl" ] || [ -f "data/releases_manifest.jsonl" ]; then
    print_success "Manifest file found"
else
    print_error "Manifest file not found in data/"
fi

# Summary
echo ""
echo "=============================="
echo "Setup Summary"
echo "=============================="
echo ""

echo "Next steps:"
echo ""
echo "1. Test locally:"
echo "   python sagemaker/local_train.py --epochs 5"
echo ""
echo "2. Test inference:"
echo "   python sagemaker/local_predict.py --image backend/data/images/0.jpg"
echo ""
echo "3. Deploy to SageMaker:"
echo "   python sagemaker/deploy.py --local-mode  # Test first"
echo "   python sagemaker/deploy.py              # Full deployment"
echo ""

echo "For more information, see:"
echo "  - SAGEMAKER_QUICKSTART.md"
echo "  - sagemaker/README.md"
echo ""

print_success "Setup complete!"

