#!/bin/bash

# Verification script to check if everything is set up correctly

echo "🔍 Verifying Album Recognition System Setup"
echo "==========================================="
echo ""

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

# Check Python
echo -n "Checking Python 3... "
if command -v python3 &> /dev/null; then
    VERSION=$(python3 --version | cut -d' ' -f2)
    echo -e "${GREEN}✓ Found Python $VERSION${NC}"
else
    echo -e "${RED}✗ Python 3 not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check Node.js
echo -n "Checking Node.js... "
if command -v node &> /dev/null; then
    VERSION=$(node --version)
    echo -e "${GREEN}✓ Found Node.js $VERSION${NC}"
else
    echo -e "${RED}✗ Node.js not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check data file
echo -n "Checking data file... "
if [ -f "data/releases_manifest_50.jsonl" ]; then
    LINES=$(wc -l < data/releases_manifest_50.jsonl)
    echo -e "${GREEN}✓ Found $LINES releases${NC}"
else
    echo -e "${RED}✗ Data file not found${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check backend files
echo -n "Checking backend files... "
BACKEND_FILES=(
    "backend/main.py"
    "backend/model_service.py"
    "backend/model_trainer.py"
    "backend/image_downloader.py"
    "backend/data_loader.py"
    "backend/requirements.txt"
)
MISSING_BACKEND=0
for file in "${BACKEND_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_BACKEND=$((MISSING_BACKEND + 1))
    fi
done
if [ $MISSING_BACKEND -eq 0 ]; then
    echo -e "${GREEN}✓ All backend files present${NC}"
else
    echo -e "${RED}✗ Missing $MISSING_BACKEND backend files${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check frontend files
echo -n "Checking frontend files... "
FRONTEND_FILES=(
    "frontend/package.json"
    "frontend/next.config.ts"
    "frontend/src/app/page.tsx"
    "frontend/src/app/layout.tsx"
)
MISSING_FRONTEND=0
for file in "${FRONTEND_FILES[@]}"; do
    if [ ! -f "$file" ]; then
        MISSING_FRONTEND=$((MISSING_FRONTEND + 1))
    fi
done
if [ $MISSING_FRONTEND -eq 0 ]; then
    echo -e "${GREEN}✓ All frontend files present${NC}"
else
    echo -e "${RED}✗ Missing $MISSING_FRONTEND frontend files${NC}"
    ERRORS=$((ERRORS + 1))
fi

# Check if backend venv exists
echo -n "Checking backend virtual environment... "
if [ -d "backend/venv" ]; then
    echo -e "${GREEN}✓ Virtual environment exists${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment not found${NC}"
    echo "  Run: cd backend && ./setup.sh"
fi

# Check if frontend node_modules exists
echo -n "Checking frontend dependencies... "
if [ -d "frontend/node_modules" ]; then
    echo -e "${GREEN}✓ Node modules installed${NC}"
else
    echo -e "${YELLOW}⚠ Node modules not installed${NC}"
    echo "  Run: cd frontend && npm install"
fi

# Check for .env.local files
echo -n "Checking backend .env.local... "
if [ -f "backend/.env.local" ]; then
    echo -e "${GREEN}✓ Found${NC}"
    if grep -q "DISCOGS_API_TOKEN=your_discogs_token_here" "backend/.env.local" 2>/dev/null; then
        echo -e "${YELLOW}  ⚠ Remember to set your DISCOGS_API_TOKEN${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Not found - copy from .env.example${NC}"
fi

# Summary
echo ""
echo "==========================================="
if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ Setup verification complete!${NC}"
    echo ""
    echo "Next steps:"
    echo "1. cd backend && ./setup.sh (if not done)"
    echo "2. cd frontend && npm install (if not done)"
    echo "3. Configure backend/.env.local with your Discogs token"
    echo "4. Follow QUICKSTART.md to run the app"
else
    echo -e "${RED}❌ Found $ERRORS error(s)${NC}"
    echo "Please fix the errors above and try again."
    exit 1
fi

