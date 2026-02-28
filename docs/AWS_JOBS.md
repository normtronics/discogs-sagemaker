# Running Training Jobs on AWS

Complete guide for automated and scheduled training jobs on AWS.

## 🎯 Job Options

### 1. Manual Job Trigger (CLI)
Run training jobs on-demand from your terminal.

### 2. Scheduled Jobs (EventBridge)
Automatically train on a schedule (daily, weekly, monthly).

### 3. API-Triggered Jobs (Lambda + API Gateway)
Trigger training via HTTP API calls.

### 4. Event-Driven Jobs (S3 + Lambda)
Auto-train when new data is uploaded to S3.

## 🚀 Quick Setup

### Option 1: One-Command Setup (Recommended)

```bash
# Setup automated weekly training
cd aws
bash setup_scheduled_training.sh
```

This creates:
- Lambda function to trigger training
- EventBridge rule (weekly schedule)
- Required IAM roles and permissions

**Default Schedule**: Every Monday at 2:00 AM UTC

### Option 2: Manual Job Triggering

```bash
# Trigger a training job immediately
python sagemaker/trigger_training_job.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --batch-size 16
```

## 📅 Scheduled Training Setup

### Step 1: Deploy Lambda Function

```bash
cd aws
bash setup_scheduled_training.sh
```

### Step 2: Customize Schedule

```bash
# Daily at 3:00 AM UTC
aws events put-rule \
  --name album-classifier-daily-training \
  --schedule-expression "cron(0 3 * * ? *)" \
  --state ENABLED

# Bi-weekly (every other Monday)
aws events put-rule \
  --name album-classifier-biweekly-training \
  --schedule-expression "cron(0 2 ? * MON#1,MON#3 *)" \
  --state ENABLED

# First day of every month
aws events put-rule \
  --name album-classifier-monthly-training \
  --schedule-expression "cron(0 2 1 * ? *)" \
  --state ENABLED
```

### Step 3: Test the Setup

```bash
# Trigger manually to test
aws lambda invoke \
  --function-name trigger-album-classifier-training \
  --payload '{"instance_type":"ml.m5.xlarge","epochs":2}' \
  /tmp/output.json

# View result
cat /tmp/output.json
```

### Step 4: Monitor Jobs

```bash
# List recent training jobs
aws sagemaker list-training-jobs \
  --sort-by CreationTime \
  --sort-order Descending \
  --max-results 5

# View Lambda logs
aws logs tail /aws/lambda/trigger-album-classifier-training --follow

# View training job logs
aws logs tail /aws/sagemaker/TrainingJobs --follow
```

## 🔧 Configuration

### Schedule Expressions

EventBridge supports cron and rate expressions:

```bash
# Rate-based
rate(1 day)          # Every day
rate(7 days)         # Every week
rate(30 days)        # Every month

# Cron-based (cron(minutes hours day month weekday year))
cron(0 2 * * ? *)    # Daily at 2:00 AM UTC
cron(0 2 ? * MON *)  # Every Monday at 2:00 AM UTC
cron(0 2 1 * ? *)    # First day of every month
cron(0 */6 * * ? *)  # Every 6 hours
```

### Training Parameters

Customize training in the EventBridge target input:

```json
{
  "instance_type": "ml.p3.2xlarge",
  "epochs": 10,
  "batch_size": 16,
  "learning_rate": 0.001
}
```

Or via Lambda environment variables:

```bash
aws lambda update-function-configuration \
  --function-name trigger-album-classifier-training \
  --environment "Variables={
    SAGEMAKER_ROLE=arn:aws:iam::123456789:role/SageMakerRole,
    SAGEMAKER_BUCKET=my-bucket,
    AWS_REGION=us-east-1,
    DEFAULT_INSTANCE_TYPE=ml.p3.2xlarge,
    DEFAULT_EPOCHS=10
  }"
```

## 🌐 API-Triggered Jobs

### Setup API Gateway

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name "Album Classifier Training API" \
  --query 'id' --output text)

# Get root resource
ROOT_ID=$(aws apigateway get-resources \
  --rest-api-id $API_ID \
  --query 'items[0].id' --output text)

# Create resource
RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --parent-id $ROOT_ID \
  --path-part train \
  --query 'id' --output text)

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --authorization-type AWS_IAM

# Integrate with Lambda
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri "arn:aws:apigateway:us-east-1:lambda:path/2015-03-31/functions/arn:aws:lambda:us-east-1:ACCOUNT_ID:function:trigger-album-classifier-training/invocations"

# Deploy API
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod

