# SageMaker Quick Start: Setup → Train → Deploy → Frontend

This is a condensed quick-start guide. For detailed instructions, see [SAGEMAKER_COMPLETE_SETUP.md](./SAGEMAKER_COMPLETE_SETUP.md).

## 🚀 Quick Start (5 Steps)

### 1. One-time AWS Setup

```bash
# Create SageMaker Studio domain (via console)
# https://console.aws.amazon.com/sagemaker/
# Admin configurations → Domains → Create domain → Quick setup

# Create S3 bucket
aws s3 mb s3://your-ml-bucket

# Upload training data
aws s3 cp data/releases_manifest_enriched.jsonl s3://your-ml-bucket/data/
aws s3 sync backend/data/images/ s3://your-ml-bucket/data/images/
```

### 2. Train Model

**Option A: From SageMaker Studio Notebook**

```python
from sagemaker.pytorch import PyTorch
import sagemaker

role = sagemaker.get_execution_role()

estimator = PyTorch(
    entry_point='train.py',
    source_dir='s3://your-ml-bucket/code/sourcedir.tar.gz',
    role=role,
    instance_type='ml.p3.2xlarge',
    framework_version='2.5.0',
    py_version='py311',
    output_path='s3://your-ml-bucket/models/',
)

estimator.fit({'training': 's3://your-ml-bucket/data/'})
```

**Option B: Package and Upload Code First**

```bash
cd backend/sagemaker
tar -czf sourcedir.tar.gz train.py inference.py requirements.txt
aws s3 cp sourcedir.tar.gz s3://your-ml-bucket/code/
```

### 3. Deploy Endpoint

```python
# In SageMaker Studio notebook
from sagemaker.pytorch import PyTorchModel

model = PyTorchModel(
    model_data=estimator.model_data,
    role=role,
    entry_point='inference.py',
    framework_version='2.5.0',
    py_version='py311',
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',
    endpoint_name='album-classifier'
)
```

### 4. Deploy API Gateway + Lambda

```bash
cd infrastructure
npm install
npm run deploy -- --context endpointName=album-classifier
```

**Get API Gateway URL:**

```bash
aws cloudformation describe-stacks \
  --stack-name InferenceStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayPredictUrl`].OutputValue' \
  --output text
```

### 5. Configure Frontend

**Create `frontend/.env.local`:**

```bash
NEXT_PUBLIC_API_URL=https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/predict
```

**Start frontend:**

```bash
cd frontend
npm run dev
```

## 📋 Checklist

- [ ] SageMaker Studio domain created
- [ ] S3 bucket created and data uploaded
- [ ] Training code packaged and uploaded
- [ ] Training job completed
- [ ] Model deployed to endpoint (status: InService)
- [ ] API Gateway + Lambda deployed
- [ ] Frontend configured with API Gateway URL
- [ ] Test end-to-end workflow

## 🔧 Common Commands

```bash
# List training jobs
aws sagemaker list-training-jobs --max-results 10

# Check endpoint status
aws sagemaker describe-endpoint --endpoint-name album-classifier

# Test endpoint
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name album-classifier \
  --content-type image/jpeg \
  --body fileb://test_image.jpg \
  output.json

# View Lambda logs
aws logs tail /aws/lambda/InferenceStack-PredictFunction-XXXXX --follow

# Test API Gateway
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/predict \
  -H "Content-Type: application/json" \
  -d '{"image": "'$(base64 -i test.jpg)'", "content_type": "image/jpeg"}'
```

## 💰 Cost Estimates

- **Training**: `ml.p3.2xlarge` ≈ $3.06/hour (GPU)
- **Training**: `ml.m5.xlarge` ≈ $0.23/hour (CPU)
- **Endpoint**: `ml.m5.large` ≈ $0.115/hour
- **Serverless**: Pay per invocation

**Tip**: Delete endpoints when not in use!

## 🐛 Troubleshooting

### Training Job Fails
- Check CloudWatch logs
- Verify S3 paths
- Check IAM permissions

### Endpoint Not Working
- Verify status is "InService"
- Check Lambda logs
- Verify endpoint name matches

### CORS Errors
- Check API Gateway CORS settings
- Verify frontend origin

## 📚 Full Documentation

- [Complete Setup Guide](./SAGEMAKER_COMPLETE_SETUP.md) - Detailed step-by-step
- [Console Guide](./SAGEMAKER_CONSOLE_GUIDE.md) - Using AWS Console
- [Deploy Inference](./infrastructure/DEPLOY_INFERENCE.md) - API Gateway setup
- [Frontend Setup](./frontend/FRONTEND_API_GATEWAY_SETUP.md) - Frontend configuration

## 🎯 Architecture

```
Frontend (Browser)
    ↓ HTTP POST
API Gateway
    ↓ Invoke
Lambda Function
    ↓ InvokeEndpoint
SageMaker Runtime
    ↓ Predictions
Lambda
    ↓ JSON Response
API Gateway
    ↓ JSON
Frontend
```

---

**Ready to go?** Start with Step 1 and work through each step. For detailed instructions, see [SAGEMAKER_COMPLETE_SETUP.md](./SAGEMAKER_COMPLETE_SETUP.md).
