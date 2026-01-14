# Running the Full Pipeline Entirely in AWS

This guide shows you how to run the full pipeline training job entirely within AWS, without needing to run anything from your local machine.

## Overview

There are several ways to run the pipeline entirely in AWS:

1. **Lambda + EventBridge** (Recommended for scheduled runs)
2. **Lambda + API Gateway** (For on-demand triggers)
3. **EC2 Instance** (For interactive development)
4. **SageMaker Studio** (For notebook-based workflows)
5. **AWS CloudShell** (Quick one-time runs)
6. **Step Functions** (For complex orchestration)

## Option 1: Lambda + EventBridge (Scheduled)

Best for: Automated, scheduled training jobs

### Setup

```bash
cd backend/aws
chmod +x setup_full_pipeline_aws.sh
./setup_full_pipeline_aws.sh
```

This script will:
- Upload source code to S3
- Create Lambda function
- Set up EventBridge schedule (optional)
- Configure IAM roles and permissions

### Manual Invocation

```bash
# Invoke Lambda function
aws lambda invoke \
  --function-name trigger-full-pipeline-training \
  --payload '{
    "instance_type": "ml.p3.2xlarge",
    "epochs": 10,
    "batch_size": 16
  }' \
  /tmp/output.json

cat /tmp/output.json
```

### Scheduled Execution

The setup script creates an EventBridge rule that runs weekly on Mondays at 2 AM UTC. To customize:

```bash
# Update schedule
aws events put-rule \
  --name album-classifier-full-pipeline-weekly \
  --schedule-expression "cron(0 2 ? * MON *)" \
  --state ENABLED

# Disable schedule
aws events disable-rule --name album-classifier-full-pipeline-weekly

# Enable schedule
aws events enable-rule --name album-classifier-full-pipeline-weekly
```

## Option 2: Lambda + API Gateway (On-Demand)

Best for: Triggering training from external systems or webhooks

### Setup API Gateway

```bash
# Create REST API
API_ID=$(aws apigateway create-rest-api \
  --name album-classifier-training-api \
  --query 'id' --output text)

# Create resource
RESOURCE_ID=$(aws apigateway create-resource \
  --rest-api-id $API_ID \
  --path-part trigger \
  --parent-id $(aws apigateway get-resources --rest-api-id $API_ID --query 'items[0].id' --output text) \
  --query 'id' --output text)

# Create POST method
aws apigateway put-method \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --authorization-type NONE

# Set Lambda integration
aws apigateway put-integration \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method POST \
  --type AWS_PROXY \
  --integration-http-method POST \
  --uri arn:aws:apigateway:${AWS_REGION}:lambda:path/2015-03-31/functions/arn:aws:lambda:${AWS_REGION}:${ACCOUNT_ID}:function:trigger-full-pipeline-training/invocations

# Deploy API
aws apigateway create-deployment \
  --rest-api-id $API_ID \
  --stage-name prod
```

### Invoke via API

```bash
# Get API endpoint
API_ENDPOINT="https://${API_ID}.execute-api.${AWS_REGION}.amazonaws.com/prod/trigger"

# Trigger training
curl -X POST $API_ENDPOINT \
  -H "Content-Type: application/json" \
  -d '{
    "instance_type": "ml.p3.2xlarge",
    "epochs": 10
  }'
```

## Option 3: EC2 Instance

Best for: Interactive development and testing

### Launch EC2 Instance

```bash
# Launch instance with SageMaker SDK pre-installed
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name your-key-pair \
  --security-group-ids sg-xxxxxxxxx \
  --user-data file://ec2-setup.sh
```

### EC2 Setup Script (`ec2-setup.sh`)

```bash
#!/bin/bash
# Install dependencies
sudo yum update -y
sudo yum install -y python3-pip git

# Clone repository
git clone https://github.com/your-repo/dsicogs-sage-app.git
cd dsicogs-sage-app/backend/sagemaker

# Install dependencies
pip3 install -r requirements.txt boto3 sagemaker

# Configure AWS credentials (use IAM role instead)
# aws configure

# Run training
python3 trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl
```

### Run on EC2

```bash
# SSH into instance
ssh -i your-key.pem ec2-user@your-instance-ip

# Run pipeline
cd dsicogs-sage-app/backend/sagemaker
python3 trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl \
  --instance-type ml.p3.2xlarge
```

## Option 4: SageMaker Studio

Best for: Notebook-based workflows and experimentation

### Setup

1. Open SageMaker Studio
2. Create new notebook
3. Install dependencies:

```python
!pip install boto3 sagemaker aiohttp aiofiles torch torchvision pillow scikit-learn
```

### Run in Notebook

```python
import boto3
import sagemaker
from sagemaker.pytorch import PyTorch
from datetime import datetime

# Get session
region = 'us-east-1'
boto_session = boto3.Session(region_name=region)
sagemaker_session = sagemaker.Session(boto_session=boto_session)

# Get role and bucket from environment
role = sagemaker.get_execution_role()
bucket = 'your-bucket-name'

# Create estimator
estimator = PyTorch(
    entry_point='full_pipeline_train.py',
    source_dir='s3://{}/album-classifier/source'.format(bucket),
    role=role,
    instance_type='ml.p3.2xlarge',
    instance_count=1,
    framework_version='2.5.1',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
        'manifest-path': f's3://{bucket}/album-classifier/data/releases_manifest_enriched.jsonl',
    },
    output_path=f's3://{bucket}/album-classifier/models',
    sagemaker_session=sagemaker_session,
    max_run=86400 * 2,
    use_spot_instances=True,
    volume_size=100,
)

# Start training
estimator.fit({'training': f's3://{bucket}/album-classifier/data'})
```