echo "API Endpoint: https://${API_ID}.execute-api.us-east-1.amazonaws.com/prod/train"
```

### Call API to Trigger Training

```bash
# Using curl
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/train \
  -H "Content-Type: application/json" \
  -d '{
    "instance_type": "ml.p3.2xlarge",
    "epochs": 10,
    "batch_size": 16
  }' \
  --aws-sigv4 "aws:amz:us-east-1:execute-api"

# Using Python
import requests
from aws_requests_auth.aws_auth import AWSRequestsAuth

auth = AWSRequestsAuth(
    aws_access_key='YOUR_KEY',
    aws_secret_access_key='YOUR_SECRET',
    aws_host='YOUR_API_ID.execute-api.us-east-1.amazonaws.com',
    aws_region='us-east-1',
    aws_service='execute-api'
)

response = requests.post(
    'https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/train',
    json={
        'instance_type': 'ml.p3.2xlarge',
        'epochs': 10
    },
    auth=auth
)
print(response.json())
```

## 📦 Event-Driven Jobs (S3 Triggers)

Automatically train when new data is uploaded:

```bash
# Add S3 trigger to Lambda
aws lambda add-permission \
  --function-name trigger-album-classifier-training \
  --statement-id s3-trigger \
  --action lambda:InvokeFunction \
  --principal s3.amazonaws.com \
  --source-arn arn:aws:s3:::${SAGEMAKER_BUCKET}

# Configure S3 bucket notification
aws s3api put-bucket-notification-configuration \
  --bucket ${SAGEMAKER_BUCKET} \
  --notification-configuration '{
    "LambdaFunctionConfigurations": [
      {
        "LambdaFunctionArn": "arn:aws:lambda:us-east-1:ACCOUNT_ID:function:trigger-album-classifier-training",
        "Events": ["s3:ObjectCreated:*"],
        "Filter": {
          "Key": {
            "FilterRules": [
              {"Name": "prefix", "Value": "album-classifier/data/"},
              {"Name": "suffix", "Value": ".jsonl"}
            ]
          }
        }
      }
    ]
  }'
```

Now training auto-triggers when you upload `releases_manifest.jsonl` to S3!

## 📊 Monitoring & Notifications

### CloudWatch Alarms

```bash
# Alert when training job fails
aws cloudwatch put-metric-alarm \
  --alarm-name album-classifier-training-failures \
  --alarm-description "Alert on training job failures" \
  --namespace AWS/SageMaker \
  --metric-name TrainingJobsFailed \
  --statistic Sum \
  --period 3600 \
  --evaluation-periods 1 \
  --threshold 1 \
  --comparison-operator GreaterThanOrEqualToThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:training-alerts

# Alert on high costs
aws cloudwatch put-metric-alarm \
  --alarm-name album-classifier-high-costs \
  --alarm-description "Alert on estimated charges > $10" \
  --namespace AWS/Billing \
  --metric-name EstimatedCharges \
  --statistic Maximum \
  --period 21600 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --alarm-actions arn:aws:sns:us-east-1:ACCOUNT_ID:billing-alerts
```

### SNS Notifications

```bash
# Create SNS topic
TOPIC_ARN=$(aws sns create-topic \
  --name album-classifier-notifications \
  --query 'TopicArn' --output text)

# Subscribe email
aws sns subscribe \
  --topic-arn $TOPIC_ARN \
  --protocol email \
  --notification-endpoint your-email@example.com

# Confirm subscription via email

# Update Lambda to send notifications
aws lambda update-function-configuration \
  --function-name trigger-album-classifier-training \
  --environment "Variables={
    SAGEMAKER_ROLE=${SAGEMAKER_ROLE},
    SAGEMAKER_BUCKET=${SAGEMAKER_BUCKET},
    AWS_REGION=${AWS_REGION},
    SNS_TOPIC_ARN=${TOPIC_ARN}
  }"
```

## 💰 Cost Optimization

### Use Spot Instances

Training jobs automatically use spot instances (up to 70% savings):

```python
# Already configured in trigger_training_job.py
use_spot_instances=True
max_wait=86400  # Wait time for spot
```

### Schedule During Off-Peak

Train during off-peak hours to reduce contention:

```bash
# Schedule for 2 AM UTC (9 PM EST)
aws events put-rule \
  --schedule-expression "cron(0 2 * * ? *)"
```

### Auto-Stop Failed Jobs

Set maximum runtime to avoid runaway costs:

```python
StoppingCondition={
    'MaxRuntimeInSeconds': 86400  # 24 hours max
}
```

### Budget Alerts

```bash
# Set monthly budget
aws budgets create-budget \
  --account-id $(aws sts get-caller-identity --query Account --output text) \
  --budget file://budget-config.json

