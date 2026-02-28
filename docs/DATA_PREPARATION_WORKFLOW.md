# Data Preparation Workflow Guide

This guide shows how to set up a SageMaker workflow to automatically build your dataset (enrich manifest + download images) on demand.

## Overview

The workflow uses **SageMaker Processing Jobs** to:
1. ✅ Enrich manifest with image URLs from Discogs API
2. ✅ Download all images
3. ✅ Upload everything to S3

## Architecture

```
Trigger (Lambda/Studio/CLI)
    ↓
SageMaker Processing Job
    ├── Step 1: Enrich manifest (Discogs API)
    ├── Step 2: Download images
    └── Step 3: Upload to S3
    ↓
S3 Output
    ├── releases_manifest_enriched.jsonl
    └── images/
        ├── 0.jpg
        ├── 1.jpg
        └── ...
```

---

## Option 1: Run from SageMaker Studio (Easiest)

### Step 1: Upload Input Manifest to S3

```bash
# Upload your base manifest
aws s3 cp data/releases_manifest_50.jsonl \
  s3://your-bucket/data/releases_manifest.jsonl
```

### Step 2: Create Notebook in Studio

Create a new notebook and run:

```python
import boto3
import sagemaker
from sagemaker.processing import ScriptProcessor, ProcessingInput, ProcessingOutput
import os
from datetime import datetime

# Configuration
BUCKET_NAME = 'your-bucket'  # ← Change this
INPUT_MANIFEST = 's3://your-bucket/data/releases_manifest.jsonl'
S3_PREFIX = 'data'
INSTANCE_TYPE = 'ml.m5.xlarge'  # CPU instance
REGION = 'us-east-1'

# Get role
role = sagemaker.get_execution_role()

# Discogs API credentials (set as environment variables or secrets)
DISCOGS_KEY = os.getenv('DISCOGS_CONSUMER_KEY')
DISCOGS_SECRET = os.getenv('DISCOGS_CONSUMER_SECRET')

# Create script processor
processor = ScriptProcessor(
    role=role,
    image_uri='763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-cpu-py311',
    command=['python3'],
    instance_type=INSTANCE_TYPE,
    instance_count=1,
    sagemaker_session=sagemaker.Session(),
)

# Upload the data_preparation.py script to S3 first
# Or use local path if running from Studio
script_path = 'data_preparation.py'  # Make sure this file is in your Studio environment

# Run processing job
job_name = f'data-prep-{datetime.now().strftime("%Y%m%d-%H%M%S")}'

processor.run(
    code=script_path,
    inputs=[
        ProcessingInput(
            source=INPUT_MANIFEST,
            destination='/opt/ml/processing/input',
            input_name='manifest'
        )
    ],
    outputs=[
        ProcessingOutput(
            source='/opt/ml/processing/output',
            destination=f's3://{BUCKET_NAME}/{S3_PREFIX}/',
            output_name='output'
        )
    ],
    arguments=[
        '--s3-bucket', BUCKET_NAME,
        '--s3-prefix', S3_PREFIX,
        '--region', REGION,
    ],
    job_name=job_name,
    environment={
        'DISCOGS_CONSUMER_KEY': DISCOGS_KEY,
        'DISCOGS_CONSUMER_SECRET': DISCOGS_SECRET,
    },
    wait=False,  # Don't wait, return immediately
)

print(f"✓ Job started: {job_name}")
print(f"Monitor: https://console.aws.amazon.com/sagemaker/home#/processing-jobs/{job_name}")
```

### Step 3: Monitor Progress

```python
# Check job status
import boto3
sagemaker_client = boto3.client('sagemaker', region_name=REGION)
response = sagemaker_client.describe_processing_job(ProcessingJobName=job_name)
print(f"Status: {response['ProcessingJobStatus']}")
```

Or check in console: **SageMaker** → **Processing** → **Processing jobs**

---

## Option 2: Use the Trigger Script

### Step 1: Upload Script to S3

```bash
cd backend/sagemaker

# Package the script
tar -czf data_prep_source.tar.gz data_preparation.py requirements.txt

# Upload to S3
aws s3 cp data_prep_source.tar.gz s3://your-bucket/code/data_prep_source.tar.gz
```

### Step 2: Run Trigger Script

```bash
cd backend/sagemaker

# Set environment variables
export DISCOGS_CONSUMER_KEY=your-key
export DISCOGS_CONSUMER_SECRET=your-secret

# Run trigger script
python trigger_data_preparation.py \
  --bucket your-bucket \
  --input-manifest s3://your-bucket/data/releases_manifest.jsonl \
  --s3-prefix data \
  --instance-type ml.m5.xlarge
```

---

## Option 3: Lambda Function (Automated Trigger)

Create a Lambda function that triggers the processing job:

