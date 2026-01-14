# Quick Start: Run Full Pipeline Entirely in AWS

This is the fastest way to get your full pipeline running entirely in AWS.

## Prerequisites

1. AWS CLI configured with credentials
2. S3 bucket created
3. SageMaker execution role created
4. Manifest file prepared

## Step 1: Upload Source Code

```bash
cd backend/aws
./upload_source_to_s3.sh
```

This uploads all training scripts to S3 where SageMaker can access them.

## Step 2: Upload Manifest

```bash
aws s3 cp data/releases_manifest_enriched.jsonl \
  s3://your-bucket/album-classifier/data/
```

## Step 3: Setup Lambda Function

```bash
cd backend/aws
./setup_full_pipeline_aws.sh
```

This creates:
- Lambda function to trigger training
- IAM roles and permissions
- Optional EventBridge schedule

## Step 4: Trigger Training

### Option A: Via Lambda (Recommended)

```bash
aws lambda invoke \
  --function-name trigger-full-pipeline-training \
  --payload '{
    "instance_type": "ml.p3.2xlarge",
    "epochs": 10
  }' \
  /tmp/output.json

cat /tmp/output.json
```

### Option B: Via AWS Console

1. Go to Lambda Console
2. Find `trigger-full-pipeline-training`
3. Click "Test"
4. Use test event:
```json
{
  "instance_type": "ml.p3.2xlarge",
  "epochs": 10,
  "batch_size": 16
}
```

### Option C: Via EventBridge (Scheduled)

The setup script creates a weekly schedule. To trigger manually:

```bash
aws events put-events \
  --entries '[{
    "Source": "manual.trigger",
    "DetailType": "Training Job Trigger",
    "Detail": "{\"instance_type\":\"ml.p3.2xlarge\"}"
  }]'
```

## Step 5: Monitor Progress

```bash
# List training jobs
aws sagemaker list-training-jobs \
  --name-contains album-classifier-full \
  --max-results 5

# View logs
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-* --follow
```

## Alternative: Run from EC2 or CloudShell

If you prefer a more interactive approach:

```bash
# On EC2 or CloudShell
git clone https://github.com/your-repo/dsicogs-sage-app.git
cd dsicogs-sage-app/backend/sagemaker

pip3 install -r requirements.txt --user

python3 trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl
```

## Troubleshooting

### Source Code Not Found

Re-upload source code:
```bash
cd backend/aws
./upload_source_to_s3.sh
```

### Permission Errors

Check IAM roles:
```bash
# Verify Lambda role
aws iam get-role --role-name FullPipelineLambdaRole

# Verify SageMaker role
aws iam get-role --role-name YOUR_SAGEMAKER_ROLE_NAME
```

### View Lambda Logs

```bash
aws logs tail /aws/lambda/trigger-full-pipeline-training --follow
```

## Next Steps

- Set up CloudWatch alarms for job failures
- Configure EventBridge for automated scheduling
- Set up API Gateway for external triggers
- See `RUN_IN_AWS.md` for advanced options


