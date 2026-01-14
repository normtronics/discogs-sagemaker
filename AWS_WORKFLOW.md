# AWS Workflow - Step by Step

Your complete workflow for deploying to AWS SageMaker.

## 🎯 Goal

Deploy the album classifier to AWS SageMaker for production use.

## 📋 Workflow

### Phase 1: AWS Setup (One-time, ~15 minutes)

```bash
# 1. Configure AWS CLI
aws configure
aws sts get-caller-identity  # Verify

# 2. Create S3 bucket
export BUCKET_NAME="discogs-sage-sagemaker"
aws s3 mb s3://${BUCKET_NAME}

# 3. Create SageMaker IAM role
# See AWS_SETUP.md for detailed commands
# Save the role ARN!

# 4. Update backend/.env.local
cat >> backend/.env.local << EOF
AWS_REGION=us-east-1
SAGEMAKER_ROLE=arn:aws:iam::YOUR_ACCOUNT_ID:role/DiscogsSageSageMakerRole
SAGEMAKER_BUCKET=${BUCKET_NAME}
EOF
```

### Phase 2: Prepare Data (~5 minutes)

```bash
# 1. Download album images (if not already done)
cd backend
python main.py &
sleep 5
curl -X POST http://localhost:8000/api/download-images
pkill -f "python main.py"
cd ..

# 2. Upload to S3
python sagemaker/upload_data_s3.py

# 3. Verify
aws s3 ls s3://${BUCKET_NAME}/album-classifier/data/ --recursive
```

### Phase 3: Train Model (~20-30 minutes)

#### Option A: Quick Test (CPU, cheaper)

```bash
python sagemaker/deploy.py \
  --instance-type ml.m5.xlarge \
  --epochs 5 \
  --skip-deploy
```

**Cost**: ~$0.50  
**Time**: ~15 minutes  
**Use for**: Initial testing

#### Option B: Full Training (GPU, faster)

```bash
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --skip-deploy
```

**Cost**: ~$2.00  
**Time**: ~10 minutes  
**Use for**: Production training

### Phase 4: Deploy Endpoint (~5 minutes)

```bash
python sagemaker/deploy.py \
  --skip-training \
  --endpoint-name discogs-sage-classifier \
  --endpoint-instance-type ml.m5.large
```

**Cost**: $0.115/hour (ongoing)  
**Use for**: Production serving

### Phase 5: Test Endpoint (~1 minute)

```bash
# Test with training image
python sagemaker/test_endpoint.py \
  --endpoint discogs-sage-classifier \
  --image backend/data/images/0.jpg

# Test with custom image
python sagemaker/test_endpoint.py \
  --endpoint discogs-sage-classifier \
  --image /path/to/album_cover.jpg
```

### Phase 6: Stop Endpoint (when not in use)

```bash
# Stop to avoid charges
aws sagemaker delete-endpoint --endpoint-name discogs-sage-classifier

# Redeploy later
python sagemaker/deploy.py --skip-training
```

## 🔄 Development Workflow

### Local Development → Cloud Training

```bash
# 1. Test locally first (free!)
python sagemaker/local_train.py --epochs 2
python sagemaker/local_predict.py --image backend/data/images/0.jpg

# 2. If working, train on cloud
python sagemaker/upload_data_s3.py
python sagemaker/deploy.py --epochs 10
```

### Iterative Training

```bash
# 1. Add more data
# Download more images via backend API

# 2. Re-upload to S3
python sagemaker/upload_data_s3.py

# 3. Retrain
python sagemaker/deploy.py \
  --epochs 10 \
  --skip-deploy

# 4. Update endpoint (zero-downtime)
python sagemaker/deploy.py \
  --skip-training \
  --endpoint-name discogs-sage-classifier
```

## 💰 Cost Tracking

### View Current Month Costs

```bash
aws ce get-cost-and-usage \
  --time-period Start=$(date -d 'month start' +%Y-%m-%d),End=$(date +%Y-%m-%d) \
  --granularity MONTHLY \
  --metrics BlendedCost
```

### Set Up Cost Alerts

```bash
# Create SNS topic for alerts
aws sns create-topic --name SageMakerCostAlerts

# Subscribe your email
aws sns subscribe \
  --topic-arn arn:aws:sns:us-east-1:ACCOUNT_ID:SageMakerCostAlerts \
  --protocol email \
  --notification-endpoint your-email@example.com

# Create budget (via Console or CLI)
# Set alert at $50/month
```

## 🎛️ Production Workflow

### Weekly Model Updates

