# AWS Setup Guide

Complete AWS setup for SageMaker deployment.

## Prerequisites

- AWS Account
- AWS CLI installed and configured
- Python 3.9+ with virtual environment

## Step 1: Configure AWS CLI

### If You Have Multiple AWS Accounts

See **[AWS_CREDENTIALS.md](AWS_CREDENTIALS.md)** for detailed guide on managing multiple accounts.

Quick setup:

```bash
# Configure with a profile name (recommended for multiple accounts)
aws configure --profile discogs-dev

# Enter your credentials:
#   AWS Access Key ID: [Get from IAM Console → Users → Security credentials]
#   AWS Secret Access Key: [From same place]
#   Default region: us-east-1
#   Default output format: json

# Set this as your active profile
export AWS_PROFILE=discogs-dev

# Verify which account you're using
aws sts get-caller-identity
# This shows your Account ID - verify it's the right one!
```

### Single AWS Account

```bash
# Configure default profile
aws configure

# Verify
aws sts get-caller-identity
```

**Where to get credentials**: 
1. Sign in to [AWS Console](https://console.aws.amazon.com/) (correct account!)
2. Go to IAM → Users → [Your User] → Security credentials
3. Click "Create access key" → Select "Command Line Interface"
4. Copy Access Key ID and Secret Access Key (can't view secret again!)

## Step 2: Create S3 Bucket

```bash
# Set your bucket name
export BUCKET_NAME="discogs-sage-sagemaker"
export AWS_REGION="us-east-1"

# Create bucket
aws s3 mb s3://${BUCKET_NAME} --region ${AWS_REGION}

# Enable versioning (recommended)
aws s3api put-bucket-versioning \
  --bucket ${BUCKET_NAME} \
  --versioning-configuration Status=Enabled

# Enable encryption
aws s3api put-bucket-encryption \
  --bucket ${BUCKET_NAME} \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

## Step 3: Create SageMaker IAM Role

```bash
# Create trust policy file
cat > trust-policy.json << EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "sagemaker.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF

# Create the role
aws iam create-role \
  --role-name DiscogsSageSageMakerRole \
  --assume-role-policy-document file://trust-policy.json

# Attach SageMaker execution policy
aws iam attach-role-policy \
  --role-name DiscogsSageSageMakerRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonSageMakerFullAccess

# Create and attach S3 access policy
cat > s3-policy.json << EOF
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
        "arn:aws:s3:::${BUCKET_NAME}/*",
        "arn:aws:s3:::${BUCKET_NAME}"
      ]
    }
  ]
}
EOF

aws iam put-role-policy \
  --role-name DiscogsSageSageMakerRole \
  --policy-name S3AccessPolicy \
  --policy-document file://s3-policy.json

# Get the role ARN (save this!)
aws iam get-role --role-name DiscogsSageSageMakerRole --query 'Role.Arn' --output text

# Clean up temp files
rm trust-policy.json s3-policy.json
```

## Step 4: Configure Environment

Create or update `backend/.env.local`:

```bash
# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=discogs-dev    # ← Use the profile you created in Step 1

# SageMaker Configuration
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT_ID:role/DiscogsSageSageMakerRole
BUCKET_NAME=discogs-sage-sagemaker

# Discogs API (if needed)
DISCOGS_CONSUMER_KEY=your_key
DISCOGS_CONSUMER_SECRET=your_secret
```

**Finding YOUR_ACCOUNT_ID**:
```bash
# Get your AWS Account ID
aws sts get-caller-identity --query Account --output text
# Returns: 123456789012

# Then replace in the SAGEMAKER_ROLE above
```

**Multiple Accounts?** Create separate env files:
- `backend/.env.dev` (development account)
- `backend/.env.prod` (production account)
- Copy the one you need to `backend/.env.local`

See [AWS_CREDENTIALS.md](AWS_CREDENTIALS.md) for details.

## Step 5: Install Dependencies

```bash
# Activate virtual environment
cd backend
source venv/bin/activate

# Install SageMaker dependencies
pip install -r ../sagemaker/requirements.txt
```

## Step 6: Download Training Data

```bash
# Start backend API
cd backend
python main.py &

# Wait for API to start, then download images
sleep 5
curl -X POST http://localhost:8000/api/download-images

# Stop backend
pkill -f "python main.py"
```

## Step 7: Upload Data to S3

```bash
# Upload training data
python sagemaker/upload_data_s3.py

# Verify upload
aws s3 ls s3://${BUCKET_NAME}/album-classifier/data/ --recursive
```

Expected output:
```
releases_manifest_50.jsonl
images/0.jpg
images/1.jpg
...
```

## Step 8: Train on SageMaker

### Option A: Quick Test (5 epochs, ~10 minutes)

```bash
python sagemaker/deploy.py \
  --instance-type ml.m5.xlarge \
  --epochs 5 \
  --skip-deploy
```

Cost: ~$0.50

### Option B: Full Training (10 epochs, ~20 minutes)

```bash
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --skip-deploy
```

Cost: ~$2.00

### Option C: Train + Deploy

```bash
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --endpoint-name discogs-sage-classifier \
  --endpoint-instance-type ml.m5.large
