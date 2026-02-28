# SageMaker Quick Start Guide

Get your album classifier running on Amazon SageMaker in minutes.

## Prerequisites

- AWS Account with SageMaker access
- Python 3.9+
- Album images downloaded (see main README)

## Step 1: Configure Environment

Create `backend/.env.local`:

```bash
# AWS Configuration
AWS_REGION=us-east-1

# SageMaker Configuration  
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT_ID:role/SageMakerExecutionRole
SAGEMAKER_BUCKET=your-sagemaker-bucket

# Discogs API (if needed)
DISCOGS_CONSUMER_KEY=your_key
DISCOGS_CONSUMER_SECRET=your_secret
```

## Step 2: Install Dependencies

```bash
pip install -r sagemaker/requirements.txt
```

## Step 3: Test Locally (Recommended)

```bash
# Train model locally
python sagemaker/local_train.py --epochs 5

# Test predictions
python sagemaker/local_predict.py --image backend/data/images/0.jpg
```

Expected output:
```
✓ Model loaded with 50 classes
✓ Image loaded: (500, 500)

Prediction Results
==================================================
1. Album Title
   Artists: Artist Name
   Confidence: 85.23%
```

## Step 4: Deploy to SageMaker

### Option A: Local SageMaker Mode (No AWS charges)

```bash
python sagemaker/deploy.py --local-mode --epochs 5
```

### Option B: Cloud Deployment

```bash
# Upload data to S3
aws s3 sync backend/data/ s3://your-bucket/album-classifier/data/

# Deploy
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --endpoint-name album-classifier
```

## Step 5: Test Endpoint

```bash
python sagemaker/test_endpoint.py \
  --endpoint album-classifier \
  --image backend/data/images/0.jpg
```

## Common Commands

```bash
# Train only (no deployment)
python sagemaker/deploy.py --skip-deploy

# Deploy existing model
python sagemaker/deploy.py --skip-training

# Custom training parameters
python sagemaker/local_train.py \
  --epochs 15 \
  --batch-size 16 \
  --learning-rate 0.0005
```

## Cost Estimates

- **Training**: ~$0.50-5.00 per run (depends on instance type and duration)
- **Endpoint**: ~$0.05-0.23 per hour (depends on instance type)
- **Storage**: ~$0.023 per GB/month in S3

**Tip**: Delete endpoints when not in use to save costs!

```bash
aws sagemaker delete-endpoint --endpoint-name album-classifier
```

## Troubleshooting

### Model not found
```bash
# Train the model first
python sagemaker/local_train.py
```

### AWS credentials error
```bash
# Configure AWS CLI
aws configure
```

### Out of memory
```bash
# Reduce batch size
python sagemaker/local_train.py --batch-size 4
```

## Next Steps

- See `sagemaker/README.md` for detailed documentation
- Optimize hyperparameters in `sagemaker/config.json`
- Set up auto-scaling for production use
- Enable model monitoring with CloudWatch

## Support

For issues or questions:
1. Check `sagemaker/README.md`
2. Review AWS SageMaker documentation
3. Check CloudWatch logs for errors

