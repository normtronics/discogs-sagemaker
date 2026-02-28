# SageMaker Integration Guide

This guide explains how the CDK infrastructure works with SageMaker and how to run training jobs directly from SageMaker Studio/Notebooks.

## Architecture Overview

```
┌─────────────────────┐
│  SageMaker Studio   │  ← You can run jobs from here
│  / Notebooks        │
└──────────┬──────────┘
           │
           │ (Option 1: Direct)
           ▼
┌─────────────────────┐
│  SageMaker          │  ← Training jobs run here
│  Training Jobs      │
└─────────────────────┘

┌─────────────────────┐
│  Lambda Function    │  ← (Option 2: Via Lambda)
│  (CDK Deployed)     │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  SageMaker          │
│  Training Jobs      │
└─────────────────────┘
```

## How It Works

### Option 1: Direct from SageMaker Studio (Recommended)

Run training jobs directly from SageMaker Studio notebooks using the SageMaker SDK. This is the most straightforward approach.

**Advantages:**
- Full control over job parameters
- Interactive development and experimentation
- Easy to monitor and debug
- No Lambda overhead

### Option 2: Via Lambda Function (CDK Deployed)

Use the Lambda function deployed by CDK to trigger jobs. Useful for:
- Scheduled training (EventBridge)
- API-triggered training
- Integration with other AWS services

**Advantages:**
- Automated scheduling
- Can be triggered from external systems
- No need to manage SageMaker Studio sessions

## Running from SageMaker Studio

### Step 1: Open SageMaker Studio

