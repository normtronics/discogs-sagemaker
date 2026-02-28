# Using SageMaker Endpoint in Frontend

This guide shows how to integrate your deployed SageMaker endpoint with the Next.js frontend.

## 🎯 Two Options

### Option 1: Via Next.js API Route (Recommended)

The frontend calls a Next.js API route (`/api/predict`), which then calls SageMaker. This is more secure because:
- ✅ AWS credentials stay on the server
- ✅ No CORS issues
- ✅ Can add caching, rate limiting, etc.

**Files:**
- `src/app/api/predict/route.ts` - Uses AWS SDK v2
- `src/app/api/predict-sagemaker/route.ts` - Uses AWS SDK v3 (modern)

### Option 2: Direct FastAPI Backend

Keep using your local FastAPI backend (`http://localhost:8000/api/predict`), which can proxy to SageMaker.

## 🚀 Setup

### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

### Step 2: Configure Environment Variables

Create `frontend/.env.local`:

```bash
# Copy from example
cp .env.local.example .env.local

# Edit with your values
AWS_REGION=us-east-1
SAGEMAKER_ENDPOINT_NAME=album-classifier
```

### Step 3: Configure AWS Credentials

**Option A: Environment Variables**
```bash
export AWS_ACCESS_KEY_ID=your-key
export AWS_SECRET_ACCESS_KEY=your-secret
export AWS_REGION=us-east-1
```

**Option B: AWS Profile**
```bash
export AWS_PROFILE=your-profile-name
```

**Option C: AWS Credentials File** (already configured)
```bash
# Uses ~/.aws/credentials automatically
```

### Step 4: Update Frontend Code

The frontend already calls `/api/predict` by default. To switch:

**Use SageMaker (via Next.js API route):**
```typescript
// In page.tsx, already configured:
const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api/predict';
```

**Use Local FastAPI:**
```bash
# Set in .env.local:
NEXT_PUBLIC_API_URL=http://localhost:8000/api/predict
```

## 🔧 Testing

### Test SageMaker Endpoint Directly

```bash
# From backend directory
cd backend
python sagemaker/test_endpoint.py \
  --endpoint album-classifier \
  --image data/images/0.jpg
```

### Test via Next.js API Route

```bash
# Start Next.js dev server
cd frontend
npm run dev

# In browser: http://localhost:3000
# Upload an image and click "Identify Album"
```

### Test API Route Directly

```bash
# Test the API route
curl -X POST http://localhost:3000/api/predict \
  -F "file=@../backend/data/images/0.jpg"
```

## 📊 How It Works

```
User Uploads Image
    ↓
Frontend (page.tsx)
    ↓
Next.js API Route (/api/predict)
    ↓
AWS SageMaker Runtime Client
    ↓
SageMaker Endpoint (album-classifier)
    ↓
Returns Predictions
    ↓
Displayed in Frontend
```

## 🔐 Security Notes

1. **Never expose AWS credentials in frontend code**
   - Credentials are only in server-side API routes
   - Or use environment variables on server

2. **CORS Configuration**
   - SageMaker endpoints don't need CORS when called from server
   - Only needed if calling directly from browser (not recommended)

3. **Rate Limiting**
   - Consider adding rate limiting to API route
   - SageMaker endpoints have costs per invocation

## 🐛 Troubleshooting

### Error: "Endpoint not found"
- Check `SAGEMAKER_ENDPOINT_NAME` in `.env.local`
- Verify endpoint exists: `aws sagemaker list-endpoints`

### Error: "Invalid credentials"
- Check AWS credentials: `aws sts get-caller-identity`
- Verify region matches endpoint region

### Error: "CORS error"
- Shouldn't happen with API route approach
- If using direct frontend calls, configure CORS in SageMaker

### Error: "Module not found: aws-sdk"
- Run `npm install` in frontend directory

## 💰 Cost Considerations

- SageMaker endpoints charge per hour + per invocation
- Consider:
  - Using local FastAPI for development
  - Only deploying SageMaker endpoint for production
  - Auto-scaling down when not in use

## 🎯 Production Deployment

### Vercel Deployment

1. Set environment variables in Vercel dashboard:
   ```
   AWS_REGION=us-east-1
   SAGEMAKER_ENDPOINT_NAME=album-classifier
   AWS_ACCESS_KEY_ID=your-key
   AWS_SECRET_ACCESS_KEY=your-secret
   ```

2. Deploy:
   ```bash
   vercel --prod
   ```

### Other Platforms

Set the same environment variables in your hosting platform's dashboard.

## 📚 Additional Resources

- [AWS SageMaker Runtime Docs](https://docs.aws.amazon.com/sagemaker/latest/APIReference/API_runtime_InvokeEndpoint.html)
- [Next.js API Routes](https://nextjs.org/docs/app/building-your-application/routing/route-handlers)
- [AWS SDK for JavaScript](https://docs.aws.amazon.com/sdk-for-javascript/v2/developer-guide/)

