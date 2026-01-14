#!/bin/bash
# Upload SageMaker source code to S3
# This must be run before Lambda can trigger training jobs

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "======================================"
echo "Upload Source Code to S3"
echo "======================================"

# Load environment variables
if [ -f "../backend/.env.local" ]; then
    source <(grep -v '^#' ../backend/.env.local | sed 's/^/export /')
    echo -e "${GREEN}✓${NC} Loaded configuration from backend/.env.local"
else
    echo -e "${RED}✗${NC} backend/.env.local not found"
    exit 1
fi

BUCKET_NAME=${BUCKET_NAME:-$SAGEMAKER_BUCKET}
if [ -z "$BUCKET_NAME" ]; then
    echo -e "${RED}✗${NC} BUCKET_NAME or SAGEMAKER_BUCKET must be set"
    exit 1
fi

SOURCE_S3_PATH="s3://${BUCKET_NAME}/album-classifier/source"

echo "Bucket: $BUCKET_NAME"
echo "S3 Path: $SOURCE_S3_PATH"
echo ""

# Navigate to sagemaker directory
cd "$(dirname "$0")"
cd ../sagemaker

# Create temporary directory for source code
TEMP_DIR=$(mktemp -d)
echo "Creating source package in $TEMP_DIR..."

# Copy Python files
cp *.py $TEMP_DIR/ 2>/dev/null || true

# Copy requirements.txt
cp requirements.txt $TEMP_DIR/ 2>/dev/null || true

# Create tar.gz of source code
cd $TEMP_DIR
echo "Creating archive..."
tar -czf source.tar.gz *.py requirements.txt 2>/dev/null || tar -czf source.tar.gz *.py

# Upload to S3
echo "Uploading to S3..."
aws s3 cp source.tar.gz ${SOURCE_S3_PATH}/source.tar.gz

# Also upload individual files for easier updates
echo "Uploading individual files..."
aws s3 sync . ${SOURCE_S3_PATH}/ --exclude "*.tar.gz" --exclude "__pycache__/*"

echo -e "${GREEN}✓${NC} Source code uploaded to ${SOURCE_S3_PATH}"
echo ""
echo "Files uploaded:"
aws s3 ls ${SOURCE_S3_PATH}/ --recursive

# Clean up
rm -rf $TEMP_DIR

echo ""
echo "======================================"
echo "Upload Complete!"
echo "======================================"
echo ""
echo "Source code is now available at:"
echo "  ${SOURCE_S3_PATH}/source.tar.gz"
echo ""
echo "Next steps:"
echo "  1. Run setup_full_pipeline_aws.sh to create Lambda function"
echo "  2. Or use the source code in SageMaker Studio notebooks"
echo ""


