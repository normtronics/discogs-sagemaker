# AWS Profile Guide

How to check and manage AWS profiles when running commands.

## Check Current Profile

### Method 1: Environment Variable

```bash
# Check if AWS_PROFILE is set
echo $AWS_PROFILE

# If empty, you're using the 'default' profile
```

### Method 2: AWS CLI Configuration

```bash
# Check which profile AWS CLI is using
aws configure list

# This shows:
# - Profile name (or 'default')
# - Access key ID
# - Region
# - Output format
```

### Method 3: Check Credentials File

```bash
# View all configured profiles
cat ~/.aws/credentials

# Or just see profile names
grep '\[' ~/.aws/credentials

# View config file (includes region settings)
cat ~/.aws/config
```

## List All Available Profiles

```bash
# List all profiles in credentials file
aws configure list-profiles

# Or manually:
grep '\[' ~/.aws/credentials | sed 's/\[//g' | sed 's/\]//g'
```

## Set Profile for Current Session

### Temporary (Current Terminal Session)

```bash
# Set profile for current session
export AWS_PROFILE=your-profile-name

# Verify it's set
aws configure list
```

### Permanent (Add to Shell Config)

Add to `~/.zshrc` or `~/.bashrc`:

```bash
export AWS_PROFILE=your-profile-name
```

Then reload:
```bash
source ~/.zshrc  # or source ~/.bashrc
```

## Use Specific Profile for Single Command

```bash
# Use specific profile for one command
aws s3 ls --profile your-profile-name

# Or with environment variable
AWS_PROFILE=your-profile-name aws s3 ls
```

## Check Profile in Different Contexts

### AWS CLI Commands

```bash
# Shows current profile and credentials
aws configure list

# Shows profile name explicitly
aws configure list | grep profile
```

### CDK Commands

```bash
# CDK uses AWS_PROFILE environment variable
echo $AWS_PROFILE

# Or check CDK context
cdk context

# CDK will use the profile from AWS_PROFILE or default
```

### Node.js / TypeScript

```bash
# Check in Node.js
node -e "console.log(process.env.AWS_PROFILE || 'default')"
```

## Common Profile Operations

### Create New Profile

```bash
# Interactive setup
aws configure --profile new-profile-name

# Or manually edit ~/.aws/credentials
```

### Switch Between Profiles

```bash
# Quick switch
export AWS_PROFILE=profile-1
aws s3 ls  # Uses profile-1

export AWS_PROFILE=profile-2
aws s3 ls  # Uses profile-2
```

### Check Profile for Specific Service

```bash
# Check which account/region you're using
aws sts get-caller-identity

# This shows:
# - Account ID
# - User/Role ARN
# - Profile (indirectly via account)
```

## Verify Profile is Working

```bash
# Test with a simple command
aws sts get-caller-identity

# Should return:
# {
#   "UserId": "...",
#   "Account": "...",
#   "Arn": "..."
# }
```

## Troubleshooting

### Profile Not Found

```bash
# Check if profile exists
aws configure list-profiles | grep your-profile-name

# If not found, create it:
aws configure --profile your-profile-name
```

### Wrong Profile Being Used

```bash
# Check current profile
echo $AWS_PROFILE

# Unset if needed
unset AWS_PROFILE

# Then AWS CLI will use 'default'
aws configure list
```

### Multiple Profile Sources

AWS CLI checks in this order:
1. `AWS_PROFILE` environment variable
2. `--profile` command-line flag
3. `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` (if set)
4. `default` profile in `~/.aws/credentials`
5. IAM role (if on EC2/ECS/Lambda)

## Quick Reference

```bash
# Check current profile
echo $AWS_PROFILE || echo "default"

# List all profiles
aws configure list-profiles

# View current config
aws configure list

# Set profile
export AWS_PROFILE=profile-name

# Use profile for one command
aws s3 ls --profile profile-name

# Verify identity
aws sts get-caller-identity
```

## Example Workflow

```bash
# 1. Check what profile you're using
aws configure list

# 2. List available profiles
aws configure list-profiles

# 3. Switch to different profile
export AWS_PROFILE=production

# 4. Verify switch worked
aws sts get-caller-identity

# 5. Run your command
aws sagemaker list-endpoints
```

---

**Tip**: Add `export AWS_PROFILE=your-profile-name` to your `~/.zshrc` or `~/.bashrc` to set it permanently for your terminal sessions.
