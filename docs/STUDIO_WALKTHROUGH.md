# SageMaker Studio Walkthrough: Train & Deploy Your Model

Step-by-step guide to train and deploy your album classifier model using SageMaker Studio.

## Prerequisites Checklist

- ✅ SageMaker Studio domain created
- ✅ S3 bucket created (or know the bucket name)
- ✅ Training data ready (manifest file and images)

---

## Step 1: Prepare Your Code and Data

### 1.1 Create S3 Bucket (if you don't have one)

```bash
# Replace 'your-ml-bucket' with your unique bucket name
aws s3 mb s3://your-ml-bucket --region us-east-1

# Verify it was created
aws s3 ls | grep your-ml-bucket
```

### 1.2 Upload Training Data to S3

From your project root:

```bash
# Upload manifest file
aws s3 cp data/releases_manifest_enriched.jsonl \
  s3://your-ml-bucket/data/releases_manifest_enriched.jsonl

# Upload images (if you have them locally)
aws s3 sync backend/data/images/ \
  s3://your-ml-bucket/data/images/

# Verify uploads
aws s3 ls s3://your-ml-bucket/data/ --recursive
```

### 1.3 Package and Upload Training Code

```bash
# Navigate to sagemaker directory
cd backend/sagemaker

# Package your code
tar -czf sourcedir.tar.gz train.py inference.py requirements.txt

# Upload to S3
aws s3 cp sourcedir.tar.gz s3://your-ml-bucket/code/sourcedir.tar.gz

# Verify
aws s3 ls s3://your-ml-bucket/code/
```

**Note**: Keep track of your bucket name - you'll need it in Studio!

---

## Step 2: Open SageMaker Studio

### 2.1 Access Studio

