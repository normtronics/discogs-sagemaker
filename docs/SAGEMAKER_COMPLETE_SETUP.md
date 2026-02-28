# Complete SageMaker Setup Guide: Setup → Train → Deploy → Frontend

This guide walks you through the complete workflow: setting up SageMaker, training a model, deploying it, and making it callable from your frontend via API Gateway + Lambda.

## 📋 Table of Contents

1. [One-time AWS Setup](#1-one-time-aws-setup)
2. [Build + Train the Model](#2-build--train-the-model)
3. [Deploy as an Endpoint](#3-deploy-as-an-endpoint)
4. [Make it Callable from Frontend](#4-make-it-callable-from-frontend)
5. [Implementation Checklist](#5-implementation-checklist)

---

## 1. One-time AWS Setup

### A. Create a SageMaker Studio Domain (Recommended)

SageMaker Studio provides a managed environment for building, training, and deploying models without managing local IAM credentials.

#### Steps:

1. **Go to SageMaker Console**
   - Navigate to: https://console.aws.amazon.com/sagemaker/
   - Select your region (top-right, e.g., `us-east-1`)

2. **Create Domain**
   - Click **Admin configurations** → **Domains** → **Create domain**
   - Choose **Quick setup** (single user) for fastest setup
   - Or choose **Standard setup** for more control

3. **Quick Setup Configuration**
   - **Domain name**: `album-classifier-domain` (or your choice)
   - **Execution role**: Create new role or select existing
   - **VPC**: Use default VPC (or configure custom)
   - Click **Create domain**

4. **Access Studio**
   - Once created, click **Open Studio** next to your domain
   - This opens a JupyterLab-like environment

**Note**: Quick setup automatically creates an execution role with necessary permissions. You can customize it later.

#### Alternative: Use SageMaker Notebook Instances

If you prefer a simpler notebook instance:

1. Go to **Notebook** → **Notebook instances** → **Create notebook instance**
2. Choose instance type (e.g., `ml.t3.medium`)
3. Select or create IAM role
4. Click **Create notebook instance**

### B. IAM Role (Execution Role)

The execution role allows SageMaker to:
- Read training data from S3
- Write model artifacts to S3
- Create hosting resources (endpoints)
- Write CloudWatch logs

#### If Quick Setup Created the Role:

The role is automatically configured. You can find it:
- In **IAM Console** → **Roles**
- Look for role like: `AmazonSageMaker-ExecutionRole-YYYYMMDD-HHMMSS`

#### If Creating Your Own Role:

1. **Go to IAM Console**
   - Navigate to: https://console.aws.amazon.com/iam/
   - Click **Roles** → **Create role**

2. **Trust Entity**
   - Select **AWS service**
   - Choose **SageMaker**

3. **Attach Policies**
   - **Required**: `AmazonSageMakerFullAccess`
   - **Custom S3 Policy** (see below)

4. **Custom S3 Policy** (attach as inline policy):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::your-ml-bucket/*",
        "arn:aws:s3:::your-ml-bucket"
      ]
    }
  ]
}
```

Replace `your-ml-bucket` with your actual bucket name.

5. **Name the Role**
   - Role name: `DiscogsSageMakerExecutionRole` (or your choice)
   - Click **Create role**

6. **Note the Role ARN**
   - You'll need this later (format: `arn:aws:iam::ACCOUNT_ID:role/ROLE_NAME`)

### C. S3 Buckets

Create (or reuse) S3 locations for:
- Training data: `s3://your-ml-bucket/data/`
- Model artifacts: `s3://your-ml-bucket/models/`
- Source code: `s3://your-ml-bucket/code/`

#### Steps:

1. **Go to S3 Console**
   - Navigate to: https://console.aws.amazon.com/s3/
   - Click **Create bucket**

2. **Bucket Configuration**
   - **Bucket name**: `album-classifier-ml-bucket` (must be globally unique)
   - **Region**: Same as your SageMaker region
   - **Block Public Access**: Keep enabled (recommended)
   - Click **Create bucket**

3. **Create Folders** (optional, S3 doesn't have real folders, but prefixes help organize)

   ```bash
   # Using AWS CLI
   aws s3 mkdir s3://your-ml-bucket/data/
   aws s3 mkdir s3://your-ml-bucket/models/
   aws s3 mkdir s3://your-ml-bucket/code/
   ```

   Or create them via console by uploading a dummy file to each prefix.

4. **Upload Training Data**

   ```bash
   # Upload manifest file
   aws s3 cp data/releases_manifest_enriched.jsonl \
     s3://your-ml-bucket/data/releases_manifest_enriched.jsonl
   
   # Upload images (if you have them locally)
   aws s3 sync backend/data/images/ \
     s3://your-ml-bucket/data/images/
   ```

---

## 2. Build + Train the Model

You have two approaches:

### Option 1: Use Built-in Algorithm/Container (Fastest Start)

AWS provides pre-built containers for common frameworks. For PyTorch:

1. **In SageMaker Studio**, create a new notebook
2. **Use SageMaker SDK**:

```python
from sagemaker.pytorch import PyTorch
import sagemaker

# Get execution role (automatically detected in Studio)
role = sagemaker.get_execution_role()

# Create estimator
estimator = PyTorch(
    entry_point='train.py',
    source_dir='s3://your-ml-bucket/code/sourcedir.tar.gz',  # Or local path
    role=role,
    instance_type='ml.p3.2xlarge',  # GPU instance
    instance_count=1,
    framework_version='2.5.0',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
    },
    output_path='s3://your-ml-bucket/models/',
)

# Start training
estimator.fit({'training': 's3://your-ml-bucket/data/'})
```

### Option 2: Bring Your Own Training Code (Recommended)

This is what you already have in `backend/sagemaker/train.py`.

#### Step 1: Package Training Code

```bash
cd backend/sagemaker
tar -czf sourcedir.tar.gz train.py inference.py requirements.txt

# Upload to S3
aws s3 cp sourcedir.tar.gz s3://your-ml-bucket/code/sourcedir.tar.gz
```

#### Step 2: Launch Training Job

**From SageMaker Studio Notebook:**

```python
from sagemaker.pytorch import PyTorch
import sagemaker

# Get execution role
role = sagemaker.get_execution_role()

# Create estimator
estimator = PyTorch(
    entry_point='train.py',
    source_dir='s3://your-ml-bucket/code/sourcedir.tar.gz',
    role=role,
    instance_type='ml.p3.2xlarge',  # Or ml.m5.xlarge for CPU (cheaper)
    instance_count=1,
    framework_version='2.5.0',
    py_version='py311',
    hyperparameters={
        'epochs': '10',
        'batch-size': '16',
        'learning-rate': '0.001',
    },
    output_path='s3://your-ml-bucket/models/',
    max_run=86400,  # 24 hours max
)

# Start training
estimator.fit({'training': 's3://your-ml-bucket/data/'})

# After training completes
print(f"Model artifacts: {estimator.model_data}")
print(f"Job name: {estimator.latest_training_job.name}")
```

**From AWS CLI:**

```bash
aws sagemaker create-training-job \
  --training-job-name album-classifier-training-$(date +%s) \
  --role-arn arn:aws:iam::ACCOUNT_ID:role/DiscogsSageMakerExecutionRole \
  --algorithm-specification '{
    "TrainingInputMode": "File",
    "TrainingImage": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-cpu-py311"
  }' \
  --input-data-config '[{
    "ChannelName": "training",
    "DataSource": {
      "S3DataSource": {
        "S3DataType": "S3Prefix",
        "S3Uri": "s3://your-ml-bucket/data/",
        "S3DataDistributionType": "FullyReplicated"
      }
    }
  }]' \
  --output-data-config '{
    "S3OutputPath": "s3://your-ml-bucket/models/"
  }' \
  --resource-config '{
    "InstanceType": "ml.p3.2xlarge",
    "InstanceCount": 1,
    "VolumeSizeInGB": 50
  }' \
  --stopping-condition '{
    "MaxRuntimeInSeconds": 86400
  }'
```

#### Step 3: Monitor Training

**In SageMaker Console:**
1. Go to **Training** → **Training jobs**
2. Click on your job name
3. View **Monitor** tab for metrics
4. Click **View logs** for CloudWatch logs

**In Notebook:**

```python
# Stream logs
from sagemaker.logs import TrainingLogs

logs = TrainingLogs(sagemaker_session, estimator.latest_training_job.name)
logs.stream()
```

#### Step 4: Check Output

Once training completes:

1. **Model artifacts** are saved to: `s3://your-ml-bucket/models/JOB_NAME/output/model.tar.gz`
2. **Note the path** - you'll need it for deployment

```bash
# List model artifacts
aws s3 ls s3://your-ml-bucket/models/album-classifier-training-*/output/
```

---

## 3. Deploy as an Endpoint

SageMaker supports multiple inference modes. For a frontend-backed API, use:

### Option A: Real-time Endpoint (Recommended for Production)

Always-on instances, best for steady traffic and low latency.

#### Step 1: Create Model

**From SageMaker Console:**

1. Go to **Inference** → **Models** → **Create model**
2. **Model settings**:
   - **Model name**: `album-classifier-model-v1`
   - **IAM role**: Your SageMaker execution role
3. **Container definition**:
   - **Inference code location**: Provide model artifacts and image location
   - **Model artifacts**: `s3://your-ml-bucket/models/JOB_NAME/output/model.tar.gz`
   - **Inference image**: `763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-inference:2.5.0-cpu-py311`
4. Click **Create model**

**From Notebook:**

```python
from sagemaker.pytorch import PyTorchModel

# Create model
model = PyTorchModel(
    model_data=estimator.model_data,  # From training job
    role=role,
    entry_point='inference.py',
    framework_version='2.5.0',
    py_version='py311',
)

# Deploy endpoint
predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',  # Cheaper: ml.t2.medium, Recommended: ml.m5.large
    endpoint_name='album-classifier'
)
```

#### Step 2: Create Endpoint Configuration

**From Console:**

1. Go to **Inference** → **Endpoint configurations** → **Create endpoint configuration**
2. **Configuration**:
   - **Name**: `album-classifier-config-v1`
   - **Add model**: Select `album-classifier-model-v1`
3. **Production variants**:
   - **Variant name**: `AllTraffic`
   - **Instance type**: `ml.m5.large` (or `ml.t2.medium` for cheaper)
   - **Initial instance count**: 1
   - **Initial variant weight**: 1
4. Click **Create endpoint configuration**

#### Step 3: Create Endpoint

**From Console:**

1. Go to **Inference** → **Endpoints** → **Create endpoint**
2. **Endpoint settings**:
   - **Endpoint name**: `album-classifier`
   - **Attach endpoint configuration**: Select `album-classifier-config-v1`
3. Click **Create endpoint**

**Deployment takes**: 5-10 minutes

**From Notebook:**

```python
# Already done if you used model.deploy() above
# Otherwise:
predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',
    endpoint_name='album-classifier'
)
```

#### Step 4: Test Endpoint

**From Console:**

1. Click on endpoint name
2. Go to **Test inference** tab
3. Upload test image or provide JSON

**From CLI:**

```bash
# Prepare test image
base64 backend/data/images/0.jpg > test_image.txt

# Invoke endpoint
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name album-classifier \
  --content-type image/jpeg \
  --body fileb://backend/data/images/0.jpg \
  output.json

# View results
cat output.json
```

**From Python:**

```python
# Using predictor from deployment
with open('test_image.jpg', 'rb') as f:
    response = predictor.predict(f.read(), initial_args={'ContentType': 'image/jpeg'})
print(response)
```

### Option B: Serverless Inference (For Spiky Traffic)

Scales to zero, cheaper for intermittent use, but has cold starts.

**From Notebook:**

```python
from sagemaker.serverless import ServerlessInferenceConfig

# Deploy as serverless
predictor = model.deploy(
    serverless_inference_config=ServerlessInferenceConfig(
        memory_size_in_mb=2048,
        max_concurrency=10,
    ),
    endpoint_name='album-classifier-serverless'
)
```

**From Console:**

1. When creating endpoint configuration, select **Serverless** instead of **Real-time**
2. Configure memory (1024-10240 MB) and max concurrency

---

## 4. Make it Callable from Frontend

**Important**: Don't call SageMaker directly from the browser. Use API Gateway → Lambda → SageMaker Runtime.

### Architecture

```
Frontend (Browser)
    ↓ HTTP POST
API Gateway
    ↓ Invoke
Lambda Function
    ↓ InvokeEndpoint
SageMaker Runtime
    ↓ Response
Lambda
    ↓ JSON Response
API Gateway
    ↓ JSON
Frontend
```

### Step 1: Deploy Infrastructure (CDK)

We've created infrastructure code for you. Deploy it:

```bash
cd infrastructure

# Install dependencies
npm install

# Deploy inference stack
npm run deploy -- \
  --context endpointName=album-classifier \
  --context sagemakerRoleArn=arn:aws:iam::ACCOUNT_ID:role/DiscogsSageMakerExecutionRole
```

This creates:
- **Lambda function** with `sagemaker:InvokeEndpoint` permission
- **API Gateway** REST API
- **CORS** enabled for your frontend origin
- **Integration** between API Gateway and Lambda

### Step 2: Get API Gateway URL

After deployment, CDK outputs the API Gateway URL:

```bash
# Get stack outputs
aws cloudformation describe-stacks \
  --stack-name InferenceStack \
  --query 'Stacks[0].Outputs'
```

Or check the CDK output in your terminal after deployment.

The URL will look like:
```
https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict
```

### Step 3: Update Frontend

Update your frontend to call the API Gateway URL instead of SageMaker directly:

**In `frontend/.env.local`:**

```bash
NEXT_PUBLIC_API_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict
```

**In your frontend code:**

```typescript
// Already configured in src/app/page.tsx
const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api/predict';

// Make request
const formData = new FormData();
formData.append('file', imageFile);

const response = await fetch(apiUrl, {
  method: 'POST',
  body: formData,
});

const data = await response.json();
```

### Step 4: Test End-to-End

1. **Start frontend**:
   ```bash
   cd frontend
   npm run dev
   ```

2. **Upload an image** via the UI

3. **Check CloudWatch logs**:
   ```bash
   # Lambda logs
   aws logs tail /aws/lambda/InferenceStack-PredictFunction-XXXXX --follow
   ```

---

## 5. Implementation Checklist

### SageMaker Side ✅

- [ ] SageMaker Studio domain created (or Notebook instance)
- [ ] Execution role can access S3 + SageMaker actions
- [ ] S3 buckets created (data, models, code)
- [ ] Training data uploaded to S3
- [ ] Training code packaged and uploaded
- [ ] Training job completed successfully
- [ ] Model artifacts saved to S3
- [ ] Model deployed to Real-time or Serverless endpoint
- [ ] Endpoint status shows "InService"
- [ ] Test invoke from Studio/CLI successful

### API Layer ✅

- [ ] Lambda execution role has `sagemaker:InvokeEndpoint` permission
- [ ] Lambda function deployed (via CDK)
- [ ] API Gateway route created (`/predict`)
- [ ] API Gateway → Lambda integration configured
- [ ] CORS enabled for frontend origin(s)
- [ ] API Gateway URL noted
- [ ] Test invoke from API Gateway successful

### Frontend ✅

- [ ] Environment variable set: `NEXT_PUBLIC_API_URL`
- [ ] Frontend calls API Gateway URL (not SageMaker)
- [ ] CORS headers received correctly
- [ ] Image upload works
- [ ] Predictions displayed correctly

### Optional Enhancements ✅

- [ ] **Auth added**: Cognito authorizer or JWT authorizer
- [ ] **Rate limiting**: Configured in API Gateway
- [ ] **Input validation**: Added in Lambda
- [ ] **Error handling**: Proper error responses
- [ ] **Logging**: CloudWatch logs configured
- [ ] **Monitoring**: CloudWatch dashboards created

---

## 🎯 Quick Reference

### Console URLs

- **SageMaker**: https://console.aws.amazon.com/sagemaker/
- **S3**: https://console.aws.amazon.com/s3/
- **IAM**: https://console.aws.amazon.com/iam/
- **API Gateway**: https://console.aws.amazon.com/apigateway/
- **Lambda**: https://console.aws.amazon.com/lambda/
- **CloudWatch**: https://console.aws.amazon.com/cloudwatch/

### Common Commands

```bash
# List training jobs
aws sagemaker list-training-jobs --max-results 10

# Describe endpoint
aws sagemaker describe-endpoint --endpoint-name album-classifier

# Invoke endpoint via API Gateway
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/predict \
  -F "file=@test_image.jpg"

# View Lambda logs
aws logs tail /aws/lambda/InferenceStack-PredictFunction-XXXXX --follow
```

### Cost Estimates

- **Training**: `ml.p3.2xlarge` ≈ $3.06/hour (GPU)
- **Training**: `ml.m5.xlarge` ≈ $0.23/hour (CPU)
- **Endpoint**: `ml.m5.large` ≈ $0.115/hour (always-on)
- **Endpoint**: `ml.t2.medium` ≈ $0.047/hour (cheapest)
- **Serverless**: Pay per invocation + compute time

**Tip**: Delete endpoints when not in use to save costs.

---

## 🚀 Next Steps

1. ✅ Complete setup checklist above
2. ✅ Test end-to-end workflow
3. ✅ Monitor costs in AWS Cost Explorer
4. ✅ Set up CloudWatch alarms for errors
5. ✅ Consider adding authentication (Cognito)
6. ✅ Set up CI/CD for automated deployments

---

## 📚 Additional Resources

- [SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [API Gateway + Lambda Integration](https://docs.aws.amazon.com/apigateway/latest/developerguide/getting-started-with-lambda.html)
- [SageMaker Pricing](https://aws.amazon.com/sagemaker/pricing/)
- [CDK Documentation](https://docs.aws.amazon.com/cdk/)

---

## ❓ Troubleshooting

### Training Job Fails

1. Check CloudWatch logs
2. Verify S3 paths are correct
3. Ensure IAM role has S3 permissions
4. Check instance type availability in region

### Endpoint Creation Fails

1. Verify model artifacts exist in S3
2. Check IAM role permissions
3. Ensure instance type is available
4. Review CloudWatch logs

### API Gateway Returns 500

1. Check Lambda logs
2. Verify Lambda has `sagemaker:InvokeEndpoint` permission
3. Ensure endpoint name is correct
4. Check CORS configuration

### Frontend CORS Error

1. Verify API Gateway CORS is enabled
2. Check `Access-Control-Allow-Origin` header
3. Ensure frontend origin is whitelisted

---

**Questions?** Check the other guides in this project or AWS documentation!
