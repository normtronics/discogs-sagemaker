# AWS Credentials for Multiple Accounts

Guide for managing credentials across multiple AWS accounts.

## 🔑 Getting AWS Credentials

### Step 1: Sign in to AWS Console

1. Go to [AWS Console](https://console.aws.amazon.com/)
2. Sign in to the **specific account** you want to use
3. Check the account ID in the top-right dropdown (12-digit number)

### Step 2: Create IAM User (If Needed)

If you don't have an IAM user with programmatic access:

```bash
# Via AWS Console:
1. Go to IAM → Users
2. Click "Create user"
3. Enter username (e.g., "sagemaker-dev")
4. Click "Next"
5. Select "Attach policies directly"
6. Add these policies:
   - AmazonSageMakerFullAccess
   - AmazonS3FullAccess (or create custom policy for your bucket)
7. Click "Next" → "Create user"
```

### Step 3: Create Access Keys

```bash
# Via AWS Console:
1. Go to IAM → Users → [Your User]
2. Click "Security credentials" tab
3. Scroll to "Access keys"
4. Click "Create access key"
5. Select "Command Line Interface (CLI)"
6. Check "I understand" → Click "Next"
7. Add description (e.g., "Local development")
8. Click "Create access key"

# ⚠️ IMPORTANT: Download the CSV or copy both:
#    - Access key ID (starts with AKIA...)
#    - Secret access key (long random string)
#    - You can't view the secret again!
```

### Alternative: Get Keys via CLI (if you have admin access)

```bash
# Create access key for your user
aws iam create-access-key --user-name YOUR_USERNAME

# Output will show AccessKeyId and SecretAccessKey
```

## 📋 Managing Multiple AWS Accounts

### Option 1: AWS CLI Profiles (Recommended)

Configure separate profiles for each account:

```bash
# Configure profile for Account 1 (e.g., development)
aws configure --profile discogs-dev
# Enter:
#   AWS Access Key ID: AKIA...
#   AWS Secret Access Key: ...
#   Default region: us-east-1
#   Default output format: json

# Configure profile for Account 2 (e.g., production)
aws configure --profile discogs-prod
# Enter credentials for production account

# Configure profile for Account 3 (e.g., staging)
aws configure --profile discogs-staging
# Enter credentials for staging account
```

### View All Configured Profiles

```bash
# List profiles
cat ~/.aws/credentials

# Example output:
# [default]
# aws_access_key_id = AKIA...
# aws_secret_access_key = ...
#
# [discogs-dev]
# aws_access_key_id = AKIA...
# aws_secret_access_key = ...
#
# [discogs-prod]
# aws_access_key_id = AKIA...
# aws_secret_access_key = ...
```

### Switch Between Accounts

```bash
# Method 1: Set AWS_PROFILE environment variable
export AWS_PROFILE=discogs-dev

# Verify which account you're using
aws sts get-caller-identity

# Output shows:
# {
#     "UserId": "AIDAI...",
#     "Account": "123456789012",
#     "Arn": "arn:aws:iam::123456789012:user/your-user"
# }

# Switch to production
export AWS_PROFILE=discogs-prod
aws sts get-caller-identity  # Different account ID!

# Method 2: Use --profile flag with each command
aws s3 ls --profile discogs-dev
aws s3 ls --profile discogs-prod
```

## 🔧 Configure Project for Specific Account

### Update backend/.env.local

```bash
# Add AWS profile to your configuration
cat >> backend/.env.local << 'EOF'

# AWS Configuration
AWS_REGION=us-east-1
AWS_PROFILE=discogs-dev        # ← Specify which profile to use

# SageMaker Configuration (for this account)
SAGEMAKER_ROLE=arn:aws:iam::123456789012:role/DiscogsSageSageMakerRole
SAGEMAKER_BUCKET=discogs-sage-dev-sagemaker

# Discogs API
DISCOGS_CONSUMER_KEY=your_key
DISCOGS_CONSUMER_SECRET=your_secret
EOF
```

### Use Profile in Scripts

All the scripts already support `AWS_PROFILE`:

```bash
# Upload data using specific profile
export AWS_PROFILE=discogs-dev
python sagemaker/upload_data_s3.py

# Or set it in .env.local and it will be picked up automatically
python sagemaker/deploy.py
```

### Verify Profile is Working

```bash
# Load profile from .env.local
source <(grep -v '^#' backend/.env.local | sed 's/^/export /')

# Check which account
aws sts get-caller-identity

# Should show the correct account ID
```

## 🏢 Multiple Environments Setup

### Recommended Structure

```bash
# Development Account
AWS_PROFILE=discogs-dev
SAGEMAKER_BUCKET=discogs-sage-dev-sagemaker
SAGEMAKER_ROLE=arn:aws:iam::111111111111:role/SageMakerRole-Dev

# Staging Account  
AWS_PROFILE=discogs-staging
SAGEMAKER_BUCKET=discogs-sage-staging-sagemaker
SAGEMAKER_ROLE=arn:aws:iam::222222222222:role/SageMakerRole-Staging

# Production Account
AWS_PROFILE=discogs-prod
SAGEMAKER_BUCKET=discogs-sage-prod-sagemaker
SAGEMAKER_ROLE=arn:aws:iam::333333333333:role/SageMakerRole-Prod
```

### Create Environment-Specific Config Files

```bash
# backend/.env.dev
AWS_REGION=us-east-1
AWS_PROFILE=discogs-dev
SAGEMAKER_ROLE=arn:aws:iam::111111111111:role/SageMakerRole-Dev
SAGEMAKER_BUCKET=discogs-sage-dev-sagemaker

# backend/.env.staging
AWS_REGION=us-east-1
AWS_PROFILE=discogs-staging
SAGEMAKER_ROLE=arn:aws:iam::222222222222:role/SageMakerRole-Staging
SAGEMAKER_BUCKET=discogs-sage-staging-sagemaker

# backend/.env.prod
AWS_REGION=us-east-1
AWS_PROFILE=discogs-prod
SAGEMAKER_ROLE=arn:aws:iam::333333333333:role/SageMakerRole-Prod
SAGEMAKER_BUCKET=discogs-sage-prod-sagemaker

# Switch environments
cp backend/.env.dev backend/.env.local     # Use dev
cp backend/.env.prod backend/.env.local    # Use prod
```

## 🔐 Security Best Practices

### 1. Use IAM Roles (Not Root Account)

```bash
# ✗ DON'T: Use root account credentials
# ✓ DO: Create IAM user with specific permissions

# Create IAM user with minimal required permissions
aws iam create-user --user-name sagemaker-developer
```

### 2. Rotate Access Keys Regularly

```bash
# Create new access key
aws iam create-access-key --user-name sagemaker-developer

# Update ~/.aws/credentials with new key

# Test new key works
aws sts get-caller-identity

# Delete old key
aws iam delete-access-key \
  --user-name sagemaker-developer \
  --access-key-id AKIA_OLD_KEY_ID
```

### 3. Use AWS SSO (Enterprise Option)

If your organization uses AWS SSO:

```bash
# Configure SSO
aws configure sso

# Follow prompts:
#   SSO start URL: https://your-org.awsapps.com/start
#   SSO Region: us-east-1
#   Select account and role
#   CLI profile name: discogs-dev

# Login
aws sso login --profile discogs-dev

# Use profile
export AWS_PROFILE=discogs-dev
```

### 4. Enable MFA

```bash
# Add MFA to your IAM user in AWS Console
1. Go to IAM → Users → [Your User]
2. Security credentials tab
3. Assign MFA device
4. Use authenticator app (Google Authenticator, Authy, etc.)

# For CLI access with MFA, use temporary credentials:
aws sts get-session-token \
  --serial-number arn:aws:iam::ACCOUNT_ID:mfa/USER_NAME \
  --token-code 123456
```

## 🧪 Testing Account Access

### Verify Credentials

```bash
# Check which account you're using
aws sts get-caller-identity

# List S3 buckets (verifies S3 access)
aws s3 ls

# List SageMaker training jobs (verifies SageMaker access)
aws sagemaker list-training-jobs

# Check specific bucket access
aws s3 ls s3://your-bucket-name/
```

### Test Script

```bash
#!/bin/bash
# test_aws_access.sh

echo "Testing AWS Access..."
echo ""

# Get account info
echo "Account Information:"
aws sts get-caller-identity

echo ""
echo "S3 Buckets:"
aws s3 ls

echo ""
echo "SageMaker Access:"
aws sagemaker list-training-jobs --max-results 1

echo ""
echo "Region:"
aws configure get region --profile ${AWS_PROFILE:-default}

echo ""
echo "✓ All checks passed!"
```

## 📊 Quick Reference

### Get Current Account Info

```bash
# Account ID
aws sts get-caller-identity --query Account --output text

# User/Role ARN
aws sts get-caller-identity --query Arn --output text

# Current profile
echo $AWS_PROFILE

# Current region
aws configure get region
```

### Common Issues

**Issue**: "Unable to locate credentials"
```bash
# Solution: Configure AWS CLI
aws configure --profile discogs-dev

# Or set profile
export AWS_PROFILE=discogs-dev
```

**Issue**: "An error occurred (AccessDenied)"
```bash
# Solution: Check which account you're using
aws sts get-caller-identity

# Verify permissions
aws iam get-user
aws iam list-attached-user-policies --user-name YOUR_USERNAME
```

**Issue**: Wrong account
```bash
# Solution: Switch profile
export AWS_PROFILE=correct-profile
aws sts get-caller-identity  # Verify
```

## 🔄 Workflow for Multiple Accounts

### Daily Development Workflow

```bash
# 1. Set development profile
export AWS_PROFILE=discogs-dev

# 2. Verify account
aws sts get-caller-identity

# 3. Use development environment
cp backend/.env.dev backend/.env.local

# 4. Work normally
python sagemaker/upload_data_s3.py
python sagemaker/deploy.py --local-mode
```

### Production Deployment Workflow

```bash
# 1. Switch to production profile
export AWS_PROFILE=discogs-prod

# 2. VERIFY you're in the right account!
aws sts get-caller-identity

# 3. Use production environment
cp backend/.env.prod backend/.env.local

# 4. Deploy
python sagemaker/deploy.py --instance-type ml.p3.2xlarge
```

### Safety Script

```bash
#!/bin/bash
# safe_deploy.sh - Always prompts for confirmation

echo "Current AWS Account:"
aws sts get-caller-identity

echo ""
read -p "Is this the correct account? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Deployment cancelled"
    exit 1
fi

echo "Proceeding with deployment..."
python sagemaker/deploy.py "$@"
```

## 📚 Additional Resources

- [AWS CLI Configuration](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html)
- [AWS Profiles](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html)
- [IAM Best Practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html)
- [AWS SSO](https://docs.aws.amazon.com/singlesignon/latest/userguide/what-is.html)

