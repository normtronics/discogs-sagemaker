#!/bin/bash
# Prepare code and data for SageMaker Studio

set -e
BUCKET_NAME=${1:?Usage: ./prepare_for_studio.sh <bucket-name>}
REGION=${2:-us-east-1}

echo "Bucket: $BUCKET_NAME"
echo "Region: $REGION"

# Create bucket if needed
aws s3 ls "s3://$BUCKET_NAME" 2>/dev/null || aws s3 mb "s3://$BUCKET_NAME" --region "$REGION"

# Upload manifest
[ -f data/releases_manifest.jsonl ] && aws s3 cp data/releases_manifest.jsonl "s3://$BUCKET_NAME/data/releases_manifest.jsonl"

# Upload images
[ -d data/images ] && aws s3 sync data/images/ "s3://$BUCKET_NAME/data/images/" --exclude "*.DS_Store"

# Package and upload code (ml + data + entry points for SageMaker)
cd backend
TMP=$(mktemp -d)
cp -r ml data train.py inference.py "$TMP/"
cd "$TMP"
tar -czf sourcedir.tar.gz ml data train.py inference.py
aws s3 cp sourcedir.tar.gz "s3://$BUCKET_NAME/code/sourcedir.tar.gz"
rm -rf "$TMP"
cd - > /dev/null

echo "Done. S3: s3://$BUCKET_NAME/data/ and s3://$BUCKET_NAME/code/"
