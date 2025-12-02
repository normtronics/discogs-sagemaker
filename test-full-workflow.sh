#!/bin/bash

# Complete workflow test script
# This script tests the entire pipeline

set -e  # Exit on error

echo "🚀 Testing Complete Album Recognition Workflow"
echo "==============================================="
echo ""

BASE_URL="http://localhost:8000"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check if API is running
check_api() {
    echo -n "Checking if API is running... "
    if curl -s "$BASE_URL/api/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ API is running${NC}"
        return 0
    else
        echo -e "${RED}✗ API is not running${NC}"
        echo "Please start the backend with: cd backend && ./run.sh"
        return 1
    fi
}

# Function to check health
check_health() {
    echo ""
    echo "📊 Checking System Health..."
    HEALTH=$(curl -s "$BASE_URL/api/health")
    echo "$HEALTH" | jq '.'
    
    MODEL_LOADED=$(echo "$HEALTH" | jq -r '.model_loaded')
    DATA_LOADED=$(echo "$HEALTH" | jq -r '.data_loaded')
    
    if [ "$MODEL_LOADED" = "true" ] && [ "$DATA_LOADED" = "true" ]; then
        echo -e "${GREEN}✓ System is healthy${NC}"
    else
        echo -e "${YELLOW}⚠ System needs setup${NC}"
        if [ "$DATA_LOADED" = "false" ]; then
            echo "  - Data not loaded"
        fi
        if [ "$MODEL_LOADED" = "false" ]; then
            echo "  - Model not trained"
        fi
    fi
}

# Function to download images
download_images() {
    echo ""
    echo "📥 Downloading Images..."
    echo "This may take 1-2 minutes due to rate limiting..."
    
    RESULT=$(curl -s -X POST "$BASE_URL/api/download-images")
    echo "$RESULT" | jq '.'
    
    DOWNLOADED=$(echo "$RESULT" | jq -r '.downloaded')
    if [ "$DOWNLOADED" -gt 0 ]; then
        echo -e "${GREEN}✓ Downloaded $DOWNLOADED images${NC}"
    fi
}

# Function to train model
train_model() {
    echo ""
    echo "🧠 Training Model..."
    echo "This may take 5-10 minutes..."
    
    RESULT=$(curl -s -X POST "$BASE_URL/api/train")
    echo "$RESULT" | jq '.'
    
    SUCCESS=$(echo "$RESULT" | jq -r '.success')
    if [ "$SUCCESS" = "true" ]; then
        ACCURACY=$(echo "$RESULT" | jq -r '.accuracy')
        echo -e "${GREEN}✓ Model trained with ${ACCURACY}% accuracy${NC}"
    fi
}

# Function to list releases
list_releases() {
    echo ""
    echo "📀 Available Releases..."
    RELEASES=$(curl -s "$BASE_URL/api/releases")
    COUNT=$(echo "$RELEASES" | jq -r '.count')
    echo "Total releases: $COUNT"
    echo ""
    echo "First 5 releases:"
    echo "$RELEASES" | jq -r '.releases[0:5][] | "\(.title) - \(.artists | join(", "))"'
}

# Main workflow
main() {
    # Check if API is running
    if ! check_api; then
        exit 1
    fi
    
    # Check health
    check_health
    
    # Ask user what to do
    echo ""
    echo "What would you like to do?"
    echo "1) Full setup (download images + train model)"
    echo "2) Download images only"
    echo "3) Train model only"
    echo "4) List releases"
    echo "5) Check health"
    echo "6) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice
    
    case $choice in
        1)
            download_images
            train_model
            check_health
            ;;
        2)
            download_images
            ;;
        3)
            train_model
            ;;
        4)
            list_releases
            ;;
        5)
            check_health
            ;;
        6)
            echo "Goodbye!"
            exit 0
            ;;
        *)
            echo "Invalid choice"
            exit 1
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}✅ Workflow completed!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. Open http://localhost:3000 in your browser"
    echo "2. Upload an album cover image"
    echo "3. Get predictions!"
}

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo -e "${YELLOW}⚠ Warning: 'jq' is not installed${NC}"
    echo "Install it for better output: brew install jq"
    echo "Continuing anyway..."
fi

# Run main workflow
main

