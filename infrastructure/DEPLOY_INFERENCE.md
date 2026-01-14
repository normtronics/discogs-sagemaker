# Deploying Inference Infrastructure (API Gateway + Lambda)

This guide shows how to deploy the API Gateway + Lambda infrastructure for calling your SageMaker endpoint from the frontend.

## Prerequisites

1. ✅ SageMaker endpoint deployed and in "InService" status
2. ✅ AWS CLI configured with appropriate permissions
3. ✅ CDK bootstrapped in your AWS account/region

## Quick Deploy

```bash
cd infrastructure

# Install dependencies
npm install

# Deploy inference stack
npm run deploy -- \
  --context endpointName=album-classifier

# Or with environment variables
SAGEMAKER_ENDPOINT_NAME=album-classifier npm run deploy
```

## Detailed Steps

### Step 1: Install Dependencies

```bash
cd infrastructure
npm install
```

### Step 2: Bootstrap CDK (if not already done)

```bash
npm run cdk bootstrap
```

### Step 3: Deploy Inference Stack

The inference stack creates:
- **Lambda function** with SageMaker invoke permissions
- **API Gateway** REST API with `/predict` endpoint
- **CORS** enabled for frontend access

```bash
# Deploy with endpoint name
npm run deploy -- \
  --context endpointName=YOUR_ENDPOINT_NAME

# Example:
npm run deploy -- \
  --context endpointName=album-classifier
```

### Step 4: Get API Gateway URL

After deployment, CDK will output the API Gateway URL:

```
Outputs:
InferenceStack.ApiGatewayUrl = https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod
InferenceStack.ApiGatewayPredictUrl = https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict
```

Or get it via AWS CLI:

```bash
aws cloudformation describe-stacks \
  --stack-name InferenceStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayPredictUrl`].OutputValue' \
  --output text
```

### Step 5: Update Frontend

Update your frontend environment variables:

**`frontend/.env.local`:**

```bash
NEXT_PUBLIC_API_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict
```

### Step 6: Test

```bash
# Test via curl
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/predict \
  -H "Content-Type: application/json" \
  -d '{
    "image": "'$(base64 -i test_image.jpg)'",
    "content_type": "image/jpeg"
  }'

# Or test from frontend
cd frontend
npm run dev
# Upload an image via the UI
```

## Configuration Options

### Deploy Both Stacks

Deploy both training and inference infrastructure:

```bash
npm run deploy -- \
  --context bucketName=your-ml-bucket \
  --context sagemakerRoleArn=arn:aws:iam::ACCOUNT:role/RoleName \
  --context endpointName=album-classifier
```

### Custom CORS Origins

Edit `infrastructure/lib/inference-stack.ts`:

```typescript
defaultCorsPreflightOptions: {
  allowOrigins: ['https://yourdomain.com'], // Restrict to specific origins
  // ...
}
```

### Custom Lambda Timeout

Edit `infrastructure/lib/inference-stack.ts`:

```typescript
timeout: cdk.Duration.seconds(60), // Increase if needed
```

## Troubleshooting

### Lambda Function Not Found

Ensure the Lambda code is in the correct location:

```bash
ls -la backend/aws/inference/lambda_function.py
```

### Permission Denied

Check Lambda execution role has `sagemaker-runtime:InvokeEndpoint`:

```bash
aws iam get-role-policy \
  --role-name InferenceStack-PredictFunctionRole-XXXXX \
  --policy-name PolicyName
```

### CORS Errors

1. Verify CORS is enabled in API Gateway
2. Check frontend origin matches allowed origins
3. Ensure preflight OPTIONS request succeeds

### Endpoint Not Found

Verify endpoint name matches:

```bash
aws sagemaker describe-endpoint --endpoint-name album-classifier
```

### Timeout Errors

Increase Lambda timeout:

```typescript
timeout: cdk.Duration.seconds(60), // In inference-stack.ts
```

## Cleanup

To remove the infrastructure:

```bash
npm run cdk destroy InferenceStack
```

## Next Steps

1. ✅ Test API Gateway endpoint
2. ✅ Update frontend to use API Gateway URL
3. ✅ Add authentication (Cognito/JWT) if needed
4. ✅ Set up CloudWatch alarms for errors
5. ✅ Monitor costs

## See Also

- [Complete Setup Guide](../SAGEMAKER_COMPLETE_SETUP.md)
- [SageMaker Console Guide](../SAGEMAKER_CONSOLE_GUIDE.md)
