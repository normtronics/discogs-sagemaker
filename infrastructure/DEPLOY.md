# Quick Deploy Guide

## Prerequisites

```bash
# Install CDK CLI globally
npm install -g aws-cdk

# Verify installation
cdk --version
```

## First Time Setup

```bash
cd infrastructure

# Install dependencies
npm install

# Bootstrap CDK (only needed once per account/region)
cdk bootstrap
```

## Deploy

### Option 1: Using Environment Variables

```bash
export BUCKET_NAME=your-sagemaker-bucket
export SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
export AWS_REGION=us-east-1

cdk deploy
```

### Option 2: Using CDK Context

```bash
cdk deploy \
  --context bucketName=your-sagemaker-bucket \
  --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

### Option 3: Edit cdk.json

Add to `cdk.json`:

```json
{
  "context": {
    "bucketName": "your-sagemaker-bucket",
    "sagemakerRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole"
  }
}
```

Then:

```bash
cdk deploy
```

## Enable Scheduled Training

```bash
cdk deploy \
  --context bucketName=your-bucket \
  --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole \
  --context enableSchedule=true
```

## After Deployment

1. **Upload source code to S3**:
   ```bash
   cd ../backend/aws
   ./upload_source_to_s3.sh
   ```

2. **Upload manifest**:
   ```bash
   aws s3 cp ../data/releases_manifest_enriched.jsonl \
     s3://your-bucket/album-classifier/data/
   ```

3. **Invoke Lambda**:
   ```bash
   # Get function name from stack outputs
   FUNCTION_NAME=$(aws cloudformation describe-stacks \
     --stack-name FullPipelineStack \
     --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
     --output text)

   # Invoke
   aws lambda invoke \
     --function-name $FUNCTION_NAME \
     --payload '{"instance_type": "ml.p3.2xlarge", "epochs": 10}' \
     /tmp/output.json

   cat /tmp/output.json
   ```

## View Outputs

```bash
aws cloudformation describe-stacks \
  --stack-name FullPipelineStack \
  --query 'Stacks[0].Outputs'
```

## Destroy

```bash
cdk destroy
```