```python
import boto3
import json
import os

def lambda_handler(event, context):
    """Trigger data preparation processing job"""
    
    sagemaker = boto3.client('sagemaker', region_name='us-east-1')
    
    # Configuration
    bucket_name = os.environ['BUCKET_NAME']
    input_manifest = os.environ['INPUT_MANIFEST']
    role_arn = os.environ['SAGEMAKER_ROLE_ARN']
    
    # Create processing job
    job_name = f'data-prep-{datetime.now().strftime("%Y%m%d-%H%M%S")}'
    
    response = sagemaker.create_processing_job(
        ProcessingJobName=job_name,
        RoleArn=role_arn,
        ProcessingResources={
            'ClusterConfig': {
                'InstanceCount': 1,
                'InstanceType': 'ml.m5.xlarge',
            }
        },
        ProcessingInputs=[
            {
                'InputName': 'manifest',
                'S3Input': {
                    'S3Uri': input_manifest,
                    'LocalPath': '/opt/ml/processing/input',
                    'S3DataType': 'S3Prefix',
                    'S3InputMode': 'File',
                }
            }
        ],
        ProcessingOutputConfig={
            'Outputs': [
                {
                    'OutputName': 'output',
                    'S3Output': {
                        'S3Uri': f's3://{bucket_name}/data/',
                        'LocalPath': '/opt/ml/processing/output',
                        'S3UploadMode': 'EndOfJob',
                    }
                }
            ]
        },
        AppSpecification={
            'ImageUri': '763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-cpu-py311',
            'ContainerEntrypoint': ['python3', '/opt/ml/processing/code/data_preparation.py'],
        },
        Environment={
            'DISCOGS_CONSUMER_KEY': os.environ['DISCOGS_CONSUMER_KEY'],
            'DISCOGS_CONSUMER_SECRET': os.environ['DISCOGS_CONSUMER_SECRET'],
        },
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'job_name': job_name,
            'status': 'Started'
        })
    }
```

---

## Option 4: Step Functions Workflow (Advanced)

Create a Step Functions state machine for orchestration:

```json
{
  "Comment": "Data Preparation Workflow",
  "StartAt": "StartDataPreparation",
  "States": {
    "StartDataPreparation": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createProcessingJob.sync",
      "Parameters": {
        "ProcessingJobName": "data-prep-${$.Execution.Name}",
        "RoleArn": "arn:aws:iam::ACCOUNT:role/SageMakerRole",
        "ProcessingResources": {
          "ClusterConfig": {
            "InstanceCount": 1,
            "InstanceType": "ml.m5.xlarge"
          }
        },
        "AppSpecification": {
          "ImageUri": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-cpu-py311"
        }
      },
      "Next": "NotifyComplete"
    },
    "NotifyComplete": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sns:publish",
      "Parameters": {
        "TopicArn": "arn:aws:sns:us-east-1:ACCOUNT:data-prep-complete",
        "Message": "Data preparation job completed"
      },
      "End": true
    }
  }
}
```

---

## Prerequisites

### 1. Discogs API Credentials

Set environment variables or use AWS Secrets Manager:

```bash
export DISCOGS_CONSUMER_KEY=your-key
export DISCOGS_CONSUMER_SECRET=your-secret
```

Or store in Secrets Manager:

```bash
aws secretsmanager create-secret \
  --name discogs-api-credentials \
  --secret-string '{"key":"your-key","secret":"your-secret"}'
```

### 2. S3 Bucket Setup

```bash
# Create bucket
aws s3 mb s3://your-bucket

# Upload input manifest
aws s3 cp data/releases_manifest_50.jsonl \
  s3://your-bucket/data/releases_manifest.jsonl
```

### 3. SageMaker Execution Role

Ensure your SageMaker execution role has:
- S3 read/write permissions
- SageMaker processing permissions
- Secrets Manager read (if using secrets)

---

## Monitoring

### Check Job Status

```bash
# Via CLI
aws sagemaker describe-processing-job \
  --processing-job-name data-prep-20240101-120000

# Via Python
import boto3
client = boto3.client('sagemaker')
response = client.describe_processing_job(
    ProcessingJobName='data-prep-20240101-120000'
)
print(response['ProcessingJobStatus'])
```

### View Logs

1. Go to **SageMaker Console** → **Processing** → **Processing jobs**
2. Click on your job name
3. Click **View logs** → Opens CloudWatch

### Check Output

```bash
# List output files
aws s3 ls s3://your-bucket/data/ --recursive

# Check enriched manifest
aws s3 cp s3://your-bucket/data/releases_manifest_enriched.jsonl - | head -5

# Count images
aws s3 ls s3://your-bucket/data/images/ | wc -l
```

---

## Cost Estimates

**Processing Job**:
- `ml.m5.xlarge`: ~$0.23/hour
- `ml.m5.2xlarge`: ~$0.46/hour
- `ml.p3.2xlarge`: ~$3.06/hour (if you need GPU for image processing)

**Typical Runtime**:
- 50 releases: ~5-10 minutes
- 500 releases: ~1-2 hours
- 5000 releases: ~10-20 hours

**Tip**: Use Spot instances to save 50-90%:

```python
processor.run(
    # ... other config ...
    use_spot_instances=True,
    max_wait=86400,  # 24 hours max wait
)
```

---

## Troubleshooting

### Job Fails Immediately

- Check CloudWatch logs
- Verify Discogs API credentials
- Ensure input manifest exists in S3
- Check IAM role permissions

### Rate Limiting Errors

The script includes rate limiting, but if you see errors:
- Increase delays in `data_preparation.py`
- Use smaller batches
- Check Discogs API status

### Out of Memory

- Use larger instance type (`ml.m5.2xlarge`)
- Process in smaller batches
- Increase instance count for parallel processing

---

## Next Steps

After data preparation completes:

1. ✅ Verify output in S3
2. ✅ Use enriched manifest for training
3. ✅ Train model (see `docs/STUDIO_WALKTHROUGH.md`)
4. ✅ Deploy endpoint

---

## Quick Reference

**Start Job**:
```bash
python trigger_data_preparation.py \
  --bucket your-bucket \
  --input-manifest s3://your-bucket/data/releases_manifest.jsonl
```

**Monitor**:
```bash
aws sagemaker describe-processing-job --processing-job-name JOB_NAME
```

**Check Output**:
```bash
aws s3 ls s3://your-bucket/data/ --recursive
```

---

**Ready to automate?** Start with Option 1 (Studio notebook) for the easiest setup!
