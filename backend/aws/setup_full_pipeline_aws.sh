#!/bin/bash
# Setup Full Pipeline Training on AWS
# Creates Lambda function, uploads source code, and sets up EventBridge schedule

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "======================================"
echo "Setup Full Pipeline Training on AWS"
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
if [ -z "$SAGEMAKER_ROLE" ] || [ -z "$BUCKET_NAME" ] || [ -z "$AWS_REGION" ]; then
    echo -e "${RED}✗${NC} Missing required environment variables"
    echo "Required: SAGEMAKER_ROLE, BUCKET_NAME, AWS_REGION"
    exit 1
fi

BUCKET_NAME=${BUCKET_NAME:-$SAGEMAKER_BUCKET}
if [ -z "$BUCKET_NAME" ]; then
    echo -e "${RED}✗${NC} BUCKET_NAME or SAGEMAKER_BUCKET must be set"
    exit 1
fi

# Get AWS account ID
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
echo -e "${GREEN}✓${NC} AWS Account ID: $ACCOUNT_ID"

# Function name
FUNCTION_NAME="trigger-full-pipeline-training"
LAMBDA_ROLE_NAME="FullPipelineLambdaRole"

echo ""
echo "======================================"
echo "Step 1: Upload Source Code to S3"
echo "======================================"

SOURCE_S3_PATH="s3://${BUCKET_NAME}/album-classifier/source"

# Create source code package
cd "$(dirname "$0")"
cd ../sagemaker

# Create temporary directory for source code
TEMP_DIR=$(mktemp -d)
cp -r *.py requirements.txt $TEMP_DIR/ 2>/dev/null || true

# Create tar.gz of source code
cd $TEMP_DIR
tar -czf source.tar.gz *.py requirements.txt 2>/dev/null || tar -czf source.tar.gz *.py

# Upload to S3
aws s3 cp source.tar.gz ${SOURCE_S3_PATH}/source.tar.gz
echo -e "${GREEN}✓${NC} Uploaded source code to ${SOURCE_S3_PATH}/source.tar.gz"

# Clean up
rm -rf $TEMP_DIR

echo ""
echo "======================================"
echo "Step 2: Create Lambda Execution Role"
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
        "sagemaker:StopTrainingJob",
        "sagemaker:CreateModel",
        "sagemaker:CreateEndpoint",
        "sagemaker:CreateEndpointConfig"
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
        "arn:aws:s3:::${BUCKET_NAME}/*",
        "arn:aws:s3:::${BUCKET_NAME}"
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
echo "Step 3: Create Lambda Function"
echo "======================================"

# Create deployment package
cd "$(dirname "$0")"
mkdir -p /tmp/lambda-package
cp lambda_trigger_full_pipeline.py /tmp/lambda-package/lambda_function.py

# Install boto3 and sagemaker in package (they're usually available in Lambda runtime)
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
        --environment "Variables={SAGEMAKER_ROLE=${SAGEMAKER_ROLE},BUCKET_NAME=${BUCKET_NAME},AWS_REGION=${AWS_REGION}}" \
        --timeout 300 \
        --memory-size 512
else
    echo -e "${YELLOW}ℹ${NC} Creating new Lambda function"
    
    aws lambda create-function \
        --function-name $FUNCTION_NAME \
        --runtime python3.11 \
        --role $LAMBDA_ROLE_ARN \
        --handler lambda_function.lambda_handler \
        --zip-file fileb://lambda-package.zip \
        --timeout 300 \
        --memory-size 512 \
        --environment "Variables={SAGEMAKER_ROLE=${SAGEMAKER_ROLE},BUCKET_NAME=${BUCKET_NAME},AWS_REGION=${AWS_REGION}}"
fi

echo -e "${GREEN}✓${NC} Lambda function deployed"

# Clean up
rm -rf /tmp/lambda-package /tmp/lambda-trust-policy.json /tmp/lambda-sagemaker-policy.json

echo ""
echo "======================================"
echo "Step 4: Create EventBridge Schedule (Optional)"
echo "======================================"

read -p "Create EventBridge schedule? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    RULE_NAME="album-classifier-full-pipeline-weekly"
    
    # Create EventBridge rule
    if aws events describe-rule --name $RULE_NAME 2>/dev/null; then
        echo -e "${YELLOW}ℹ${NC} Rule $RULE_NAME already exists"
    else
        aws events put-rule \
            --name $RULE_NAME \
            --description "Trigger full pipeline training weekly" \
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
fi

echo ""
echo "======================================"
echo "Setup Complete!"
echo "======================================"
echo ""
echo "Lambda Function: $FUNCTION_NAME"
echo "Source Code: ${SOURCE_S3_PATH}/source.tar.gz"
echo ""
echo "Test the function:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME --payload '{}' /tmp/output.json"
echo ""
echo "Invoke with custom parameters:"
echo "  aws lambda invoke --function-name $FUNCTION_NAME \\"
echo "    --payload '{\"instance_type\":\"ml.p3.2xlarge\",\"epochs\":20}' \\"
echo "    /tmp/output.json"
echo ""
echo "View logs:"
echo "  aws logs tail /aws/lambda/$FUNCTION_NAME --follow"
echo ""
echo "Monitor training job:"
echo "  aws sagemaker list-training-jobs --name-contains album-classifier-full"
echo ""


