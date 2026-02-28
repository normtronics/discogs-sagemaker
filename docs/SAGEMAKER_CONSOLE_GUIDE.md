# SageMaker UI Console Setup Guide

Complete guide for setting up your album classifier using the AWS SageMaker Console instead of CLI/scripts.

## 📋 Prerequisites

Before starting in the console:

1. ✅ Upload data to S3 (still need CLI for this):
   ```bash
   cd backend
   python sagemaker/upload_data_s3.py
   ```

2. ✅ Package your training code:
   ```bash
   cd backend/sagemaker
   tar -czf sourcedir.tar.gz train.py inference.py
   
   # Upload to S3
   aws s3 cp sourcedir.tar.gz s3://your-bucket/album-classifier/code/
   ```

## 🎯 Part 1: Training Job via Console

### Step 1: Open SageMaker Console

1. Go to https://console.aws.amazon.com/sagemaker/
2. Select your region (top-right, e.g., `us-east-1`)
3. Click **Training** → **Training jobs** in left sidebar

### Step 2: Create Training Job

Click **Create training job** button

#### **Job Settings**
- **Job name**: `album-classifier-training-001`
- **IAM role**: Select your SageMaker role
  - Or create new: `DiscogsSageSageMakerRole`

#### **Algorithm Source**
- Select: **Built-in algorithm**
- Then change to: **Your own algorithm container in ECR**
- **OR** use: **Script mode** (easier)

#### **Script Mode Setup** (Recommended)
1. **Framework**: PyTorch
2. **Framework version**: 2.5.0
3. **Python version**: py311
4. **Script location**: 
   - **S3 URI**: `s3://your-bucket/album-classifier/code/sourcedir.tar.gz`
   - **Entry point**: `train.py`

#### **Resource Configuration**
- **Instance type**: `ml.p3.2xlarge` (GPU, faster) or `ml.m5.xlarge` (CPU, cheaper)
- **Instance count**: 1
- **Volume size**: 50 GB

#### **Input Data Configuration**

Click **Add channel**:
- **Channel name**: `training`
- **S3 location**: `s3://your-bucket/album-classifier/data/`
- **Content type**: Leave empty
- **Compression type**: None
- **Record wrapper**: None
- **S3 data type**: S3Prefix
- **S3 data distribution type**: FullyReplicated

#### **Output Data Configuration**
- **S3 location**: `s3://your-bucket/album-classifier/models/`

#### **Hyperparameters** (Optional)

Click **Add hyperparameter**:
```
epochs = 10
batch-size = 16
learning-rate = 0.001
lr-step-size = 5
lr-gamma = 0.1
```

#### **Checkpoint Configuration** (Optional)
- **S3 location**: `s3://your-bucket/album-classifier/checkpoints/`

#### **Stopping Condition**
- **Max runtime**: 86400 seconds (24 hours)

### Step 3: Monitor Training

1. Click on your job name to view details
2. Watch **Status**: InProgress → Completed
3. View logs: Click **View logs** → Goes to CloudWatch
4. Check metrics: **Monitor** tab shows training metrics

**Training takes**: 10-30 minutes depending on instance type

### Step 4: Check Output

Once complete:
1. Go to **S3** console
2. Navigate to: `s3://your-bucket/album-classifier/models/`
3. Find: `album-classifier-training-001/output/model.tar.gz`
4. Note this path - you'll need it for deployment!

---

## 🚀 Part 2: Deploy Model Endpoint via Console

### Step 1: Create Model

1. In SageMaker console, go to **Inference** → **Models**
2. Click **Create model**

#### **Model Settings**
- **Model name**: `album-classifier-model-v1`
- **IAM role**: Same SageMaker role as training

#### **Container Definition**
- **Container input**: Provide model artifacts and image location
- **Location of inference code**: Same as training
  - **Image**: (auto-selected for PyTorch 2.5.0)
  - **Model artifacts**: `s3://your-bucket/album-classifier/models/album-classifier-training-001/output/model.tar.gz`

Click **Create model**

### Step 2: Create Endpoint Configuration

1. Go to **Inference** → **Endpoint configurations**
2. Click **Create endpoint configuration**

#### **Configuration**
- **Name**: `album-classifier-config-v1`
- **Add model**: Select `album-classifier-model-v1`

#### **Production Variants**
- **Variant name**: `AllTraffic`
- **Instance type**: 
  - `ml.t2.medium` - Cheapest ($0.047/hr)
  - `ml.m5.large` - Recommended ($0.115/hr)
  - `ml.m5.xlarge` - Faster ($0.23/hr)