# budget-config.json
{
  "BudgetName": "SageMaker-Monthly",
  "BudgetLimit": {
    "Amount": "100",
    "Unit": "USD"
  },
  "TimeUnit": "MONTHLY",
  "BudgetType": "COST"
}
```

## 🔍 Troubleshooting

### Check Lambda Function

```bash
# Test Lambda directly
aws lambda invoke \
  --function-name trigger-album-classifier-training \
  --payload '{"instance_type":"ml.m5.xlarge","epochs":2}' \
  /tmp/response.json

cat /tmp/response.json
```

### View Lambda Logs

```bash
# Real-time logs
aws logs tail /aws/lambda/trigger-album-classifier-training --follow

# Recent errors
aws logs filter-log-events \
  --log-group-name /aws/lambda/trigger-album-classifier-training \
  --filter-pattern "ERROR"
```

### Check EventBridge Rule

```bash
# List rules
aws events list-rules

# Describe specific rule
aws events describe-rule --name album-classifier-weekly-training

# Check targets
aws events list-targets-by-rule --rule album-classifier-weekly-training
```

### Check Training Job Status

```bash
# List jobs
aws sagemaker list-training-jobs --max-results 5

# Describe specific job
aws sagemaker describe-training-job --training-job-name JOB_NAME

# View logs
aws logs tail /aws/sagemaker/TrainingJobs/JOB_NAME --follow
```

## 🛠️ Management Commands

```bash
# Disable scheduled training
aws events disable-rule --name album-classifier-weekly-training

# Enable scheduled training
aws events enable-rule --name album-classifier-weekly-training

# Update schedule
aws events put-rule \
  --name album-classifier-weekly-training \
  --schedule-expression "cron(0 3 * * ? *)"

# Delete schedule
aws events remove-targets --rule album-classifier-weekly-training --ids 1
aws events delete-rule --name album-classifier-weekly-training

# Delete Lambda function
aws lambda delete-function --function-name trigger-album-classifier-training

# Update training parameters
aws events put-targets \
  --rule album-classifier-weekly-training \
  --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:trigger-album-classifier-training,Input='{\"instance_type\":\"ml.p3.8xlarge\",\"epochs\":20}'"
```

## 📈 Usage Examples

### Weekly Production Training

```bash
# Setup
bash aws/setup_scheduled_training.sh

# Customize for production
aws events put-rule \
  --name album-classifier-production \
  --schedule-expression "cron(0 2 ? * MON *)" \
  --state ENABLED

aws events put-targets \
  --rule album-classifier-production \
  --targets "Id=1,Arn=arn:aws:lambda:us-east-1:ACCOUNT:function:trigger-album-classifier-training,Input='{\"instance_type\":\"ml.p3.2xlarge\",\"epochs\":15,\"batch_size\":32}'"
```

### On-Demand Experimentation

```bash
# Quick test (2 epochs, small instance)
python sagemaker/trigger_training_job.py \
  --instance-type ml.m5.large \
  --epochs 2 \
  --batch-size 4

# Full experiment (20 epochs, large instance)
python sagemaker/trigger_training_job.py \
  --instance-type ml.p3.8xlarge \
  --epochs 20 \
  --batch-size 64 \
  --wait
```

### CI/CD Pipeline Integration

```yaml
# .github/workflows/train.yml
name: Train Model
on:
  schedule:
    - cron: '0 2 * * 1'  # Weekly
  workflow_dispatch:

jobs:
  train:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Configure AWS
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-east-1
      
      - name: Trigger Training
        run: |
          aws lambda invoke \
            --function-name trigger-album-classifier-training \
            --payload '{"epochs":10}' \
            /tmp/output.json
```

## 🎓 Best Practices

1. **Test locally first** - Use `local_train.py` before scheduling
2. **Start with small schedules** - Weekly before daily
3. **Monitor costs** - Set up billing alerts
4. **Use spot instances** - Save up to 70%
5. **Set max runtime** - Prevent runaway jobs
6. **Enable notifications** - Know when jobs complete/fail
7. **Version your data** - Track what each model was trained on
8. **Keep checkpoints** - Resume failed trainings
9. **Test Lambda manually** - Before enabling schedule
10. **Review logs regularly** - Catch issues early

## 📚 Related Documentation

- [AWS_SETUP.md](AWS_SETUP.md) - Initial AWS setup
- [AWS_WORKFLOW.md](AWS_WORKFLOW.md) - Daily workflows
- [sagemaker/README.md](sagemaker/README.md) - Technical details

