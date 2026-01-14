# Full Pipeline SageMaker Training Job

This document describes how to use the full pipeline training job that combines image downloading, S3 upload, model training, and deployment into a single SageMaker job.

## Overview

The full pipeline script (`full_pipeline_train.py`) performs the following steps:

1. **Download Images**: Downloads album cover images from URLs in the manifest file
2. **Upload to S3**: Uploads downloaded images to S3 for future use
3. **Train Model**: Trains the album classification model using the downloaded images
4. **Deploy Model** (optional): Deploys the trained model to a SageMaker endpoint

## Prerequisites

1. **AWS Credentials**: Configure AWS credentials with SageMaker permissions
2. **S3 Bucket**: Create an S3 bucket for storing data and models
3. **SageMaker Role**: Create an IAM role with SageMaker execution permissions
4. **Manifest File**: Prepare a manifest file with release data and image URLs

## Setup

1. **Install Dependencies**:
   ```bash
   cd backend/sagemaker
   pip install -r requirements.txt
   ```

2. **Configure Environment**:
   Create or update `backend/.env.local`:
   ```bash
   AWS_REGION=us-east-1
   BUCKET_NAME=your-sagemaker-bucket
   SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole
   ```

3. **Prepare Manifest File**:
   Ensure your manifest file (`releases_manifest_enriched.jsonl`) contains image URLs:
   ```json
   {"release_id": 123, "title": "Album", "cover_image": "https://...", ...}
   ```

   Upload the manifest to S3:
   ```bash
   aws s3 cp data/releases_manifest_enriched.jsonl s3://your-bucket/album-classifier/data/
   ```

## Usage

### Basic Usage

Run the full pipeline with default settings:

```bash
cd backend/sagemaker
python trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl
```

### Advanced Usage

Customize the pipeline with various options:

```bash
python trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl \
  --instance-type ml.p3.2xlarge \
  --epochs 20 \
  --batch-size 32 \
  --learning-rate 0.0001 \
  --max-concurrent-downloads 20 \
  --endpoint-instance-type ml.m5.xlarge
```

### Skip Steps

You can skip individual steps if needed:

```bash
# Skip download (assume images already exist)
python trigger_full_pipeline.py --skip-download

# Skip upload (don't upload to S3)
python trigger_full_pipeline.py --skip-upload

# Skip training (only download/upload)
python trigger_full_pipeline.py --skip-training

# Skip deployment (only train)
python trigger_full_pipeline.py --skip-deploy
```

### Monitor Progress

Monitor the training job:

```bash
# Get job status
aws sagemaker describe-training-job --training-job-name album-classifier-full-YYYYMMDD-HHMMSS

# View logs
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-YYYYMMDD-HHMMSS --follow
```

## Configuration Options

### Instance Types

- **Training**: `ml.p3.2xlarge` (GPU), `ml.m5.xlarge` (CPU), `ml.g4dn.xlarge` (GPU)
- **Endpoint**: `ml.m5.large` (CPU), `ml.g4dn.xlarge` (GPU)

### Hyperparameters

- `epochs`: Number of training epochs (default: 10)
- `batch-size`: Training batch size (default: 16)
- `learning-rate`: Learning rate (default: 0.001)
- `max-concurrent-downloads`: Concurrent image downloads (default: 10)

### S3 Structure

The pipeline expects the following S3 structure:

```
s3://your-bucket/
  album-classifier/
    data/
      releases_manifest_enriched.jsonl  # Manifest file
      images/                            # Downloaded images (created by pipeline)
    models/                              # Trained models (created by pipeline)
    code/                                # Training code (uploaded automatically)
    checkpoints/                         # Training checkpoints (created by pipeline)
```

## Workflow

1. **Trigger Job**: Run `trigger_full_pipeline.py`
2. **SageMaker Starts**: Job starts on specified instance type
3. **Download Images**: Script downloads images from URLs in manifest
4. **Upload to S3**: Images are uploaded to S3 for future use
5. **Train Model**: Model is trained using downloaded images
6. **Save Model**: Trained model is saved to S3
7. **Deploy** (optional): Model is deployed to SageMaker endpoint

## Cost Considerations

- **Spot Instances**: The pipeline uses spot instances by default for cost savings
- **Volume Size**: Default volume size is 100GB (adjust if needed)
- **Max Runtime**: Default max runtime is 48 hours (for large downloads)
- **Instance Selection**: Choose appropriate instance type based on your needs:
  - GPU instances (`ml.p3.*`) are faster but more expensive
  - CPU instances (`ml.m5.*`) are cheaper but slower

## Troubleshooting

### Common Issues

1. **Manifest Not Found**:
   - Ensure manifest is uploaded to S3
   - Check the `--manifest-path` argument

2. **Image Download Failures**:
   - Check network connectivity
   - Verify image URLs in manifest
   - Reduce `--max-concurrent-downloads` if rate-limited

3. **S3 Upload Failures**:
   - Verify bucket permissions
   - Check bucket exists and is accessible
   - Ensure SageMaker role has S3 write permissions

4. **Training Failures**:
   - Check instance type has sufficient memory
   - Verify images are downloaded successfully
   - Check CloudWatch logs for detailed errors

5. **Deployment Failures**:
   - Deployment may fail due to permissions or timeouts
   - Model artifacts are still saved and can be deployed separately
   - Use `deploy.py` script for manual deployment

### Manual Deployment

If deployment fails during training, deploy manually:

```bash
python deploy.py \
  --skip-training \
  --model-path s3://your-bucket/album-classifier/models/job-name/output/model.tar.gz
```

## Example: Complete Workflow

```bash
# 1. Prepare manifest (if not already done)
cd backend
python enrich_manifest_with_images.py \
  --input ../data/releases_manifest.jsonl \
  --output ../data/releases_manifest_enriched.jsonl

# 2. Upload manifest to S3
aws s3 cp ../data/releases_manifest_enriched.jsonl \
  s3://your-bucket/album-classifier/data/

# 3. Run full pipeline
cd sagemaker
python trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl \
  --instance-type ml.p3.2xlarge \
  --epochs 15 \
  --batch-size 16

# 4. Monitor progress
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-* --follow

# 5. Test endpoint (after deployment)
python test_endpoint.py \
  --endpoint album-classifier-YYYYMMDD-HHMMSS \
  --image path/to/test/image.jpg
```

## Next Steps

After the pipeline completes:

1. **Test the Endpoint**: Use `test_endpoint.py` to test predictions
2. **Monitor Performance**: Check CloudWatch metrics
3. **Update Frontend**: Update frontend to use new endpoint
4. **Schedule Retraining**: Set up EventBridge schedule for periodic retraining

## See Also

- `train.py`: Standalone training script
- `deploy.py`: Standalone deployment script
- `trigger_training_job.py`: Simple training job trigger
- `README.md`: General SageMaker documentation