```

Cost: Training ~$2.00 + Endpoint $0.115/hour

## Step 9: Test Endpoint

```bash
# Test with a training image
python sagemaker/test_endpoint.py \
  --endpoint discogs-sage-classifier \
  --image backend/data/images/0.jpg
```

## Cost Management

### Stop Endpoint When Not in Use

```bash
# Delete endpoint (stops charges)
aws sagemaker delete-endpoint --endpoint-name discogs-sage-classifier

# Delete endpoint configuration
aws sagemaker delete-endpoint-config --endpoint-config-name discogs-sage-classifier

# Redeploy later with same model
python sagemaker/deploy.py --skip-training --endpoint-name discogs-sage-classifier
```

### Monthly Cost Estimates

**Development (testing)**
- Training: 2-3 jobs/week × $2 = ~$20/month
- Endpoint: Not running = $0
- S3: ~100 MB = $0.02/month
- **Total: ~$20/month**

**Production (always-on)**
- Training: 1 job/week × $2 = ~$8/month
- Endpoint: ml.m5.large 24/7 = ~$83/month
- S3: ~1 GB = $0.02/month
- **Total: ~$90/month**

**Production (auto-scaling)**
- Training: 1 job/week = ~$8/month
- Endpoint: ml.m5.large 8hr/day avg = ~$28/month
- S3: ~1 GB = $0.02/month
- **Total: ~$35/month**

## CloudWatch Monitoring

### View Training Logs

```bash
# List log streams for your training job
aws logs describe-log-streams \
  --log-group-name /aws/sagemaker/TrainingJobs \
  --order-by LastEventTime \
  --descending \
  --max-items 5

# Tail logs (replace LOG_STREAM_NAME)
aws logs tail /aws/sagemaker/TrainingJobs/LOG_STREAM_NAME --follow
```

### View Endpoint Metrics

```bash
# Get endpoint invocations (last hour)
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name ModelLatency \
  --dimensions Name=EndpointName,Value=discogs-sage-classifier \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average,Maximum
```

## Troubleshooting

### Issue: "Role not authorized"

```bash
# Wait 10-15 seconds after role creation
sleep 15

# Or add explicit permissions
aws iam attach-role-policy \
  --role-name DiscogsSageSageMakerRole \
  --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly
```

### Issue: "Bucket not found"

```bash
# Verify bucket exists
aws s3 ls s3://${BUCKET_NAME}

# Check region matches
aws s3api get-bucket-location --bucket ${BUCKET_NAME}
```

### Issue: "No training data found"

```bash
# Verify data in S3
aws s3 ls s3://${BUCKET_NAME}/album-classifier/data/ --recursive

# Re-upload if needed
python sagemaker/upload_data_s3.py
```

### Issue: "Training failed - Out of memory"

```bash
# Reduce batch size
python sagemaker/deploy.py --batch-size 4 --epochs 5
```

## Security Best Practices

1. **Enable MFA** on your AWS account
2. **Use IAM roles** with least privilege
3. **Enable S3 bucket versioning** for data recovery
4. **Enable CloudTrail** for audit logging
5. **Use VPC endpoints** for production (optional)
6. **Rotate credentials** regularly
7. **Enable S3 encryption** (AES256 or KMS)

## Production Checklist

- [ ] AWS CLI configured
- [ ] S3 bucket created with encryption
- [ ] IAM role created with proper permissions
- [ ] Environment variables configured
- [ ] Training data uploaded to S3
- [ ] Training job successful
- [ ] Endpoint deployed and tested
- [ ] CloudWatch alarms configured
- [ ] Cost alerts enabled
- [ ] Auto-scaling configured (optional)
- [ ] VPC configured (optional)

## Next Steps

1. **Integrate with Backend**: Update FastAPI to call SageMaker endpoint
2. **Set Up CI/CD**: Automate model retraining
3. **Add Monitoring**: CloudWatch dashboards and alarms
4. **Optimize Costs**: Implement auto-scaling and scheduled shutdowns
5. **Scale Up**: Add more albums to dataset

## Useful Commands

```bash
# List all endpoints
aws sagemaker list-endpoints

# Describe endpoint
aws sagemaker describe-endpoint --endpoint-name discogs-sage-classifier

# List training jobs
aws sagemaker list-training-jobs --sort-by CreationTime --sort-order Descending

# Check S3 bucket size
aws s3 ls s3://${BUCKET_NAME} --recursive --summarize | grep "Total Size"

# Estimate monthly costs
aws ce get-cost-and-usage \
  --time-period Start=$(date -d '30 days ago' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://<(echo '{"Services":{"Key":"SERVICE","Values":["Amazon SageMaker","Amazon S3"]}}')
```

## Support Resources

- [SageMaker Documentation](https://docs.aws.amazon.com/sagemaker/)
- [SageMaker Pricing](https://aws.amazon.com/sagemaker/pricing/)
- [AWS Cost Calculator](https://calculator.aws/)
- [SageMaker Examples](https://github.com/aws/amazon-sagemaker-examples)