- **Initial instance count**: 1
- **Initial variant weight**: 1

#### **Data Capture** (Optional but recommended)
- Enable: ✓
- **Sampling percentage**: 100
- **S3 URI**: `s3://your-bucket/album-classifier/data-capture/`

Click **Create endpoint configuration**

### Step 3: Create Endpoint

1. Go to **Inference** → **Endpoints**
2. Click **Create endpoint**

#### **Endpoint Settings**
- **Endpoint name**: `album-classifier`
- **Attach endpoint configuration**: Select `album-classifier-config-v1`

Click **Create endpoint**

**Deployment takes**: 5-10 minutes

### Step 4: Test Endpoint

Once status shows **InService**:

#### Via Console (JSON Test)
1. Click on endpoint name
2. Go to **Test inference** tab
3. Upload test image or provide JSON:
   ```json
   {
     "image": "base64_encoded_image_data_here"
   }
   ```

#### Via AWS CLI
```bash
# Prepare test image
base64 test_album.jpg > test_image.txt

# Invoke endpoint
aws sagemaker-runtime invoke-endpoint \
  --endpoint-name album-classifier \
  --content-type image/jpeg \
  --body fileb://test_album.jpg \
  output.json

# View results
cat output.json
```

#### Via Python Script
```bash
cd backend
python sagemaker/test_endpoint.py \
  --endpoint album-classifier \
  --image data/images/0.jpg
```

---

## 🔄 Part 3: Automated Retraining via Console

### Option A: Manual Retraining

1. Go to **Training** → **Training jobs**
2. Select your completed job
3. Click **Clone** button
4. Modify settings if needed
5. Click **Create training job**

### Option B: Scheduled Training (EventBridge)

#### Step 1: Create EventBridge Rule

1. Go to **Amazon EventBridge** console
2. Click **Rules** → **Create rule**

**Rule Details**:
- **Name**: `album-classifier-weekly-training`
- **Description**: Train model every Monday at 2 AM
- **Event bus**: default
- **Rule type**: Schedule

**Schedule Pattern**:
- **Schedule type**: Cron-based schedule
- **Cron expression**: `0 2 ? * MON *`
  - This means: Every Monday at 2:00 AM UTC

**Target**:
- **Target type**: AWS service
- **Select target**: SageMaker Pipeline
- **Pipeline**: (need to create pipeline first)

#### Step 2: Create Lambda for Triggering (Alternative)

If you want Lambda to trigger training:

1. Create Lambda function (see `backend/aws/lambda_trigger_training.py`)
2. In EventBridge, select target as Lambda
3. Lambda will call SageMaker API to start training job

---

## 📊 Part 4: Monitoring via Console

### View Training Progress

**During Training**:
1. **Training jobs** → Click job name
2. **Monitor** tab:
   - Training metrics graphs
   - CPU/GPU utilization
   - Memory usage
3. **View logs** → CloudWatch logs

### Monitor Endpoint

**After Deployment**:
1. **Endpoints** → Click endpoint name
2. **Monitor** tab shows:
   - Invocations per minute
   - Model latency
   - Error rates
   - CPU/memory utilization

### CloudWatch Dashboards

1. Go to **CloudWatch** console
2. **Dashboards** → **Create dashboard**
3. Add widgets:
   - **ModelInvocations**: Track usage
   - **ModelLatency**: Track performance
   - **Invocation4XXErrors**: Track errors

---

## 💰 Part 5: Cost Management via Console

### View Current Costs

1. Go to **AWS Cost Explorer**
2. Filter by:
   - Service: Amazon SageMaker
   - Time range: Last 7 days
3. Group by: Usage Type

### Set Budget Alerts

1. Go to **AWS Budgets**
2. **Create budget**
3. **Budget type**: Cost budget
4. **Amount**: $100/month
5. **Alert threshold**: 80% of budget
6. **Email**: your-email@example.com

### Stop Endpoint to Save Costs

**When not using**:
1. Go to **Endpoints**
2. Select endpoint
3. Click **Delete**
4. Confirm

**Redeploy later**:
1. **Endpoints** → **Create endpoint**
2. Use same configuration
3. Takes 5-10 minutes

---

## 🎛️ Part 6: Auto-Scaling via Console

For production workloads with variable traffic:

### Configure Auto-Scaling

