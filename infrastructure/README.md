# CDK Infrastructure for Full Pipeline

This directory contains AWS CDK code to deploy the full pipeline infrastructure for SageMaker training.

## What Gets Deployed

- **Lambda Function**: Triggers SageMaker training jobs
- **IAM Roles**: Permissions for Lambda to invoke SageMaker
- **EventBridge Rule**: Optional scheduled training (disabled by default)
- **S3 Bucket Reference**: Uses existing bucket for data/models

## Prerequisites

1. **AWS CDK CLI**:
   ```bash
   npm install -g aws-cdk
   ```

2. **Node.js** (v18+):
   ```bash
   node --version
   ```

3. **AWS Credentials**: Configured via `aws configure` or environment variables

4. **Existing Resources**:
   - S3 bucket for data/models
   - SageMaker execution role

## Setup

### 1. Install Dependencies

```bash
cd infrastructure
npm install
```

### 2. Bootstrap CDK (First Time Only)

```bash
cdk bootstrap
```

### 3. Configure Environment

Set environment variables or use CDK context:

```bash
# Option 1: Environment variables
export BUCKET_NAME=your-sagemaker-bucket
export SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
export AWS_REGION=us-east-1

# Option 2: CDK context (recommended)
# Edit cdk.json or pass via command line
```

### 4. Synthesize CloudFormation Template

```bash
cdk synth --context bucketName=your-bucket --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

### 5. Review Changes

```bash
cdk diff --context bucketName=your-bucket --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

### 6. Deploy

```bash
cdk deploy --context bucketName=your-bucket --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

## Configuration Options

### Via CDK Context

Create or edit `cdk.json`:

```json
{
  "context": {
    "bucketName": "your-sagemaker-bucket",
    "sagemakerRoleArn": "arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole"
  }
}
```

### Via Command Line

```bash
cdk deploy \
  --context bucketName=your-bucket \
  --context sagemakerRoleArn=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

### Via Environment Variables

```bash
export BUCKET_NAME=your-bucket
export SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
cdk deploy
```

## Enable Scheduled Training

By default, the EventBridge rule is disabled. To enable:

### Option 1: Via CDK Context

```json
{
  "context": {
    "enableSchedule": true
  }
}
```

Then update the stack:

```typescript
// In lib/full-pipeline-stack.ts, change:
enabled: app.node.tryGetContext('enableSchedule') || false,
```

### Option 2: Via AWS Console

1. Go to EventBridge → Rules
2. Find `FullPipelineStack-WeeklyTrainingSchedule-XXXXX`
3. Click "Enable"

### Option 3: Via AWS CLI

```bash
aws events enable-rule --name FullPipelineStack-WeeklyTrainingSchedule-XXXXX
```

## Usage

### Invoke Lambda Function

```bash
# Get function name from outputs
FUNCTION_NAME=$(aws cloudformation describe-stacks \
  --stack-name FullPipelineStack \
  --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
  --output text)

# Invoke with default parameters
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload '{}' \
  /tmp/output.json

# Invoke with custom parameters
aws lambda invoke \
  --function-name $FUNCTION_NAME \
  --payload '{
    "instance_type": "ml.p3.2xlarge",
    "epochs": 20,
    "batch_size": 32,
    "learning_rate": 0.0001
  }' \
  /tmp/output.json

cat /tmp/output.json
```

### View Logs

```bash
aws logs tail /aws/lambda/$FUNCTION_NAME --follow
```

## Updating the Stack

After making changes to the CDK code:

```bash
# Review changes
cdk diff

# Deploy updates
cdk deploy
```

## Destroying the Stack

```bash
cdk destroy
```

**Note**: This will delete the Lambda function and EventBridge rule, but NOT:
- S3 bucket or its contents
- SageMaker training jobs or models
- SageMaker endpoints

## Project Structure

```
infrastructure/
├── bin/
│   └── app.ts              # CDK app entry point
├── lib/
│   └── full-pipeline-stack.ts  # Main stack definition
├── cdk.json                # CDK configuration
├── tsconfig.json           # TypeScript configuration
├── package.json            # Node.js dependencies
└── README.md               # This file
```

## Customization

### Change Lambda Timeout

Edit `lib/full-pipeline-stack.ts`:

```typescript
timeout: cdk.Duration.minutes(15), // Change to desired duration
```

### Change Memory Size

```typescript
memorySize: 512, // Change to desired MB
```

### Change Schedule

```typescript
schedule: events.Schedule.cron({
  minute: '0',
  hour: '2',
  day: '?',
  month: '*',
  weekDay: 'MON',
}),
```

### Add API Gateway

```typescript
import * as apigateway from 'aws-cdk-lib/aws-apigateway';

const api = new apigateway.RestApi(this, 'TrainingApi');
const resource = api.root.addResource('trigger');
resource.addMethod('POST', new apigateway.LambdaIntegration(this.lambdaFunction));
```

## Troubleshooting

### CDK Bootstrap Error

```bash
# Bootstrap CDK in your account/region
cdk bootstrap aws://ACCOUNT-ID/REGION
```

### Permission Errors

Ensure your AWS credentials have:
- CloudFormation permissions
- IAM permissions (to create roles)
- Lambda permissions
- EventBridge permissions

### Lambda Function Not Found

Ensure source code is in `backend/aws/lambda_trigger_full_pipeline.py`:
```bash
ls -la backend/aws/lambda_trigger_full_pipeline.py
```

### Build Errors

```bash
# Clean and rebuild
rm -rf node_modules cdk.out
npm install
npm run build
```

## Cost Considerations

- **Lambda**: Pay per invocation (~$0.20 per million requests)
- **EventBridge**: Free for custom events
- **CloudFormation**: Free
- **SageMaker**: Charged separately based on training job instance types

## Next Steps

1. Upload source code to S3 (see `backend/aws/upload_source_to_s3.sh`)
2. Upload manifest file to S3
3. Invoke Lambda function to trigger training
4. Monitor training jobs in SageMaker console

## Running from SageMaker Studio

The CDK infrastructure works seamlessly with SageMaker Studio. You can run training jobs directly from notebooks:

1. **Open SageMaker Studio** and create a new notebook
2. **Use the provided notebook**: See `sagemaker-notebook-example.ipynb`
3. **Or run directly**: See `SAGEMAKER_INTEGRATION.md` for detailed guide

The Lambda function deployed by CDK can also be invoked from SageMaker notebooks, but running directly is recommended for interactive development.

## See Also

- [SageMaker Integration Guide](SAGEMAKER_INTEGRATION.md) - How to run from SageMaker Studio
- [AWS CDK Documentation](https://docs.aws.amazon.com/cdk/)
- [Full Pipeline README](../backend/sagemaker/FULL_PIPELINE_README.md)
- [Run in AWS Guide](../backend/sagemaker/RUN_IN_AWS.md)

