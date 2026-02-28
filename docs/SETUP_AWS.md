# AWS Profile Setup for Frontend

## Quick Setup

### Step 1: Install Dependencies

```bash
cd frontend
npm install
```

This installs:
- `@aws-sdk/client-sagemaker-runtime` - SageMaker client
- `@aws-sdk/credential-providers` - Profile support

### Step 2: Create Environment File

Create `frontend/.env.local`:

```bash
AWS_PROFILE=artofdigging
AWS_REGION=us-east-1
SAGEMAKER_ENDPOINT_NAME=album-classifier-1764735852
```

### Step 3: Verify AWS Profile

```bash
# Check profile exists
aws configure list-profiles

# Test profile works
AWS_PROFILE=artofdigging aws sts get-caller-identity

# Should show account info for artofdigging account
```

### Step 4: Run Frontend

```bash
cd frontend
npm run dev
```

The API route will automatically use the `artofdigging` profile from `~/.aws/credentials`.

## How It Works

The API route (`src/app/api/predict/route.ts`) uses:

```typescript
import { fromIni } from '@aws-sdk/credential-providers';

const client = new SageMakerRuntimeClient({
  region: awsRegion,
  credentials: fromIni({ profile: 'artofdigging' }),
});
```

This loads credentials from `~/.aws/credentials` using the `[artofdigging]` profile.

## Troubleshooting

### Error: "The security token included in the request is invalid"

1. **Check profile exists:**
   ```bash
   cat ~/.aws/credentials | grep "\[artofdigging\]"
   ```

2. **Verify credentials are valid:**
   ```bash
   AWS_PROFILE=artofdigging aws sts get-caller-identity
   ```

3. **Check region matches endpoint:**
   ```bash
   AWS_PROFILE=artofdigging aws sagemaker list-endpoints --region us-east-1
   ```

### Error: "Cannot find module '@aws-sdk/credential-providers'"

```bash
cd frontend
npm install @aws-sdk/credential-providers
```

### Error: "Endpoint not found"

Check endpoint name and region:
```bash
AWS_PROFILE=artofdigging aws sagemaker list-endpoints --region us-east-1
```

Update `.env.local` if endpoint name is different.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `AWS_PROFILE` | `artofdigging` | AWS profile name from `~/.aws/credentials` |
| `AWS_REGION` | `us-east-1` | AWS region where endpoint is deployed |
| `SAGEMAKER_ENDPOINT_NAME` | `album-classifier-1764735852` | Name of your SageMaker endpoint |

## Alternative: Use Environment Variables Instead of Profile

If you prefer not to use profiles, set these in `.env.local`:

```bash
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=us-east-1
SAGEMAKER_ENDPOINT_NAME=album-classifier
```

Then update `route.ts` to use default credentials instead of `fromIni`.

