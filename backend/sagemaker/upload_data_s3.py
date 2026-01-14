#!/usr/bin/env python3
"""
Upload training data to S3
Prepares data for SageMaker training
"""
import os
import sys
import boto3
import argparse
from pathlib import Path
from dotenv import load_dotenv
from botocore.exceptions import ClientError


def load_config():
    """Load configuration from env.local"""
    # __file__ is backend/sagemaker/upload_data_s3.py
    # parent is backend/sagemaker/, parent.parent is backend/
    backend_root = Path(__file__).parent.parent
    env_path = backend_root / '.env.local'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded configuration from {env_path}")
    else:
        print(f"Warning: {env_path} not found")


def check_local_data(data_dir):
    """Check if local data exists"""
    data_path = Path(data_dir)  # This is backend/data/
    backend_root = data_path.parent  # This is backend/
    project_root = backend_root.parent  # This is project root
    
    # Check for images in backend/data/images
    images_dir = data_path / 'images'
    if not images_dir.exists():
        print(f"✗ Images directory not found: {images_dir}")
        return False
    
    image_files = list(images_dir.glob('*.jpg'))
    if not image_files:
        print(f"✗ No images found in {images_dir}")
        return False
    
    print(f"✓ Found {len(image_files)} images in {images_dir}")
    
    # Check for manifest in project_root/data/
    possible_manifests = [
        project_root / 'data' / 'releases_manifest_enriched.jsonl',
        project_root / 'data' / 'releases_manifest.jsonl',
        project_root / 'data' / 'releases_metadata.jsonl',
        project_root / 'data' / 'releases_manifest_50.jsonl',
    ]
    
    manifest_path = None
    for path in possible_manifests:
        if path.exists():
            manifest_path = path
            break
    
    if not manifest_path:
        print(f"✗ Manifest file not found")
        print(f"  Looked for:")
        for path in possible_manifests:
            print(f"    - {path}")
        return False
    
    print(f"✓ Found manifest: {manifest_path}")
    
    return True


def upload_to_s3(local_dir, bucket, s3_prefix, region='us-east-1'):
    """Upload directory to S3"""
    print(f"\n{'='*60}")
    print("Uploading to S3")
    print(f"{'='*60}")
    
    s3_client = boto3.client('s3', region_name=region)
    
    # Check if bucket exists
    try:
        s3_client.head_bucket(Bucket=bucket)
        print(f"✓ Bucket '{bucket}' accessible")
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"✗ Bucket '{bucket}' not found")
            print(f"\nCreate it with:")
            print(f"  aws s3 mb s3://{bucket} --region {region}")
            return False
        else:
            print(f"✗ Error accessing bucket: {e}")
            return False
    
    local_path = Path(local_dir)
    uploaded_files = 0
    total_size = 0
    
    # Upload all files
    for file_path in local_path.rglob('*'):
        if file_path.is_file():
            # Calculate relative path
            relative_path = file_path.relative_to(local_path)
            s3_key = f"{s3_prefix}/{relative_path}".replace('\\', '/')
            
            # Upload file
            try:
                file_size = file_path.stat().st_size
                print(f"Uploading {relative_path} ({file_size / 1024:.1f} KB)...")
                
                s3_client.upload_file(
                    str(file_path),
                    bucket,
                    s3_key,
                    ExtraArgs={'ServerSideEncryption': 'AES256'}
                )
                
                uploaded_files += 1
                total_size += file_size
                
            except Exception as e:
                print(f"✗ Error uploading {relative_path}: {e}")
                return False
    
    print(f"\n{'='*60}")
    print("Upload Complete!")
    print(f"{'='*60}")
    print(f"Files uploaded: {uploaded_files}")
    print(f"Total size: {total_size / (1024*1024):.2f} MB")
    print(f"S3 location: s3://{bucket}/{s3_prefix}/")
    print(f"\nVerify with:")
    print(f"  aws s3 ls s3://{bucket}/{s3_prefix}/ --recursive")
    
    return True


