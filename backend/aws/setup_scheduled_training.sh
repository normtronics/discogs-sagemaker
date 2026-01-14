#!/bin/bash
# Setup Scheduled Training on AWS
# Creates Lambda function and EventBridge rule for automated training

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "======================================"
echo "Setup Scheduled Training on AWS"
echo "======================================"

# Load environment variables
if [ -f "../backend/.env.local" ]; then
    source <(grep -v '^#' ../backend/.env.local | sed 's/^/export /')
    echo -e "${GREEN}✓${NC} Loaded configuration from backend/.env.local"
else
    echo -e "${RED}✗${NC} backend/.env.local not found"
    exit 1
fi

# Check required variables
if [ -z "$SAGEMAKER_ROLE" ] || [ -z "$SAGEMAKER_BUCKET" ] || [ -z "$AWS_REGION" ]; then
    echo -e "${RED}✗${NC} Missing required environment variables"
    echo "Required: SAGEMAKER_ROLE, SAGEMAKER_BUCKET, AWS_REGION"
    exit 1
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓${NC} AWS Account ID: $ACCOUNT_ID"

# Function name
FUNCTION_NAME="trigger-album-classifier-training"
LAMBDA_ROLE_NAME="AlbumClassifierLambdaRole"

echo ""
echo "======================================"
echo "Step 1: Create Lambda Execution Role"
echo "======================================"

# Create Lambda execution role if it doesn't exist
if aws iam get-role --role-name $LAMBDA_ROLE_NAME 2>/dev/null; then
    echo -e "${YELLOW}ℹ${NC} Role $LAMBDA_ROLE_NAME already exists"
else
    # Create trust policy
    cat > /tmp/lambda-trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "lambda.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

    aws iam create-role \
        --role-name $LAMBDA_ROLE_NAME \
        --assume-role-policy-document file:///tmp/lambda-trust-policy.json
    
    echo -e "${GREEN}✓${NC} Created role $LAMBDA_ROLE_NAME"
    
    # Attach policies
    aws iam attach-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
    
    # Create and attach SageMaker policy
    cat > /tmp/lambda-sagemaker-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "sagemaker:CreateTrainingJob",
        "sagemaker:DescribeTrainingJob",
        "sagemaker:StopTrainingJob"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${SAGEMAKER_BUCKET}/*",
        "arn:aws:s3:::${SAGEMAKER_BUCKET}"
      ]
    },
    {
      "Effect": "Allow",
      "Action": "iam:PassRole",
      "Resource": "${SAGEMAKER_ROLE}"
    }
  ]
}
EOF

    aws iam put-role-policy \
        --role-name $LAMBDA_ROLE_NAME \
        --policy-name SageMakerAccessPolicy \
        --policy-document file:///tmp/lambda-sagemaker-policy.json
    
    echo -e "${GREEN}✓${NC} Attached policies to role"
    
    # Wait for role to propagate
    echo -e "${YELLOW}ℹ${NC} Waiting for role to propagate..."
    sleep 10
fi

LAMBDA_ROLE_ARN="arn:aws:iam::${ACCOUNT_ID}:role/${LAMBDA_ROLE_NAME}"

echo ""
echo "======================================"
echo "Step 2: Create Lambda Function"
echo "======================================"

# Create deployment package
cd "$(dirname "$0")"
mkdir -p /tmp/lambda-package
cp lambda_trigger_training.py /tmp/lambda-package/lambda_function.py

cd /tmp/lambda-package
zip -q lambda-package.zip lambda_function.py

# Create or update Lambda function
if aws lambda get-function --function-name $FUNCTION_NAME 2>/dev/null; then
    echo -e "${YELLOW}ℹ${NC} Updating existing Lambda function"
    
    aws lambda update-function-code \
        --function-name $FUNCTION_NAME \
        --zip-file fileb://lambda-package.zip
    
    aws lambda update-function-configuration \
        --function-name $FUNCTION_NAME \
        --environment "Variables={SAGEMAKER_ROLE=${SAGEMAKER_ROLE},SAGEMAKER_BUCKET=${SAGEMAKER_BUCKET},AWS_REGION=${AWS_REGION}}" \
        --timeout 300 \
        --memory-size 256
else
    echo -e "${YELLOW}ℹ${NC} Creating new Lambda function"
    
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.11 \
        --role $LAMBDA_ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://lambda-package.zip \
        --timeout 300 \
        --memory-size 256 \
        --environment "Variables={SAGEMAKER_ROLE=${SAGEMAKER_ROLE},SAGEMAKER_BUCKET=${SAGEMAKER_BUCKET},AWS_REGION=${AWS_REGION}}"
fi

echo -e "${GREEN}✓${NC} Lambda function deployed"

# Clean up
rm -rf /tmp/lambda-package /tmp/lambda-trust-policy.json /tmp/lambda-sagemaker-policy.json

echo ""
echo "======================================"
echo "Step 3: Create EventBridge Schedule"
echo "======================================"

RULE_NAME="album-classifier-weekly-training"

# Create EventBridge rule
if aws events describe-rule --name $RULE_NAME 2>/dev/null; then
    echo -e "${YELLOW}ℹ${NC} Rule $RULE_NAME already exists"
else
    aws events put-rule \
        --name $RULE_NAME \
        --description "Trigger album classifier training weekly" \
        --schedule-expression "cron(0 2 ? * MON *)" \
        --state ENABLED
    
    echo -e "${GREEN}✓${NC} Created EventBridge rule"
fi

# Add Lambda permission for EventBridge
aws lambda add-permission \
    --function-name $FUNCTION_NAME \
    --statement-id ${RULE_NAME}-permission \
    --action lambda:InvokeFunction \
    --principal events.amazonaws.com \
    --source-arn arn:aws:events:${AWS_REGION}:${ACCOUNT_ID}:rule/${RULE_NAME} \
    2>/dev/null || echo -e "${YELLOW}ℹ${NC} Permission already exists"

# Add Lambda as target
aws events put-targets \
    --rule $RULE_NAME \
    --targets "Id=1,Arn=arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:${FUNCTION_NAME},Input='{\"instance_type\":\"ml.p3.2xlarge\",\"epochs\":10,\"batch_size\":16,\"learning_rate\":0.001}'"

echo -e "${GREEN}✓${NC} Configured EventBridge target"

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Lambda Function: $FUNCTION_NAME"
echo "Schedule: Every Monday at 2:00 AM UTC"
echo "Instance Type: ml.p3.2xlarge"
echo "Epochs: 10"
echo ""
echo "Test the function:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME /tmp/output.json"
echo ""
echo "View logs:"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
echo "Disable schedule:"
echo "  aws events disable-rule --name $RULE_NAME"
echo ""
echo "Enable schedule:"
echo "  aws events enable-rule --name $RULE_NAME"
echo ""

