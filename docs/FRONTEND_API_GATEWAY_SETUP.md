# Frontend Setup for API Gateway

This guide shows how to configure your frontend to use the API Gateway endpoint instead of calling SageMaker directly.

## Quick Setup

### Step 1: Deploy Inference Infrastructure

First, deploy the API Gateway + Lambda infrastructure (see `docs/DEPLOY_INFERENCE.md`):

```bash
cd infrastructure
npm install
npm run deploy -- --context endpointName=album-classifier
```

### Step 2: Get API Gateway URL

After deployment, get the API Gateway URL from CDK outputs:

```bash
aws cloudformation describe-stacks \
  --stack-name InferenceStack \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiGatewayPredictUrl`].OutputValue' \
  --output text
```

Or check the terminal output after deployment.

### Step 3: Configure Frontend

Create or update `frontend/.env.local`:

```bash
# Use API Gateway endpoint (recommended for production)
NEXT_PUBLIC_API_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict

# Or use Next.js API route (which calls SageMaker directly)
# NEXT_PUBLIC_API_URL=/api/predict

# Or use local FastAPI backend
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/predict
```

### Step 4: Update Frontend Code (Optional)

The current frontend sends FormData. The API Gateway Lambda function supports both FormData and JSON with base64 images.

**Option A: Keep FormData (Current)**

The Lambda function handles multipart/form-data, but API Gateway doesn't parse it automatically. For better reliability, use Option B.

**Option B: Send JSON with Base64 (Recommended)**

Update `frontend/src/app/page.tsx` to convert images to base64:

```typescript
const handleSubmit = async () => {
  if (!selectedFile) return;

  setLoading(true);
  setError("");
  setPredictions([]);

  try {
    // Convert file to base64
    const reader = new FileReader();
    reader.onloadend = async () => {
      const base64String = reader.result as string;
      
      // Remove data URL prefix if present
      const base64Data = base64String.includes(',') 
        ? base64String.split(',')[1] 
        : base64String;

      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api/predict';
      
      // Check if API Gateway URL (has execute-api in it)
      const isApiGateway = apiUrl.includes('execute-api');
      
      const response = await fetch(apiUrl, {
        method: "POST",
        headers: isApiGateway ? {
          "Content-Type": "application/json",
        } : undefined,
        body: isApiGateway 
          ? JSON.stringify({
              image: base64Data,
              content_type: selectedFile.type || 'image/jpeg',
            })
          : (() => {
              const formData = new FormData();
              formData.append("file", selectedFile);
              return formData;
            })(),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data: PredictionResponse = await response.json();
      setPredictions(data.predictions);
      setLoading(false);
    };
    
    reader.readAsDataURL(selectedFile);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to get predictions");
    console.error("Prediction error:", err);
    setLoading(false);
  }
};
```

**Option C: Use Next.js API Route as Proxy**

Keep using `/api/predict` but update it to call API Gateway:

```typescript
// frontend/src/app/api/predict/route.ts
import { NextRequest, NextResponse } from 'next/server';

const API_GATEWAY_URL = process.env.API_GATEWAY_URL || '';

export async function POST(request: NextRequest) {
  try {
    const formData = await request.formData();
    const file = formData.get('file') as File;

    if (!file) {
      return NextResponse.json(
        { success: false, error: 'No file provided' },
        { status: 400 }
      );
    }

    // Convert to base64
    const arrayBuffer = await file.arrayBuffer();
    const base64 = Buffer.from(arrayBuffer).toString('base64');

    // Call API Gateway
    const response = await fetch(API_GATEWAY_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        image: base64,
        content_type: file.type || 'image/jpeg',
      }),
    });

    if (!response.ok) {
      throw new Error(`API Gateway error: ${response.status}`);
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error: any) {
    console.error('API Gateway proxy error:', error);
    return NextResponse.json(
      {
        success: false,
        error: error.message || 'Failed to get predictions',
      },
      { status: 500 }
    );
  }
}
```

Then set in `.env.local`:

```bash
API_GATEWAY_URL=https://abc123xyz.execute-api.us-east-1.amazonaws.com/prod/predict
NEXT_PUBLIC_API_URL=/api/predict
```

## Testing

### Test API Gateway Directly

```bash
# Convert image to base64
IMAGE_B64=$(base64 -i test_image.jpg)

# Call API Gateway
curl -X POST https://YOUR_API_ID.execute-api.us-east-1.amazonaws.com/prod/predict \
  -H "Content-Type: application/json" \
  -d "{
    \"image\": \"$IMAGE_B64\",
    \"content_type\": \"image/jpeg\"
  }"
```

### Test from Frontend

1. Start frontend:
   ```bash
   cd frontend
   npm run dev
   ```

2. Open http://localhost:3000

3. Upload an image

4. Check browser console for errors

5. Check CloudWatch logs:
   ```bash
   aws logs tail /aws/lambda/InferenceStack-PredictFunction-XXXXX --follow
   ```

## Troubleshooting

### CORS Errors

If you see CORS errors:

1. Verify API Gateway CORS is enabled (should be automatic with CDK)
2. Check browser console for CORS error details
3. Verify frontend origin matches allowed origins in API Gateway

### 400 Bad Request

- Check Lambda logs for error details
- Verify image is properly base64 encoded
- Ensure content_type is set correctly

### 500 Internal Server Error

- Check Lambda logs:
  ```bash
  aws logs tail /aws/lambda/InferenceStack-PredictFunction-XXXXX --follow
  ```
- Verify SageMaker endpoint is "InService"
- Check Lambda has `sagemaker-runtime:InvokeEndpoint` permission

### Timeout Errors

- Increase Lambda timeout in `infrastructure/lib/inference-stack.ts`
- Check SageMaker endpoint latency
- Consider using async invocation for long-running requests

## Security Considerations

### Production Setup

1. **Restrict CORS Origins**:
   ```typescript
   // In inference-stack.ts
   allowOrigins: ['https://yourdomain.com'],
   ```

2. **Add Authentication**:
   - Use Cognito authorizer in API Gateway
   - Or JWT token validation in Lambda

3. **Rate Limiting**:
   - Configure API Gateway throttling
   - Or use AWS WAF

4. **Input Validation**:
   - Validate image size in Lambda
   - Validate image format
   - Set max file size limits

## Environment Variables Summary

| Variable | Purpose | Example |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | Frontend API endpoint | `https://api.execute-api.us-east-1.amazonaws.com/prod/predict` |
| `API_GATEWAY_URL` | Backend API Gateway URL (for proxy) | `https://api.execute-api.us-east-1.amazonaws.com/prod/predict` |
| `SAGEMAKER_ENDPOINT_NAME` | SageMaker endpoint name | `album-classifier` |

## Next Steps

1. ✅ Configure frontend environment variables
2. ✅ Test API Gateway endpoint
3. ✅ Update frontend code if needed
4. ✅ Add authentication (optional)
5. ✅ Set up monitoring and alerts

## See Also

- [Complete Setup Guide](SAGEMAKER_COMPLETE_SETUP.md)
- [Deploy Inference Infrastructure](DEPLOY_INFERENCE.md)
- [SageMaker Console Guide](../SAGEMAKER_CONSOLE_GUIDE.md)