def main():
    parser = argparse.ArgumentParser(description='Upload training data to S3')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='Local data directory (default: backend/data)')
    parser.add_argument('--bucket', type=str, default=None,
                        help='S3 bucket name (default: from env)')
    parser.add_argument('--prefix', type=str, default='album-classifier/data',
                        help='S3 prefix (default: album-classifier/data)')
    parser.add_argument('--region', type=str, default=None,
                        help='AWS region (default: from env or us-east-1)')
    
    args = parser.parse_args()
    
    # Load config
    load_config()
    
    # Set defaults from environment
    if args.data_dir is None:
        # __file__ is backend/sagemaker/upload_data_s3.py
        # parent is backend/sagemaker/, parent.parent is backend/
        backend_root = Path(__file__).parent.parent
        args.data_dir = str(backend_root / 'data')
    
    data_path = Path(args.data_dir)
    backend_root = data_path.parent  # backend/ (parent of data/)
    project_root = backend_root.parent  # project root
    
    if args.bucket is None:
        args.bucket = os.getenv('BUCKET_NAME') or os.getenv('SAGEMAKER_BUCKET')
        if not args.bucket:
            print("✗ Error: BUCKET_NAME not set in .env.local")
            print("\nSet it with:")
            print("  export BUCKET_NAME=your-bucket-name")
            sys.exit(1)
    
    if args.region is None:
        args.region = os.getenv('AWS_REGION', 'us-east-1')
    
    print(f"\n{'='*60}")
    print("S3 Data Upload Configuration")
    print(f"{'='*60}")
    print(f"Local directory: {args.data_dir}")
    print(f"S3 bucket: {args.bucket}")
    print(f"S3 prefix: {args.prefix}")
    print(f"Region: {args.region}")
    
    # Check local data
    print(f"\n{'='*60}")
    print("Checking Local Data")
    print(f"{'='*60}")
    
    if not check_local_data(args.data_dir):
        print("\n✗ Please download training data first")
        print("\nRun:")
        print("  cd backend")
        print("  python main.py  # Start API")
        print("  curl -X POST http://localhost:8000/api/download-images")
        sys.exit(1)
    
    # Create a temporary directory structure for upload that combines both locations
    import tempfile
    import shutil
    
    print(f"\n{'='*60}")
    print("Preparing Data for Upload")
    print(f"{'='*60}\n")
    
    # Create temp directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_data = Path(temp_dir) / 'data'
        temp_data.mkdir()
        
        # Copy images from backend/data/images to temp/data/images
        images_src = data_path / 'images'
        images_dst = temp_data / 'images'
        print(f"Copying images from {images_src}...")
        shutil.copytree(images_src, images_dst)
        
        # Copy manifest from project_root/data/ to temp/data/
        manifest_src = None
        for name in ['releases_manifest_enriched.jsonl', 'releases_manifest.jsonl', 
                     'releases_metadata.jsonl', 'releases_manifest_50.jsonl']:
            path = project_root / 'data' / name
            if path.exists():
                manifest_src = path
                break
        
        if manifest_src:
            manifest_dst = temp_data / 'releases_manifest.jsonl'
            print(f"Copying manifest from {manifest_src}...")
            shutil.copy(manifest_src, manifest_dst)
        
        print(f"✓ Prepared data in {temp_data}\n")
        
        # Upload to S3
        success = upload_to_s3(str(temp_data), args.bucket, args.prefix, args.region)
    
    if success:
        print(f"\n{'='*60}")
        print("Next Steps")
        print(f"{'='*60}")
        print("\n1. Train model on SageMaker:")
        print("   python sagemaker/deploy.py --epochs 10")
        print("\n2. Or train locally first:")
        print("   python sagemaker/local_train.py --epochs 5")
    else:
        sys.exit(1)


if __name__ == '__main__':
    main()