1. Go to **Endpoints** → Click your endpoint
2. **Endpoint runtime settings** tab
3. Under **Variants**, click on variant
4. **Configure auto scaling**

#### Auto-Scaling Settings:
- **Minimum instances**: 1
- **Maximum instances**: 3
- **Target value**: 70 (invocations per instance)
- **Scale-in cooldown**: 300 seconds
- **Scale-out cooldown**: 60 seconds

**Scaling Policy**:
- **Metric**: `SageMakerVariantInvocationsPerInstance`
- **Target value**: 1000 (adjust based on your needs)

---

## 🔐 Part 7: Security Setup via Console

### Create IAM Role

1. Go to **IAM** console
2. **Roles** → **Create role**
3. **Trusted entity**: SageMaker
4. **Permissions policies**:
   - `AmazonSageMakerFullAccess`
   - Custom S3 policy for your bucket

#### Custom S3 Policy:
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
        "arn:aws:s3:::your-bucket/*",
        "arn:aws:s3:::your-bucket"
      ]
    }
  ]
}
```

### Enable Encryption

**For Endpoints**:
1. When creating endpoint configuration
2. **Encryption** section
3. **KMS key**: Select key or use default

**For S3**:
1. Go to S3 bucket
2. **Properties** → **Default encryption**
3. Enable with AWS managed keys (SSE-S3)

---

## 📝 Quick Reference: Console URLs

### Direct Console Links

```
SageMaker Home:
https://console.aws.amazon.com/sagemaker/

Training Jobs:
https://console.aws.amazon.com/sagemaker/home#/jobs

Endpoints:
https://console.aws.amazon.com/sagemaker/home#/endpoints

Models:
https://console.aws.amazon.com/sagemaker/home#/models

S3 Buckets:
https://console.aws.amazon.com/s3/

CloudWatch Logs:
https://console.aws.amazon.com/cloudwatch/home#logs

EventBridge Rules:
https://console.aws.amazon.com/events/home#/rules

Cost Explorer:
https://console.aws.amazon.com/cost-management/home
```

---

## 🎓 Console vs CLI/Scripts

| Task | Console | Scripts | Recommendation |
|------|---------|---------|----------------|
| **First time setup** | ✅ Easier to learn | ⚠️ Steeper learning curve | Console |
| **Repeated training** | ⚠️ Manual clicks | ✅ One command | Scripts |
| **Experimentation** | ⚠️ Tedious | ✅ Quick iteration | Scripts |
| **Production** | ⚠️ Hard to automate | ✅ CI/CD ready | Scripts |
| **Monitoring** | ✅ Great visualizations | ⚠️ Need CloudWatch | Console |
| **Cost tracking** | ✅ Built-in dashboards | ⚠️ Need setup | Console |

## 🚀 Recommended Workflow

1. **First Training**: Use Console (learn the process)
2. **Experimentation**: Use Scripts (iterate quickly)
3. **Monitoring**: Use Console (better visualization)
4. **Production**: Use Scripts + EventBridge (automation)

---

## 🔧 Troubleshooting Console Issues

### Training Job Fails

1. **Check logs**: Training jobs → Job name → View logs
2. **Common issues**:
   - IAM role permissions
   - S3 path incorrect
   - Code errors in train.py

### Endpoint Creation Fails

1. **Check**: Model artifacts exist in S3
2. **Verify**: IAM role has S3 read permissions
3. **Check**: Instance type available in your region

### Can't Invoke Endpoint

1. **Status**: Must show "InService"
2. **Wait**: 5-10 minutes after creation
3. **IAM**: Ensure you have `sagemaker:InvokeEndpoint` permission

---

## 📚 Additional Resources

- [SageMaker Console Guide](https://docs.aws.amazon.com/sagemaker/latest/dg/gs-console.html)
- [Training Jobs Documentation](https://docs.aws.amazon.com/sagemaker/latest/dg/how-it-works-training.html)
- [Endpoint Deployment](https://docs.aws.amazon.com/sagemaker/latest/dg/how-it-works-deployment.html)
- [SageMaker Pricing](https://aws.amazon.com/sagemaker/pricing/)

---

## 🎯 Next Steps

After console setup:
1. ✅ Train first model via console
2. ✅ Deploy endpoint and test
3. ✅ Set up monitoring dashboard
4. ✅ Configure budget alerts
5. 🔄 Consider scripting for automation

**Questions?** Check the [AWS SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/) or the other guides in this project!