1. Go to [SageMaker Console](https://console.aws.amazon.com/sagemaker/)
2. Click "SageMaker Studio" in the left sidebar
3. Click "Open Studio" (or create a domain if needed)
4. Create a new notebook

### Step 2: Install Dependencies

In your notebook, run:

```python
!pip install boto3 sagemaker aiohttp aiofiles torch torchvision pillow scikit-learn
```

### Step 3: Run Training Job

Use the provided notebook template (see `notebooks/sagemaker-notebook-example.ipynb`) or run directly:

```python
import boto3
import sagemaker
from sagemaker.pytorch import PyTorch
from datetime import datetime

# Get SageMaker session and role
region = 'us-east-1'
boto_session = boto3.Session(region_name=region)
sagemaker_session = sagemaker.Session(boto_session=boto_session)
role = sagemaker.get_execution_role()  # Automatically gets the role

# Configuration
bucket = 'your-sagemaker-bucket'  # Replace with your bucket name
manifest_path = f's3://{bucket}/album-classifier/data/releases_manifest_enriched.jsonl'

# Create estimator
estimator = PyTorch(
    entry_point='full_pipeline_train.py',
    source_dir=f's3://{bucket}/album-classifier/source',  # Source code from S3
    role=role,
    instance_type='ml.p3.2xlarge',
    instance_count=1,
    framework_version='2.5.1',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
        'manifest-path': manifest_path,
        'max-concurrent': '10',
        'skip-download': 'false',
        'skip-upload': 'false',
        'skip-training': 'false',
        'skip-deploy': 'false',
        'endpoint-instance-type': 'ml.m5.large',
    },
    output_path=f's3://{bucket}/album-classifier/models',
    code_location=f's3://{bucket}/album-classifier/code',
    sagemaker_session=sagemaker_session,
    base_job_name='album-classifier-full',
    max_run=86400 * 2,  # 48 hours max
    use_spot_instances=True,  # Cost savings
    max_wait=86400 * 2,
    checkpoint_s3_uri=f's3://{bucket}/album-classifier/checkpoints',
    volume_size=100,  # GB - for image storage
)

# Start training
print("Starting full pipeline training job...")
print(f"Manifest: {manifest_path}")
print(f"Instance: ml.p3.2xlarge")
print(f"Output: s3://{bucket}/album-classifier/models")

estimator.fit({'training': f's3://{bucket}/album-classifier/data'})

print(f"\nTraining complete!")
print(f"Model artifacts: {estimator.model_data}")
print(f"Job name: {estimator.latest_training_job.name}")
```

### Step 4: Monitor Progress

```python
# Get job name
job_name = estimator.latest_training_job.name

# Describe job
import boto3
sagemaker_client = boto3.client('sagemaker', region_name=region)
response = sagemaker_client.describe_training_job(TrainingJobName=job_name)

print(f"Status: {response['TrainingJobStatus']}")
print(f"Start time: {response['TrainingStartTime']}")
if 'TrainingEndTime' in response:
    print(f"End time: {response['TrainingEndTime']}")
```

### Step 5: View Logs

In SageMaker Studio:
1. Go to Training → Training jobs
2. Click on your job name
3. Click "View logs" tab

Or in the notebook:

```python
# Stream logs
from sagemaker.logs import TrainingLogs

logs = TrainingLogs(sagemaker_session, estimator.latest_training_job.name)
logs.stream()
```

## Using the Trigger Script from SageMaker

You can also use the `trigger_full_pipeline.py` script from SageMaker Studio:

### Option A: Upload Script to Studio

1. Upload `backend/sagemaker/trigger_full_pipeline.py` to your Studio environment
2. Run:

```python
# In notebook
import sys
sys.path.append('/path/to/script')

from trigger_full_pipeline import create_full_pipeline_job

result = create_full_pipeline_job(
    instance_type='ml.p3.2xlarge',
    epochs=10,
    batch_size=16,
    wait=False  # Set to True to wait for completion
)

print(f"Job started: {result['job_name']}")
```

### Option B: Use Environment Variables

Set up environment variables in Studio:

```python
import os
os.environ['SAGEMAKER_ROLE'] = 'arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole'
os.environ['BUCKET_NAME'] = 'your-sagemaker-bucket'
os.environ['AWS_REGION'] = 'us-east-1'
```

Then use the trigger script normally.

## Using Lambda Function from SageMaker

If you've deployed the CDK stack, you can invoke the Lambda function from SageMaker:

```python
import boto3
import json

lambda_client = boto3.client('lambda', region_name='us-east-1')

# Get function name from CDK stack outputs
# Or hardcode: function_name = 'FullPipelineStack-TriggerFullPipelineFunction-XXXXX'

response = lambda_client.invoke(
    FunctionName='FullPipelineStack-TriggerFullPipelineFunction-XXXXX',
    InvocationType='RequestResponse',  # Use 'Event' for async
    Payload=json.dumps({
        'instance_type': 'ml.p3.2xlarge',
        'epochs': 10,
        'batch_size': 16,
        'learning_rate': 0.001
    })
)

result = json.loads(response['Payload'].read())
print(result)
```

## Prerequisites

Before running from SageMaker Studio:

1. **Upload Source Code to S3**:
   ```bash
   cd backend/aws
   ./upload_source_to_s3.sh
   ```

2. **Upload Manifest**:
   ```bash
   aws s3 cp data/releases_manifest_enriched.jsonl \
     s3://your-bucket/album-classifier/data/
   ```

3. **Verify S3 Structure**:
   ```
   s3://your-bucket/
     album-classifier/
       source/
         source.tar.gz          # Training scripts
       data/
         releases_manifest_enriched.jsonl  # Manifest file
       models/                  # Model outputs (created by jobs)
       code/                    # Code artifacts (created by jobs)
       checkpoints/             # Training checkpoints
   ```

## Monitoring Jobs in SageMaker Console

1. **Training Jobs**:
   - Go to SageMaker → Training → Training jobs
   - View status, metrics, logs
   - Click job name for details

2. **CloudWatch Logs**:
   - Go to CloudWatch → Log groups
   - Find `/aws/sagemaker/TrainingJobs/album-classifier-full-*`
   - View real-time logs

3. **CloudWatch Metrics**:
   - Go to CloudWatch → Metrics
   - SageMaker → TrainingJob
   - View GPU/CPU utilization, training loss, etc.

## Best Practices

1. **Use Spot Instances**: Already enabled by default (50-70% cost savings)
2. **Right-size Instances**: Start with `ml.m5.xlarge` for testing
3. **Monitor Costs**: Use AWS Cost Explorer
4. **Use Checkpoints**: Enable checkpointing for long training jobs
5. **Version Control**: Tag S3 objects with versions
6. **Clean Up**: Delete old training jobs and endpoints

## Troubleshooting

### Source Code Not Found

```python
# Verify source code is uploaded
import boto3
s3_client = boto3.client('s3')
response = s3_client.list_objects_v2(
    Bucket='your-bucket',
    Prefix='album-classifier/source/'
)
print(response['Contents'])
```

### Permission Errors

Ensure your SageMaker execution role has:
- S3 read/write access
- SageMaker training permissions
- CloudWatch Logs write access

### Job Fails Immediately

Check:
1. Source code is accessible
2. Manifest file exists
3. IAM role has correct permissions
4. Instance type is available in your region

## Next Steps

- See `notebooks/sagemaker-notebook-example.ipynb` for a complete notebook template
- See `RUN_IN_AWS.md` for more deployment options
- See `FULL_PIPELINE_README.md` for pipeline details