## Option 5: AWS CloudShell

Best for: Quick one-time runs without local setup

### Steps

1. Open AWS CloudShell from AWS Console
2. Clone repository:

```bash
git clone https://github.com/your-repo/dsicogs-sage-app.git
cd dsicogs-sage-app/backend/sagemaker
```

3. Install dependencies:

```bash
pip3 install -r requirements.txt --user
```

4. Run pipeline:

```bash
python3 trigger_full_pipeline.py \
  --manifest-path s3://your-bucket/album-classifier/data/releases_manifest_enriched.jsonl
```

## Option 6: Step Functions (Advanced)

Best for: Complex workflows with error handling and retries

### Create Step Functions State Machine

```json
{
  "Comment": "Full Pipeline Training Workflow",
  "StartAt": "TriggerTraining",
  "States": {
    "TriggerTraining": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createTrainingJob.sync",
      "Parameters": {
        "TrainingJobName": "album-classifier-full-$.timestamp",
        "RoleArn": "${SAGEMAKER_ROLE}",
        "AlgorithmSpecification": {
          "TrainingImage": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.1-gpu-py311",
          "TrainingInputMode": "File"
        },
        "InputDataConfig": [{
          "ChannelName": "training",
          "DataSource": {
            "S3DataSource": {
              "S3DataType": "S3Prefix",
              "S3Uri": "s3://${BUCKET_NAME}/album-classifier/data"
            }
          }
        }],
        "OutputDataConfig": {
          "S3OutputPath": "s3://${BUCKET_NAME}/album-classifier/models"
        },
        "ResourceConfig": {
          "InstanceType": "ml.p3.2xlarge",
          "InstanceCount": 1,
          "VolumeSizeInGB": 100
        },
        "StoppingCondition": {
          "MaxRuntimeInSeconds": 172800
        },
        "HyperParameters": {
          "epochs": "10",
          "batch-size": "16",
          "learning-rate": "0.001"
        }
      },
      "Next": "DeployModel"
    },
    "DeployModel": {
      "Type": "Task",
      "Resource": "arn:aws:states:::sagemaker:createModel",
      "Parameters": {
        "ModelName": "album-classifier-$.timestamp",
        "PrimaryContainer": {
          "Image": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.5.1-gpu-py311",
          "ModelDataUrl": "$.ModelArtifacts.S3ModelArtifacts"
        },
        "ExecutionRoleArn": "${SAGEMAKER_ROLE}"
      },
      "End": true
    }
  }
}
```

## Prerequisites for All Options

### 1. Upload Source Code to S3

```bash
cd backend/sagemaker
tar -czf source.tar.gz *.py requirements.txt
aws s3 cp source.tar.gz s3://your-bucket/album-classifier/source/
```

### 2. Upload Manifest to S3

```bash
aws s3 cp data/releases_manifest_enriched.jsonl \
  s3://your-bucket/album-classifier/data/
```

### 3. Configure IAM Permissions

Ensure your execution role has:
- SageMaker full access
- S3 read/write access to your bucket
- CloudWatch Logs write access

## Monitoring

### View Training Jobs

```bash
# List all training jobs
aws sagemaker list-training-jobs \
  --name-contains album-classifier-full \
  --max-results 10

# Get job status
aws sagemaker describe-training-job \
  --training-job-name album-classifier-full-YYYYMMDD-HHMMSS
```

### View Logs

```bash
# CloudWatch Logs
aws logs tail /aws/sagemaker/TrainingJobs/album-classifier-full-* --follow

# Lambda logs
aws logs tail /aws/lambda/trigger-full-pipeline-training --follow
```

### CloudWatch Metrics

View metrics in AWS Console:
- Training job duration
- GPU/CPU utilization
- Model accuracy
- Cost metrics

## Cost Optimization

1. **Use Spot Instances**: Already enabled by default
2. **Right-size Instances**: Use `ml.m5.xlarge` for testing, `ml.p3.2xlarge` for production
3. **Schedule Off-Peak**: Run during off-peak hours
4. **Auto-stop Endpoints**: Delete endpoints when not in use
5. **Use Lambda**: Pay only for execution time

## Troubleshooting

### Common Issues

1. **Source Code Not Found**:
   ```bash
   # Re-upload source code
   cd backend/sagemaker
   tar -czf source.tar.gz *.py requirements.txt
   aws s3 cp source.tar.gz s3://your-bucket/album-classifier/source/
   ```

2. **Permission Denied**:
   - Check IAM role permissions
   - Verify bucket policies
   - Ensure SageMaker role can assume execution role

3. **Timeout Errors**:
   - Increase Lambda timeout (max 15 minutes)
   - Use async invocation for long-running jobs
   - Consider Step Functions for complex workflows

4. **Out of Memory**:
   - Increase instance volume size
   - Reduce batch size
   - Use larger instance types

## Best Practices

1. **Use Infrastructure as Code**: Deploy with CloudFormation or Terraform
2. **Version Control**: Tag S3 objects with versions
3. **Monitoring**: Set up CloudWatch alarms
4. **Cost Tracking**: Use AWS Cost Explorer
5. **Security**: Use least-privilege IAM policies
6. **Backup**: Keep model artifacts in S3 with versioning

## Next Steps

- Set up monitoring and alerting
- Create CI/CD pipeline for automated deployments
- Implement model versioning
- Set up A/B testing for model endpoints


