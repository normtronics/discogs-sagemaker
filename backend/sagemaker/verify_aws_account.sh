#!/bin/bash
# Verify AWS Account Configuration
# Checks which account you're using and validates access

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo "======================================"
echo "AWS Account Verification"
echo "======================================"
echo ""

# Check if AWS CLI is installed
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗${NC} AWS CLI not installed"
    echo "Install with: brew install awscli (Mac) or pip install awscli"
    exit 1
fi

echo -e "${GREEN}✓${NC} AWS CLI installed"

# Check current profile
if [ -n "$AWS_PROFILE" ]; then
    echo -e "${BLUE}Profile:${NC} $AWS_PROFILE"
else
    echo -e "${BLUE}Profile:${NC} default"
fi

echo ""
echo "======================================"
echo "Account Information"
echo "======================================"

# Get account info
if ACCOUNT_INFO=$(aws sts get-caller-identity 2>&1); then
    ACCOUNT_ID=$(echo $ACCOUNT_INFO | jq -r '.Account')
    USER_ARN=$(echo $ACCOUNT_INFO | jq -r '.Arn')
    USER_ID=$(echo $ACCOUNT_INFO | jq -r '.UserId')
    
    echo -e "${GREEN}✓${NC} Successfully authenticated"
    echo ""
    echo -e "${BLUE}Account ID:${NC} $ACCOUNT_ID"
    echo -e "${BLUE}User ARN:${NC} $USER_ARN"
    echo -e "${BLUE}User ID:${NC} $USER_ID"
else
    echo -e "${RED}✗${NC} Failed to authenticate"
    echo ""
    echo "Error: $ACCOUNT_INFO"
    echo ""
    echo "Solutions:"
    echo "  1. Configure AWS CLI: aws configure --profile YOUR_PROFILE"
    echo "  2. Set profile: export AWS_PROFILE=YOUR_PROFILE"
    echo "  3. Check credentials: cat ~/.aws/credentials"
    exit 1
fi

# Check region
echo ""
echo "======================================"
echo "Region Configuration"
echo "======================================"

if [ -n "$AWS_PROFILE" ]; then
    REGION=$(aws configure get region --profile $AWS_PROFILE 2>/dev/null || echo "not set")
else
    REGION=$(aws configure get region 2>/dev/null || echo "not set")
fi

if [ "$REGION" != "not set" ]; then
    echo -e "${GREEN}✓${NC} Region: $REGION"
else
    echo -e "${YELLOW}⚠${NC} Region not set (will use default)"
fi

# Check S3 access
echo ""
echo "======================================"
echo "S3 Access"
echo "======================================"

if aws s3 ls &> /dev/null; then
    BUCKET_COUNT=$(aws s3 ls | wc -l | tr -d ' ')
    echo -e "${GREEN}✓${NC} S3 access verified ($BUCKET_COUNT buckets)"
    
    # List buckets
    if [ $BUCKET_COUNT -gt 0 ]; then
        echo ""
        echo "Your S3 buckets:"
        aws s3 ls | sed 's/^/  /'
    fi
else
    echo -e "${RED}✗${NC} No S3 access"
fi

# Check SageMaker access
echo ""
echo "======================================"
echo "SageMaker Access"
echo "======================================"

if aws sagemaker list-training-jobs --max-results 1 &> /dev/null; then
    echo -e "${GREEN}✓${NC} SageMaker access verified"
    
    # Count recent training jobs
    JOB_COUNT=$(aws sagemaker list-training-jobs --query 'TrainingJobSummaries | length(@)' --output text)
    echo "  Recent training jobs: $JOB_COUNT"
else
    echo -e "${YELLOW}⚠${NC} Limited or no SageMaker access"
fi

# Check for env.local
echo ""
echo "======================================"
echo "Project Configuration"
echo "======================================"

if [ -f "../backend/.env.local" ]; then
    echo -e "${GREEN}✓${NC} backend/.env.local exists"
    
    # Extract values
    PROFILE_IN_FILE=$(grep "^AWS_PROFILE" ../backend/.env.local | cut -d'=' -f2 | tr -d ' "'"'"'')
    ROLE_IN_FILE=$(grep "^SAGEMAKER_ROLE" ../backend/.env.local | cut -d'=' -f2 | tr -d ' "'"'"'')
    BUCKET_IN_FILE=$(grep "^SAGEMAKER_BUCKET" ../backend/.env.local | cut -d'=' -f2 | tr -d ' "'"'"'')
    
    if [ -n "$PROFILE_IN_FILE" ]; then
        echo -e "  ${BLUE}AWS_PROFILE:${NC} $PROFILE_IN_FILE"
        
        if [ "$AWS_PROFILE" != "$PROFILE_IN_FILE" ] && [ -n "$AWS_PROFILE" ]; then
            echo -e "  ${YELLOW}⚠ Warning:${NC} Environment profile ($AWS_PROFILE) differs from .env.local ($PROFILE_IN_FILE)"
        fi
    fi
    
    if [ -n "$ROLE_IN_FILE" ]; then
        ROLE_ACCOUNT=$(echo $ROLE_IN_FILE | cut -d':' -f5)
        echo -e "  ${BLUE}SAGEMAKER_ROLE:${NC} $ROLE_IN_FILE"
        
        if [ "$ROLE_ACCOUNT" != "$ACCOUNT_ID" ]; then
            echo -e "  ${RED}✗ Error:${NC} Role is in account $ROLE_ACCOUNT but you're using account $ACCOUNT_ID"
        else
            echo -e "  ${GREEN}✓${NC} Role matches current account"
        fi
    fi
    
    if [ -n "$BUCKET_IN_FILE" ]; then
        echo -e "  ${BLUE}SAGEMAKER_BUCKET:${NC} $BUCKET_IN_FILE"
        
        # Check if bucket exists
        if aws s3 ls s3://$BUCKET_IN_FILE &> /dev/null; then
            echo -e "  ${GREEN}✓${NC} Bucket exists and is accessible"
        else
            echo -e "  ${RED}✗${NC} Bucket not found or not accessible"
        fi
    fi
else
    echo -e "${RED}✗${NC} backend/.env.local not found"
    echo "  Create it from: cp backend/.env.example backend/.env.local"
fi

# Summary
echo ""
echo "======================================"
echo "Summary"
echo "======================================"
echo ""
echo "Current AWS Account: $ACCOUNT_ID"
echo "Profile: ${AWS_PROFILE:-default}"
echo "Region: $REGION"
echo ""

if [ "$ROLE_ACCOUNT" = "$ACCOUNT_ID" ] 2>/dev/null; then
    echo -e "${GREEN}✓${NC} All checks passed! You're ready to use SageMaker."
    echo ""
    echo "Next steps:"
    echo "  1. Upload data: python sagemaker/upload_data_s3.py"
    echo "  2. Train model: python sagemaker/deploy.py"
else
    echo -e "${YELLOW}⚠${NC} Some issues detected. Review the output above."
fi

echo ""

