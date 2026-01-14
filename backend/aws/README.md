# AWS Automation Scripts

Scripts for automated training jobs on AWS.

## 📁 Contents

- **`lambda_trigger_training.py`** - Lambda function to trigger SageMaker training
- **`setup_scheduled_training.sh`** - One-command setup for scheduled training
- **`eventbridge_schedule.json`** - EventBridge schedule configuration example

## 🚀 Quick Start

### Setup Scheduled Training

```bash
# One command setup
bash setup_scheduled_training.sh
```

This will:
1. Create Lambda execution role with proper permissions
2. Deploy Lambda function to trigger training jobs
3. Create EventBridge rule for weekly scheduling
4. Configure all necessary permissions

**Default Schedule**: Every Monday at 2:00 AM UTC

### Manual Job Trigger

```bash
# Trigger a training job now
cd ..
python sagemaker/trigger_training_job.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10
```

## 📋 What Gets Created

### IAM Role
- **Name**: `AlbumClassifierLambdaRole`
- **Permissions**:
  - Lambda basic execution
  - SageMaker training job creation
  - S3 read/write access
  - IAM PassRole for SageMaker

### Lambda Function
- **Name**: `trigger-album-classifier-training`
- **Runtime**: Python 3.11
- **Memory**: 256 MB
- **Timeout**: 5 minutes
- **Environment Variables**:
  - `SAGEMAKER_ROLE`
  - `SAGEMAKER_BUCKET`
  - `AWS_REGION`

### EventBridge Rule
- **Name**: `album-classifier-weekly-training`
- **Schedule**: `cron(0 2 ? * MON *)` (Weekly, Monday 2 AM UTC)
- **Target**: Lambda function
- **Input**: Training parameters (instance type, epochs, etc.)

## 🎛️ Customization

### Change Schedule

```bash
# Daily at 3 AM UTC
aws events put-rule \
  --name album-classifier-weekly-training \
  --schedule-expression "cron(0 3 * * ? *)"

# Bi-weekly
aws events put-rule \
  --name album-classifier-weekly-training \
  --schedule-expression "cron(0 2 ? * MON#1,MON#3 *)"

# Monthly (first day)
aws events put-rule \
  --name album-classifier-weekly-training \
  --schedule-expression "cron(0 2 1 * ? *)"
```

### Change Training Parameters

```bash
# Update instance type and epochs
aws events put-targets \
  --rule album-classifier-weekly-training \
  --targets "Id=1,Arn=arn:aws:lambda:REGION:ACCOUNT:function:trigger-album-classifier-training,Input='{\"instance_type\":\"ml.p3.8xlarge\",\"epochs\":20,\"batch_size\":32}'"
```

### Disable/Enable Schedule

```bash
# Disable
aws events disable-rule --name album-classifier-weekly-training

# Enable
aws events enable-rule --name album-classifier-weekly-training
```

## 📊 Monitoring

### View Lambda Logs

```bash
# Real-time
aws logs tail /aws/lambda/trigger-album-classifier-training --follow

# Recent invocations
aws lambda list-invocations \
  --function-name trigger-album-classifier-training
```

### Check Training Jobs

```bash
# List recent jobs
aws sagemaker list-training-jobs \
  --sort-by CreationTime \
  --sort-order Descending \
  --max-results 10

# Describe specific job
aws sagemaker describe-training-job --training-job-name JOB_NAME
```

### Test Lambda Function

```bash
# Manual invocation
aws lambda invoke \
  --function-name trigger-album-classifier-training \
  --payload '{"instance_type":"ml.m5.xlarge","epochs":2}' \
  /tmp/output.json

# View result
cat /tmp/output.json
```

## 💰 Cost Estimates

### Lambda Costs
- Free tier: 1M requests/month, 400K GB-seconds/month
- After free tier: $0.20 per 1M requests
- **Weekly schedule**: ~4 requests/month = **FREE**

### Training Costs
- ml.m5.xlarge: $0.23/hour
- ml.p3.2xlarge: $3.06/hour
- **Weekly training** (10 min avg): ~$2/week = **$8/month**

### Total Monthly Cost
- Lambda: FREE
- EventBridge: FREE
- Training (weekly): ~$8/month
- **Total: ~$8/month**

## 🔧 Troubleshooting

### Lambda Function Not Triggering

```bash
# Check EventBridge rule
aws events describe-rule --name album-classifier-weekly-training

# Check targets
aws events list-targets-by-rule --rule album-classifier-weekly-training

# Check Lambda permissions
aws lambda get-policy --function-name trigger-album-classifier-training
```

### Training Job Fails to Start

```bash
# Check Lambda logs
aws logs tail /aws/lambda/trigger-album-classifier-training

# Check SageMaker role permissions
aws iam get-role --role-name DiscogsSageSageMakerRole

# Verify S3 bucket exists
aws s3 ls s3://${SAGEMAKER_BUCKET}/
```

### Can't Access Lambda Function

```bash
# Verify function exists
aws lambda get-function --function-name trigger-album-classifier-training

# Check IAM role
aws iam get-role --role-name AlbumClassifierLambdaRole

# Redeploy
bash setup_scheduled_training.sh
```

## 🧹 Cleanup

Remove all created resources:

```bash
# Delete EventBridge rule
aws events remove-targets --rule album-classifier-weekly-training --ids 1
aws events delete-rule --name album-classifier-weekly-training

# Delete Lambda function
aws lambda delete-function --function-name trigger-album-classifier-training

# Delete IAM role
aws iam delete-role-policy \
  --role-name AlbumClassifierLambdaRole \
  --policy-name SageMakerAccessPolicy

aws iam detach-role-policy \
  --role-name AlbumClassifierLambdaRole \
  --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole

aws iam delete-role --role-name AlbumClassifierLambdaRole
```

## 📚 Additional Resources

- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)
- [EventBridge Schedules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)
- [SageMaker Training Jobs](https://docs.aws.amazon.com/sagemaker/latest/dg/how-it-works-training.html)
- [Parent Documentation](../AWS_JOBS.md)

