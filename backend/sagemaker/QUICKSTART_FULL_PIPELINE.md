# Quick Start: Full Pipeline SageMaker Job

This guide shows you how to quickly deploy a SageMaker job that downloads images, uploads them to S3, trains a model, and deploys it.

## Prerequisites

1. AWS credentials configured
2. S3 bucket created
3. SageMaker execution role created
4. Manifest file with image URLs prepared

## Quick Start

### 1. Configure Environment

Edit `backend/.env.local`:

```bash
AWS_REGION=us-east-1
BUCKET_NAME=your-sagemaker-bucket
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
```

### 2. Upload Manifest to S3

```bash
aws s3 cp data/releases_manifest_enriched.jsonl \
  s3://your-bucket/album-classifier/data/
```

### 3. Run Full Pipeline

```bash
cd backend/sagemaker
python trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl
```

That's it! The job will:
- Download images from URLs in the manifest
- Upload images to S3
- Train the model
- Deploy to a SageMaker endpoint

## Monitor Progress

```bash
# View logs (replace with your job name)
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-* --follow
```

## Customize

```bash
python trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl \
  --instance-type ml.p3.2xlarge \
  --epochs 20 \
  --batch-size 32 \
  --max-concurrent-downloads 20
```

## Skip Steps

```bash
# Only download and upload (skip training)
python trigger_full_pipeline.py --skip-training

# Only train (skip download/upload)
python trigger_full_pipeline.py --skip-download --skip-upload

# Train but don't deploy
python trigger_full_pipeline.py --skip-deploy
```

## See Full Documentation

See `FULL_PIPELINE_README.md` for complete documentation.


