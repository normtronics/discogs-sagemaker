# SageMaker Setup for Album Classification

This directory contains all the necessary files to train and deploy the album classification model using Amazon SageMaker.

## 📁 Structure

```
sagemaker/
├── train.py              # SageMaker training script
├── inference.py          # SageMaker inference handler
├── local_train.py        # Local training simulator
├── local_predict.py      # Local inference tester
├── deploy.py            # Deployment automation script
├── test_endpoint.py     # Endpoint testing script
├── requirements.txt     # Python dependencies
├── Dockerfile          # Custom container (optional)
├── config.json         # SageMaker configuration
└── .env.example        # Environment variables template
```

## 🚀 Quick Start

### 1. Setup Environment

Copy the environment template and configure your AWS settings:

```bash
cp sagemaker/.env.example backend/.env.local
```

Edit `backend/.env.local` and set:
- `SAGEMAKER_ROLE`: Your SageMaker execution role ARN
- `SAGEMAKER_BUCKET`: S3 bucket for storing data/models
- `AWS_REGION`: AWS region (default: us-east-1)

### 2. Local Testing (Recommended First)

Test the training pipeline locally before deploying to SageMaker:

```bash
# Install dependencies
pip install -r sagemaker/requirements.txt

# Train model locally
python sagemaker/local_train.py --epochs 5

# Test inference locally
python sagemaker/local_predict.py --image backend/data/images/0.jpg
```

### 3. Deploy to SageMaker

#### Option A: Local Mode (No AWS charges)

Test SageMaker locally without AWS:

```bash
python sagemaker/deploy.py --local-mode --epochs 5
```

#### Option B: Full SageMaker Deployment

Deploy to actual SageMaker infrastructure:

```bash
# Train and deploy
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --endpoint-name album-classifier

# Or just train (skip deployment)
python sagemaker/deploy.py --skip-deploy

# Or deploy pre-trained model
python sagemaker/deploy.py --skip-training
```

### 4. Test Endpoint

Once deployed, test the endpoint:

```bash
python sagemaker/test_endpoint.py \
  --endpoint album-classifier \
  --image backend/data/images/0.jpg
```

## 📝 Detailed Usage

### Training Script (`train.py`)

The main training script compatible with SageMaker's PyTorch container.

**Environment Variables:**
- `SM_CHANNEL_TRAINING`: Path to training data
- `SM_MODEL_DIR`: Path to save model
- `SM_OUTPUT_DATA_DIR`: Path for training outputs

**Command Line Arguments:**
```bash
python train.py \
  --epochs 10 \
  --batch-size 16 \
  --learning-rate 0.001 \
  --lr-step-size 5 \
  --lr-gamma 0.1 \
  --test-size 0.2
```

### Inference Handler (`inference.py`)

Implements SageMaker's inference functions:
- `model_fn()`: Load model
- `input_fn()`: Process input data
- `predict_fn()`: Make predictions
- `output_fn()`: Format output

Supports content types:
- `image/jpeg`
- `image/png`
- `application/json` (with base64 encoded images)

### Local Training (`local_train.py`)

Simulates SageMaker environment locally:

```bash
# Basic training
python sagemaker/local_train.py

# Custom parameters
python sagemaker/local_train.py \
  --epochs 15 \
  --batch-size 8 \
  --learning-rate 0.0005
```

### Local Inference (`local_predict.py`)

Test inference without deploying:

```bash
python sagemaker/local_predict.py \
  --image path/to/test.jpg \
  --model-dir sagemaker/models \
  --top-k 5
```

### Deployment Script (`deploy.py`)

Automates training and deployment:

```bash
# Full pipeline
python sagemaker/deploy.py

# Custom configuration
python sagemaker/deploy.py \
  --instance-type ml.p3.8xlarge \
  --epochs 20 \
  --batch-size 32 \
  --endpoint-name my-classifier \
  --endpoint-instance-type ml.m5.xlarge

# Skip deployment
python sagemaker/deploy.py --skip-deploy

# Skip training
python sagemaker/deploy.py --skip-training
```