1. Go to [SageMaker Console](https://console.aws.amazon.com/sagemaker/)
2. Click **SageMaker Studio** in the left sidebar
3. Find your domain and click **Open Studio**
4. Wait for Studio to load (may take 1-2 minutes)

### 2.2 Create a New Notebook

1. In Studio, click **File** → **New** → **Notebook**
2. Choose **Python 3** kernel
3. Click **Select**

---

## Step 3: Install Required Libraries

In your new notebook, run this cell:

```python
!pip install sagemaker boto3
```

---

## Step 4: Configure Your Training Job

Create a new cell and paste this code (update the bucket name):

```python
import sagemaker
from sagemaker.pytorch import PyTorch
import boto3

# Configuration - UPDATE THESE VALUES
BUCKET_NAME = 'your-ml-bucket'  # ← Change this!
REGION = 'us-east-1'  # Change if your bucket is in a different region

# Get execution role (automatically detected in Studio)
role = sagemaker.get_execution_role()
print(f"Using role: {role}")

# Verify bucket access
s3_client = boto3.client('s3', region_name=REGION)
try:
    s3_client.head_bucket(Bucket=BUCKET_NAME)
    print(f"✓ Bucket '{BUCKET_NAME}' is accessible")
except Exception as e:
    print(f"✗ Error accessing bucket: {e}")
    print("Make sure the bucket exists and your role has S3 permissions")
```

Run this cell to verify your setup.

---

## Step 5: Create and Start Training Job

Create a new cell with the training job code:

```python
# Create PyTorch estimator
estimator = PyTorch(
    entry_point='train.py',  # Your training script
    source_dir=f's3://{BUCKET_NAME}/code/sourcedir.tar.gz',  # Your code package
    role=role,
    instance_type='ml.m5.xlarge',  # Start with CPU (cheaper). Use 'ml.p3.2xlarge' for GPU
    instance_count=1,
    framework_version='2.5.0',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
    },
    output_path=f's3://{BUCKET_NAME}/models/',  # Where model artifacts will be saved
    sagemaker_session=sagemaker.Session(),
    base_job_name='album-classifier',  # Base name for training job
    max_run=86400,  # Max runtime: 24 hours
)

# Print job configuration
print("Training job configuration:")
print(f"  Instance type: ml.m5.xlarge")
print(f"  Framework: PyTorch 2.5.0")
print(f"  Output path: s3://{BUCKET_NAME}/models/")
print(f"  Data path: s3://{BUCKET_NAME}/data/")
print("\nStarting training job...")

# Start training
estimator.fit({'training': f's3://{BUCKET_NAME}/data/'})
```

**Important**: 
- Replace `your-ml-bucket` with your actual bucket name
- `ml.m5.xlarge` is CPU-based (cheaper, ~$0.23/hour)
- `ml.p3.2xlarge` is GPU-based (faster, ~$3.06/hour)

Run this cell to start training. This will take 10-30 minutes depending on your instance type.

---

## Step 6: Monitor Training Progress

### Option A: Watch in Notebook

The `estimator.fit()` call will show progress. You can also check:

```python
# Get job name
job_name = estimator.latest_training_job.name
print(f"Training job name: {job_name}")

# Check status
import boto3
sagemaker_client = boto3.client('sagemaker', region_name=REGION)
response = sagemaker_client.describe_training_job(TrainingJobName=job_name)
print(f"Status: {response['TrainingJobStatus']}")
```

### Option B: Check in Console

1. Go to **Training** → **Training jobs** in SageMaker console
2. Click on your job name
3. View **Monitor** tab for metrics
4. Click **View logs** for CloudWatch logs

---

## Step 7: Deploy Model to Endpoint

Once training completes, deploy the model:

```python
# Create model from training job
from sagemaker.pytorch import PyTorchModel

model = PyTorchModel(
    model_data=estimator.model_data,  # Model artifacts from training
    role=role,
    entry_point='inference.py',  # Your inference script
    framework_version='2.5.0',
    py_version='py311',
    source_dir=f's3://{BUCKET_NAME}/code/sourcedir.tar.gz',  # Same code package
)

# Deploy endpoint
print("Deploying model to endpoint...")
print("This will take 5-10 minutes...")

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',  # Cheaper: ml.t2.medium, Recommended: ml.m5.large
    endpoint_name='album-classifier',
    wait=True  # Wait for deployment to complete
)

print(f"\n✓ Endpoint deployed!")
print(f"Endpoint name: album-classifier")
print(f"Endpoint ARN: {predictor.endpoint}")
```

**Instance Types for Endpoints**:
- `ml.t2.medium` - Cheapest ($0.047/hour)
- `ml.m5.large` - Recommended ($0.115/hour)
- `ml.m5.xlarge` - Faster ($0.23/hour)

---

## Step 8: Test Your Endpoint

Test the deployed endpoint:

```python
# Test with a sample image
import base64
from PIL import Image
import io

# Option 1: Test with image from S3 (if you uploaded images)
# Or download a test image first
# !wget https://example.com/test-album.jpg

# Option 2: Create a test image (for testing)
# Or use an image you have locally

# Read image file
with open('test_image.jpg', 'rb') as f:
    image_data = f.read()

# Make prediction
response = predictor.predict(
    image_data,
    initial_args={'ContentType': 'image/jpeg'}
)

print("Predictions:")
import json
print(json.dumps(response, indent=2))
```

---

## Step 9: Complete Notebook

Here's a complete notebook you can copy-paste:

```python
# ============================================
# SageMaker Training & Deployment Notebook
# ============================================

import sagemaker
from sagemaker.pytorch import PyTorch, PyTorchModel
import boto3
import json

# ============================================
# CONFIGURATION - UPDATE THESE VALUES
# ============================================
BUCKET_NAME = 'your-ml-bucket'  # ← CHANGE THIS!
REGION = 'us-east-1'
ENDPOINT_NAME = 'album-classifier'

# ============================================
# Setup
# ============================================
role = sagemaker.get_execution_role()
print(f"Role: {role}")

s3_client = boto3.client('s3', region_name=REGION)
try:
    s3_client.head_bucket(Bucket=BUCKET_NAME)
    print(f"✓ Bucket accessible")
except Exception as e:
    print(f"✗ Bucket error: {e}")

# ============================================
# Training
# ============================================
print("\n" + "="*50)
print("STEP 1: Training")
print("="*50)

estimator = PyTorch(
    entry_point='train.py',
    source_dir=f's3://{BUCKET_NAME}/code/sourcedir.tar.gz',
    role=role,
    instance_type='ml.m5.xlarge',  # CPU: ml.m5.xlarge, GPU: ml.p3.2xlarge
    instance_count=1,
    framework_version='2.5.0',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
    },
    output_path=f's3://{BUCKET_NAME}/models/',
    sagemaker_session=sagemaker.Session(),
    base_job_name='album-classifier',
    max_run=86400,
)

print("Starting training...")
estimator.fit({'training': f's3://{BUCKET_NAME}/data/'})

print(f"\n✓ Training complete!")
print(f"Model artifacts: {estimator.model_data}")

# ============================================
# Deployment
# ============================================
print("\n" + "="*50)
print("STEP 2: Deployment")
print("="*50)

model = PyTorchModel(
    model_data=estimator.model_data,
    role=role,
    entry_point='inference.py',
    framework_version='2.5.0',
    py_version='py311',
    source_dir=f's3://{BUCKET_NAME}/code/sourcedir.tar.gz',
)

print("Deploying endpoint...")
predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',
    endpoint_name=ENDPOINT_NAME,
    wait=True
)

print(f"\n✓ Endpoint deployed: {ENDPOINT_NAME}")

# ============================================
# Testing
# ============================================
print("\n" + "="*50)
print("STEP 3: Testing")
print("="*50)

# Test with sample image (update path as needed)
# with open('test_image.jpg', 'rb') as f:
#     image_data = f.read()
#     response = predictor.predict(image_data, initial_args={'ContentType': 'image/jpeg'})
#     print(json.dumps(response, indent=2))

print("Endpoint ready for use!")
print(f"Endpoint name: {ENDPOINT_NAME}")
```

---

## Troubleshooting

### Error: "Bucket not found"

- Verify bucket name is correct
- Check bucket exists: `aws s3 ls s3://your-bucket-name`
- Ensure bucket is in the same region as SageMaker

### Error: "Access Denied"

- Check your SageMaker execution role has S3 permissions
- Verify role can read from `s3://your-bucket/data/`
- Verify role can write to `s3://your-bucket/models/`

### Error: "Training job failed"

1. Check CloudWatch logs:
   - Go to **Training jobs** → Click job name → **View logs**
2. Common issues:
   - Missing manifest file in S3
   - Missing images in S3
   - Code errors in `train.py`
   - Insufficient instance capacity (try different instance type)

### Error: "Endpoint creation failed"

- Verify model artifacts exist: `aws s3 ls s3://your-bucket/models/`
- Check endpoint name is unique
- Verify instance type is available in your region

### Training Takes Too Long

- Use GPU instance: `ml.p3.2xlarge` (faster but more expensive)
- Reduce epochs or batch size
- Use smaller dataset for testing

---

## Next Steps

After deployment:

1. ✅ **Test endpoint** (Step 8 above)
2. ✅ **Deploy API Gateway + Lambda** (see `docs/DEPLOY_INFERENCE.md`)
3. ✅ **Configure frontend** (see `docs/FRONTEND_API_GATEWAY_SETUP.md`)

---

## Cost Management

**Training Costs**:
- `ml.m5.xlarge` (CPU): ~$0.23/hour
- `ml.p3.2xlarge` (GPU): ~$3.06/hour

**Endpoint Costs**:
- `ml.m5.large`: ~$0.115/hour
- `ml.t2.medium`: ~$0.047/hour

**Tip**: Delete endpoints when not in use to save costs!

```python
# Delete endpoint when done testing
predictor.delete_endpoint()
predictor.delete_model()
```

---

## Quick Reference

**S3 Structure**:
```
s3://your-bucket/
  ├── data/
  │   ├── releases_manifest_enriched.jsonl
  │   └── images/
  │       ├── 0.jpg
  │       ├── 1.jpg
  │       └── ...
  ├── code/
  │   └── sourcedir.tar.gz
  └── models/
      └── album-classifier-YYYY-MM-DD-HH-MM-SS/
          └── output/
              └── model.tar.gz
```

**Key Commands**:
```python
# Check training status
sagemaker_client.describe_training_job(TrainingJobName=job_name)

# Check endpoint status
sagemaker_client.describe_endpoint(EndpointName='album-classifier')

# List endpoints
sagemaker_client.list_endpoints()
```

---

**Ready to start?** Begin with Step 1 and work through each step. If you get stuck, check the troubleshooting section or the detailed guides:
- [Complete Setup Guide](./SAGEMAKER_COMPLETE_SETUP.md)
- [Console Guide](./SAGEMAKER_CONSOLE_GUIDE.md)
