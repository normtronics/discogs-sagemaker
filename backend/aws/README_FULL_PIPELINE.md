# Full Pipeline AWS Deployment Guide

This guide explains how to deploy and run the full pipeline training job entirely within AWS.

## Overview

The full pipeline combines:
1. **Image Download**: Downloads images from URLs in manifest
2. **S3 Upload**: Uploads images to S3
3. **Model Training**: Trains the classification model
4. **Model Deployment**: Deploys to SageMaker endpoint (optional)

All of this runs entirely in AWS without requiring your local machine.

## Quick Start

### 1. Upload Source Code

```bash
cd backend/aws
./upload_source_to_s3.sh
```

### 2. Upload Manifest

```bash
aws s3 cp data/releases_manifest_enriched.jsonl \
  s3://your-bucket/album-classifier/data/
```

### 3. Setup Lambda Function

```bash
cd backend/aws
./setup_full_pipeline_aws.sh
```

### 4. Trigger Training

```bash
aws lambda invoke \
  --function-name trigger-full-pipeline-training \
  --payload '{"instance_type": "ml.p3.2xlarge", "epochs": 10}' \
  /tmp/output.json
```

## Architecture

```
┌─────────────────┐
│  EventBridge    │  (Scheduled triggers)
│  or API Gateway │  (On-demand triggers)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Lambda Function│  (Triggers SageMaker job)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SageMaker       │  (Runs full pipeline)
│ Training Job    │  - Downloads images
└────────┬────────┘  - Uploads to S3
         │           - Trains model
         │           - Deploys endpoint
         ▼
┌─────────────────┐
│  S3 Bucket      │  (Stores data & models)
└─────────────────┘
```

## Files

- `lambda_trigger_full_pipeline.py`: Lambda function code
- `setup_full_pipeline_aws.sh`: Setup script for AWS infrastructure
- `upload_source_to_s3.sh`: Script to upload source code to S3

## Detailed Documentation

- **Quick Start**: See `../sagemaker/AWS_QUICKSTART.md`
- **Full Guide**: See `../sagemaker/RUN_IN_AWS.md`
- **Pipeline Details**: See `../sagemaker/FULL_PIPELINE_README.md`

## Prerequisites

1. AWS CLI configured
2. S3 bucket created
3. SageMaker execution role created
4. Manifest file with image URLs prepared

## Environment Variables

Set in `backend/.env.local`:

```bash
AWS_REGION=us-east-1
BUCKET_NAME=your-sagemaker-bucket
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

## Monitoring

### View Training Jobs

```bash
aws sagemaker list-training-jobs \
  --name-contains album-classifier-full \
  --max-results 10
```

### View Logs

```bash
# Training job logs
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-* --follow

# Lambda logs
aws logs tail /aws/lambda/trigger-full-pipeline-training --follow
```

### CloudWatch Metrics

View in AWS Console:
- Training job duration
- GPU/CPU utilization
- Model accuracy
- Cost metrics

## Cost Optimization

1. **Spot Instances**: Enabled by default (50-70% savings)
2. **Right-size Instances**: Use `ml.m5.xlarge` for testing
3. **Schedule Off-Peak**: Run during off-peak hours
4. **Auto-stop Endpoints**: Delete when not in use

## Troubleshooting

### Source Code Not Found

```bash
# Re-upload source code
cd backend/aws
./upload_source_to_s3.sh
```

### Permission Errors

```bash
# Check Lambda role
aws iam get-role --role-name FullPipelineLambdaRole

# Check SageMaker role
aws iam get-role --role-name YOUR_SAGEMAKER_ROLE_NAME
```

### Lambda Timeout

Increase timeout:
```bash
aws lambda update-function-configuration \
  --function-name trigger-full-pipeline-training \
  --timeout 900  # Max 15 minutes
```

## Next Steps

- Set up CloudWatch alarms
- Configure EventBridge schedules
- Set up API Gateway for external triggers
- Implement model versioning
- Set up cost monitoring