## 🔧 Configuration

### config.json

Central configuration for SageMaker:

```json
{
  "training": {
    "instance_type": "ml.p3.2xlarge",
    "hyperparameters": {
      "epochs": 10,
      "batch_size": 16
    }
  },
  "deployment": {
    "instance_type": "ml.m5.large",
    "endpoint_name": "album-classifier"
  }
}
```

### Custom Docker Container

Build and push custom container:

```bash
# Build
docker build -t album-classifier:latest -f sagemaker/Dockerfile .

# Tag for ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com
docker tag album-classifier:latest YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/album-classifier:latest

# Push
docker push YOUR_ACCOUNT.dkr.ecr.us-east-1.amazonaws.com/album-classifier:latest
```

## 📊 Data Preparation

### Upload Data to S3

```bash
# Upload training data
aws s3 sync backend/data/ s3://your-bucket/album-classifier/data/

# Verify
aws s3 ls s3://your-bucket/album-classifier/data/
```

### Data Format

Expected directory structure:
```
data/
├── releases_manifest_50.jsonl  # or releases_manifest.jsonl
└── images/
    ├── 0.jpg
    ├── 1.jpg
    └── ...
```

## 🧪 Testing

### Unit Tests

```bash
# Test training locally
python sagemaker/local_train.py --epochs 2

# Test inference
python sagemaker/local_predict.py --image backend/data/images/0.jpg
```

### Integration Tests

```bash
# Test full pipeline in local mode
python sagemaker/deploy.py --local-mode --epochs 2
```

### Endpoint Tests

```bash
# Test deployed endpoint
python sagemaker/test_endpoint.py \
  --endpoint album-classifier \
  --image backend/data/images/0.jpg
```

## 💰 Cost Optimization

### Training
- **Development**: Use `ml.m5.xlarge` ($0.23/hr)
- **Production**: Use `ml.p3.2xlarge` ($3.06/hr) with GPU
- **Cost Saving**: Use Spot Instances (up to 70% savings)

### Inference
- **Low Traffic**: `ml.t2.medium` ($0.047/hr)
- **Medium Traffic**: `ml.m5.large` ($0.115/hr)
- **High Traffic**: `ml.m5.xlarge` with auto-scaling

### Tips
- Use local mode for development
- Stop endpoints when not in use
- Enable auto-scaling for variable loads
- Monitor with CloudWatch

## 🔍 Monitoring

### CloudWatch Metrics

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

# Get endpoint invocations
cloudwatch.get_metric_statistics(
    Namespace='AWS/SageMaker',
    MetricName='ModelLatency',
    Dimensions=[{'Name': 'EndpointName', 'Value': 'album-classifier'}],
    StartTime=datetime.now() - timedelta(hours=1),
    EndTime=datetime.now(),
    Period=300,
    Statistics=['Average', 'Maximum']
)
```

### Model Performance

Track accuracy, precision, recall:
- Training logs in CloudWatch
- Validation metrics in output artifacts
- Inference metrics via data capture

## 🚨 Troubleshooting

### Common Issues

**Issue**: Model not found
```bash
# Solution: Train model first
python sagemaker/local_train.py
```

**Issue**: AWS credentials not configured
```bash
# Solution: Configure AWS CLI
aws configure
```

**Issue**: Insufficient permissions
```bash
# Solution: Ensure SageMaker role has required permissions
# - AmazonSageMakerFullAccess
# - S3 access to your bucket
```

**Issue**: Out of memory during training
```bash
# Solution: Reduce batch size
python sagemaker/deploy.py --batch-size 4
```

### Debug Mode

Enable verbose logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 📚 Additional Resources

- [SageMaker Python SDK](https://sagemaker.readthedocs.io/)
- [PyTorch on SageMaker](https://docs.aws.amazon.com/sagemaker/latest/dg/pytorch.html)
- [SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples)

## 📄 License

MIT