```bash
#!/bin/bash
# weekly_update.sh

# 1. Download latest data
cd backend && python download_new_releases.py

# 2. Upload to S3
cd .. && python sagemaker/upload_data_s3.py

# 3. Train new model
python sagemaker/deploy.py \
  --instance-type ml.p3.2xlarge \
  --epochs 10 \
  --skip-deploy

# 4. Test new model
python sagemaker/test_endpoint.py \
  --endpoint discogs-sage-classifier-staging \
  --image test_images/*.jpg

# 5. If tests pass, update production endpoint
python sagemaker/deploy.py \
  --skip-training \
  --endpoint-name discogs-sage-classifier
```

### A/B Testing

```bash
# Deploy staging endpoint
python sagemaker/deploy.py \
  --endpoint-name discogs-sage-classifier-staging \
  --endpoint-instance-type ml.t2.medium

# Test both endpoints
python sagemaker/test_endpoint.py --endpoint discogs-sage-classifier-staging --image test.jpg
python sagemaker/test_endpoint.py --endpoint discogs-sage-classifier --image test.jpg

# If staging is better, promote to production
aws sagemaker update-endpoint \
  --endpoint-name discogs-sage-classifier \
  --endpoint-config-name $(aws sagemaker describe-endpoint --endpoint-name discogs-sage-classifier-staging --query EndpointConfigName --output text)
```

## 🔍 Monitoring

### Check Endpoint Status

```bash
# Is it running?
aws sagemaker describe-endpoint \
  --endpoint-name discogs-sage-classifier \
  --query 'EndpointStatus'

# How many invocations today?
aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name ModelInvocations \
  --dimensions Name=EndpointName,Value=discogs-sage-classifier \
  --start-time $(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 86400 \
  --statistics Sum
```

### View Training History

```bash
# List recent training jobs
aws sagemaker list-training-jobs \
  --sort-by CreationTime \
  --sort-order Descending \
  --max-results 10

# Get training job details
aws sagemaker describe-training-job \
  --training-job-name <job-name>
```

## 🚨 Troubleshooting

### Training Failed

```bash
# View logs
aws logs tail /aws/sagemaker/TrainingJobs --follow

# Common fixes:
# - Reduce batch size: --batch-size 4
# - Use smaller instance: --instance-type ml.m5.large
# - Check S3 data: aws s3 ls s3://${BUCKET_NAME}/album-classifier/data/
```

### Endpoint Not Responding

```bash
# Check status
aws sagemaker describe-endpoint --endpoint-name discogs-sage-classifier

# Check CloudWatch logs
aws logs tail /aws/sagemaker/Endpoints/discogs-sage-classifier --follow

# Restart endpoint
aws sagemaker delete-endpoint --endpoint-name discogs-sage-classifier
python sagemaker/deploy.py --skip-training
```

### High Costs

```bash
# Check what's running
aws sagemaker list-endpoints
aws sagemaker list-training-jobs --status-equals InProgress

# Stop everything
aws sagemaker list-endpoints --query 'Endpoints[].EndpointName' --output text | \
  xargs -I {} aws sagemaker delete-endpoint --endpoint-name {}
```

## 📊 Quick Reference

| Task | Command | Cost | Time |
|------|---------|------|------|
| Local test | `python sagemaker/local_train.py` | $0 | 5 min |
| Upload data | `python sagemaker/upload_data_s3.py` | $0 | 2 min |
| Quick train | `deploy.py --instance-type ml.m5.xlarge --epochs 5` | $0.50 | 15 min |
| Full train | `deploy.py --instance-type ml.p3.2xlarge --epochs 10` | $2.00 | 10 min |
| Deploy endpoint | `deploy.py --skip-training` | $0.12/hr | 5 min |
| Test endpoint | `test_endpoint.py --endpoint NAME --image test.jpg` | $0.001 | 10 sec |

## 🎓 Best Practices

1. **Always test locally first** - It's free and fast
2. **Start with small epochs** - Validate pipeline before full training
3. **Use GPU for production** - Faster training = lower cost
4. **Stop endpoints when not in use** - Save $80+/month
5. **Monitor costs daily** - Set up alerts
6. **Version your models** - Keep track of what's deployed
7. **Test before promoting** - Use staging endpoints

## 🔗 Related Docs

- [AWS_SETUP.md](AWS_SETUP.md) - Initial AWS configuration
- [sagemaker/README.md](sagemaker/README.md) - Detailed documentation
- [SAGEMAKER_QUICKSTART.md](SAGEMAKER_QUICKSTART.md) - Quick start guide

