# Troubleshooting SageMaker Endpoint Timeouts

## Issue: Endpoint Timeout Error

If you see: `Your invocation timed out while waiting for a response from container primary`

## Common Causes

### 1. Cold Start (Most Common)
- **First request** after endpoint creation takes 60-90 seconds
- Model needs to load into memory
- Subsequent requests are faster (5-10 seconds)

**Solution:** Wait for first request to complete, or send a warm-up request

### 2. Instance Type Too Small
- Small instances (ml.t2.medium) are slow
- CPU-only instances are slower than GPU

**Check instance type:**
```bash
AWS_PROFILE=artofdigging aws sagemaker describe-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --region us-east-1 \
  | grep InstanceType
```

**Recommended instance types:**
- `ml.m5.large` - Good balance ($0.115/hr)
- `ml.m5.xlarge` - Faster ($0.23/hr)
- `ml.g4dn.xlarge` - GPU, fastest ($0.526/hr)

### 3. Model Loading Error
- Check CloudWatch logs for errors
- Model file might be corrupted
- Metadata.json might be missing

**Check logs:**
```bash
# Use the link from the error message:
https://us-east-1.console.aws.amazon.com/cloudwatch/home?region=us-east-1#logEventViewer:group=/aws/sagemaker/Endpoints/album-classifier-1764735852
```

### 4. Image Size Too Large
- Very large images take longer to process
- Resize images before sending (max 224x224 for model)

## Solutions

### Solution 1: Increase Timeout (Already Done)
The API route now has a 2-minute timeout. This should handle cold starts.

### Solution 2: Check Endpoint Status

```bash
AWS_PROFILE=artofdigging aws sagemaker describe-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --region us-east-1
```

Look for:
- `EndpointStatus`: Should be `InService`
- `InstanceType`: Check if it's too small

### Solution 3: Check CloudWatch Logs

1. Go to CloudWatch Console
2. Navigate to Log Groups
3. Find: `/aws/sagemaker/Endpoints/album-classifier-1764735852`
4. Check recent log streams for errors

Common errors:
- `ModelError`: Model failed to load
- `ValueError`: Input format issue
- `TimeoutError`: Processing took too long

### Solution 4: Warm Up Endpoint

Send a test request to warm up the endpoint:

```bash
cd backend
python sagemaker/test_endpoint.py \
  --endpoint album-classifier-1764735852 \
  --image data/images/0.jpg
```

### Solution 5: Upgrade Instance Type

If endpoint is too slow, upgrade:

```bash
# Create new endpoint configuration with larger instance
AWS_PROFILE=artofdigging aws sagemaker create-endpoint-config \
  --endpoint-config-name album-classifier-config-v2 \
  --production-variants \
    VariantName=AllTraffic,ModelName=your-model-name,InitialInstanceCount=1,InstanceType=ml.m5.xlarge \
  --region us-east-1

# Update endpoint
AWS_PROFILE=artofdigging aws sagemaker update-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --endpoint-config-name album-classifier-config-v2 \
  --region us-east-1
```

### Solution 6: Check Model Files

Verify model artifacts exist:

```bash
# Check S3 bucket
AWS_PROFILE=artofdigging aws s3 ls s3://your-bucket/album-classifier/models/ --recursive
```

Should see:
- `model.tar.gz` or `model.pth`
- `metadata.json`

## Quick Diagnostic Commands

```bash
# 1. Check endpoint status
AWS_PROFILE=artofdigging aws sagemaker describe-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --region us-east-1 \
  --query 'EndpointStatus'

# 2. Check instance type
AWS_PROFILE=artofdigging aws sagemaker describe-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --region us-east-1 \
  --query 'ProductionVariants[0].InstanceType'

# 3. Test endpoint directly
AWS_PROFILE=artofdigging aws sagemaker-runtime invoke-endpoint \
  --endpoint-name album-classifier-1764735852 \
  --content-type image/jpeg \
  --body fileb://backend/data/images/0.jpg \
  output.json \
  --region us-east-1

# 4. Check CloudWatch metrics
AWS_PROFILE=artofdigging aws cloudwatch get-metric-statistics \
  --namespace AWS/SageMaker \
  --metric-name ModelLatency \
  --dimensions Name=EndpointName,Value=album-classifier-1764735852 \
  --start-time $(date -u -d '1 hour ago' +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Average \
  --region us-east-1
```

## Expected Behavior

- **Cold start**: 60-90 seconds (first request)
- **Warm requests**: 5-15 seconds
- **With GPU**: 2-5 seconds

If requests consistently take >60 seconds, there's likely an issue.

## Next Steps

1. Check CloudWatch logs (link in error message)
2. Verify endpoint is `InService`
3. Check instance type
4. Try warm-up request
5. If still failing, check model files in S3

