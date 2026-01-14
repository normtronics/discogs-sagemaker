#!/usr/bin/env python3
"""
Comprehensive SageMaker Training Script
Downloads images, uploads to S3, trains model, and optionally deploys

This script combines:
1. Image downloading from manifest URLs
2. Uploading images to S3
3. Model training
4. Model deployment (optional)
"""
import os
import json
import argparse
import asyncio
import aiohttp
import boto3
import sagemaker
from pathlib import Path
from typing import List, Dict
from PIL import Image
from io import BytesIO
from datetime import datetime
from botocore.exceptions import ClientError

import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from sklearn.model_selection import train_test_split

# Import training functions from train.py
import sys
sys.path.insert(0, os.path.dirname(__file__))
from train import (
    load_releases_data, create_datasets, create_model,
    train_epoch, validate
)


class ImageDownloader:
    """Download images from URLs in manifest"""
    
    def __init__(self, max_concurrent=10):
        self.max_concurrent = max_concurrent
        self.stats = {
            'downloaded': 0,
            'failed': 0,
            'skipped': 0
        }
    
    async def download_single_image(
        self,
        session: aiohttp.ClientSession,
        idx: int,
        image_url: str,
        save_path: str
    ) -> bool:
        """Download a single image"""
        try:
            # Skip if already exists
            if os.path.exists(save_path):
                return True
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "image/*",
                "Referer": "https://www.discogs.com/"
            }
            
            async with session.get(image_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Verify it's a valid image
                    img = Image.open(BytesIO(content))
                    img.verify()
                    
                    # Convert to RGB and save
                    img = Image.open(BytesIO(content)).convert("RGB")
                    img.save(save_path, "JPEG", quality=90)
                    
                    return True
                else:
                    print(f"Failed {idx}: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            print(f"Error {idx}: {str(e)[:50]}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return False
    
    async def download_images(self, releases: List[Dict], images_dir: str):
        """Download all images from releases"""
        Path(images_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"\n{'='*60}")
        print("Downloading Images")
        print(f"{'='*60}")
        print(f"Total releases: {len(releases)}")
        print(f"Images directory: {images_dir}\n")
        
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_download(idx, image_url, save_path):
            async with semaphore:
                success = await self.download_single_image(session, idx, image_url, save_path)
                if success:
                    self.stats['downloaded'] += 1
                else:
                    self.stats['failed'] += 1
                return success
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            
            for idx, release in enumerate(releases):
                image_url = release.get('cover_image') or release.get('thumb')
                if not image_url:
                    self.stats['failed'] += 1
                    continue
                
                save_path = os.path.join(images_dir, f"{idx}.jpg")
                
                # Skip if already exists
                if os.path.exists(save_path):
                    self.stats['skipped'] += 1
                    continue
                
                task = bounded_download(idx, image_url, save_path)
                tasks.append(task)
                
                # Print progress every 100 images
                if len(tasks) % 100 == 0:
                    print(f"Queued {len(tasks)} downloads...")
            
            # Execute downloads
            print(f"\nDownloading {len(tasks)} images...")
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            successful = sum(1 for r in results if r is True)
            print(f"\nDownload complete: {successful}/{len(tasks)} successful")
        
        return self.stats


class S3Uploader:
    """Upload images to S3"""
    
    def __init__(self, bucket: str, prefix: str, region: str = 'us-east-1'):
        self.bucket = bucket
        self.prefix = prefix
        self.region = region
        self.s3_client = boto3.client('s3', region_name=region)
    
    def upload_directory(self, local_dir: str):
        """Upload directory to S3"""
        print(f"\n{'='*60}")
        print("Uploading to S3")
        print(f"{'='*60}")
        print(f"Bucket: {self.bucket}")
        print(f"Prefix: {self.prefix}")
        print(f"Local directory: {local_dir}\n")
        
        local_path = Path(local_dir)
        uploaded_files = 0
        total_size = 0
        
        # Upload all files
        for file_path in local_path.rglob('*'):
            if file_path.is_file():
                # Calculate relative path
                relative_path = file_path.relative_to(local_path)
                s3_key = f"{self.prefix}/{relative_path}".replace('\\', '/')
                
                # Upload file
                try:
                    file_size = file_path.stat().st_size
                    if uploaded_files % 100 == 0:
                        print(f"Uploading {relative_path} ({file_size / 1024:.1f} KB)...")
                    
                    self.s3_client.upload_file(
                        str(file_path),
                        self.bucket,
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
        print(f"S3 location: s3://{self.bucket}/{self.prefix}/")
        
        return True


def download_and_upload_images(
    releases: List[Dict],
    images_dir: str,
    bucket: str,
    s3_prefix: str,
    region: str = 'us-east-1',
    max_concurrent: int = 10
):
    """Download images and upload to S3"""
    print(f"\n{'='*60}")
    print("Step 1: Download Images")
    print(f"{'='*60}")
    
    # Download images
    downloader = ImageDownloader(max_concurrent=max_concurrent)
    stats = asyncio.run(downloader.download_images(releases, images_dir))
    
    print(f"\nDownload Statistics:")
    print(f"  Downloaded: {stats['downloaded']}")
    print(f"  Failed: {stats['failed']}")
    print(f"  Skipped: {stats['skipped']}")
    
    # Upload to S3
    print(f"\n{'='*60}")
    print("Step 2: Upload Images to S3")
    print(f"{'='*60}")
    
    uploader = S3Uploader(bucket, s3_prefix, region)
    success = uploader.upload_directory(images_dir)
    
    if not success:
        raise RuntimeError("Failed to upload images to S3")
    
    return stats


def train_model(
    releases: List[Dict],
    images_dir: str,
    model_dir: str,
    epochs: int = 10,
    batch_size: int = 8,
    learning_rate: float = 0.001,
    test_size: float = 0.2,
    num_workers: int = 0
):
    """Train the model"""
    print(f"\n{'='*60}")
    print("Step 3: Train Model")
    print(f"{'='*60}")
    
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Create datasets
    print(f"Creating datasets from {images_dir}...")
    train_dataset, val_dataset = create_datasets(images_dir, releases, test_size=test_size)
    
    # Create data loaders
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=num_workers)
    
    print(f"Training samples: {len(train_dataset)}, Validation samples: {len(val_dataset)}")
    
    # Create model
    num_classes = len(releases)
    model = create_model(num_classes)
    model = model.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)
    
    # Training loop
    best_acc = 0.0
    best_model_path = os.path.join(model_dir, 'model.pth')
    os.makedirs(model_dir, exist_ok=True)
    
    for epoch in range(epochs):
        print(f"\nEpoch {epoch + 1}/{epochs}")
        print("-" * 50)
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        
        # Validate
        val_loss, val_acc = validate(model, val_loader, criterion, device)
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
        
        # Save best model
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print(f"✓ Model saved with accuracy: {best_acc:.2f}%")
        
        scheduler.step()
    
    # Save final model
    torch.save(model.state_dict(), best_model_path)
    
    # Save model metadata
    metadata = {
        "num_classes": num_classes,
        "best_val_accuracy": best_acc,
        "epochs": epochs,
        "train_size": len(train_dataset),
        "val_size": len(val_dataset),
        "releases": releases
    }
    
    metadata_path = os.path.join(model_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nTraining completed!")
    print(f"Best validation accuracy: {best_acc:.2f}%")
    print(f"Model saved to: {best_model_path}")
    
    return best_acc


def deploy_model(
    model_dir: str,
    bucket: str,
    endpoint_name: str,
    instance_type: str = 'ml.m5.large',
    role: str = None,
    region: str = 'us-east-1'
):
    """Deploy model to SageMaker endpoint"""
    print(f"\n{'='*60}")
    print("Step 4: Deploy Model")
    print(f"{'='*60}")
    
    if not role:
        role = os.getenv('SAGEMAKER_ROLE')
        if not role:
            print("Warning: SAGEMAKER_ROLE not set, skipping deployment")
            return None
    
    # Initialize SageMaker session
    boto_session = boto3.Session(region_name=region)
    sagemaker_session = sagemaker.Session(boto_session=boto_session)
    
    # Upload model to S3
    model_s3_path = f"s3://{bucket}/album-classifier/models/{endpoint_name}/model.tar.gz"
    
    print(f"Uploading model to {model_s3_path}...")
    # Create model.tar.gz
    import tarfile
    import tempfile
    
    with tempfile.TemporaryDirectory() as temp_dir:
        model_tar = os.path.join(temp_dir, 'model.tar.gz')
        with tarfile.open(model_tar, 'w:gz') as tar:
            tar.add(model_dir, arcname='.')
        
        s3_client = boto3.client('s3', region_name=region)
        bucket_name = bucket
        s3_key = f"album-classifier/models/{endpoint_name}/model.tar.gz"
        s3_client.upload_file(model_tar, bucket_name, s3_key)
    
    # Deploy using PyTorchModel
    from sagemaker.pytorch import PyTorchModel
    
    # Get source directory for inference code
    source_dir = os.path.dirname(__file__)
    
    model = PyTorchModel(
        model_data=model_s3_path,
        role=role,
        entry_point='inference.py',
        source_dir=source_dir,
        framework_version='2.5.1',
        py_version='py311',
        sagemaker_session=sagemaker_session
    )
    
    print(f"Deploying to endpoint: {endpoint_name}")
    predictor = model.deploy(
        initial_instance_count=1,
        instance_type=instance_type,
        endpoint_name=endpoint_name
    )
    
    print(f"\n{'='*60}")
    print("Deployment Complete!")
    print(f"{'='*60}")
    print(f"Endpoint Name: {endpoint_name}")
    print(f"Endpoint ARN: {predictor.endpoint_name}")
    
    return predictor


def main():
    """Main pipeline function"""
    parser = argparse.ArgumentParser(description='Full pipeline: download, upload, train, deploy')
    
    # Data paths
    parser.add_argument('--manifest-path', type=str, default=None,
                        help='Path to manifest file (local or S3, default: from SM_CHANNEL_TRAINING)')
    parser.add_argument('--images-dir', type=str, default='/opt/ml/input/data/training/images',
                        help='Local directory for images')
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', '/opt/ml/model'),
                        help='Directory to save model')
    
    # S3 configuration
    parser.add_argument('--bucket', type=str, default=None,
                        help='S3 bucket name (default: from env)')
    parser.add_argument('--s3-prefix', type=str, default='album-classifier/data',
                        help='S3 prefix for images')
    parser.add_argument('--region', type=str, default='us-east-1',
                        help='AWS region')
    
    # Download settings
    parser.add_argument('--max-concurrent', type=int, default=10,
                        help='Max concurrent downloads')
    parser.add_argument('--skip-download', type=str, default='false',
                        help='Skip image download (true/false, for SageMaker hyperparameters)')
    parser.add_argument('--skip-upload', type=str, default='false',
                        help='Skip S3 upload (true/false, for SageMaker hyperparameters)')
    
    # Training settings
    parser.add_argument('--skip-training', type=str, default='false',
                        help='Skip training (true/false, for SageMaker hyperparameters)')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=8,
                        help='Training batch size')
    parser.add_argument('--learning-rate', type=float, default=0.001,
                        help='Learning rate')
    parser.add_argument('--test-size', type=float, default=0.2,
                        help='Validation set size')
    parser.add_argument('--num-workers', type=int, default=0,
                        help='Number of data loader workers')
    
    # Deployment settings
    parser.add_argument('--skip-deploy', type=str, default='false',
                        help='Skip deployment (true/false, for SageMaker hyperparameters)')
    parser.add_argument('--endpoint-name', type=str, default=None,
                        help='Endpoint name (auto-generated if not provided)')
    parser.add_argument('--endpoint-instance-type', type=str, default='ml.m5.large',
                        help='Instance type for endpoint')
    
    args = parser.parse_args()
    
    # Convert string flags to boolean (for SageMaker hyperparameters)
    args.skip_download = args.skip_download.lower() == 'true'
    args.skip_upload = args.skip_upload.lower() == 'true'
    args.skip_training = args.skip_training.lower() == 'true'
    args.skip_deploy = args.skip_deploy.lower() == 'true'
    
    # Set defaults from environment
    if args.bucket is None:
        args.bucket = os.getenv('BUCKET_NAME') or os.getenv('SAGEMAKER_BUCKET')
        if not args.bucket:
            raise ValueError("BUCKET_NAME must be set in environment or --bucket argument")
    
    if args.endpoint_name is None:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        args.endpoint_name = f'album-classifier-{timestamp}'
    
    print(f"\n{'='*60}")
    print("Full Pipeline: Download, Upload, Train, Deploy")
    print(f"{'='*60}")
    print(f"Manifest: {args.manifest_path}")
    print(f"Images directory: {args.images_dir}")
    print(f"Model directory: {args.model_dir}")
    print(f"S3 bucket: {args.bucket}")
    print(f"S3 prefix: {args.s3_prefix}")
    print(f"Region: {args.region}")
    
    # Load manifest
    print(f"\n{'='*60}")
    print("Loading Manifest")
    print(f"{'='*60}")
    
    # Determine manifest path
    if args.manifest_path is None:
        # Try to find manifest in SageMaker training channel or default locations
        training_channel = os.environ.get('SM_CHANNEL_TRAINING', '/opt/ml/input/data/training')
        possible_manifests = [
            os.path.join(training_channel, 'releases_manifest_enriched.jsonl'),
            os.path.join(training_channel, 'releases_manifest.jsonl'),
            os.path.join(training_channel, 'releases_metadata.jsonl'),
            os.path.join(training_channel, 'releases_manifest_50.jsonl'),
        ]
        
        manifest_path = None
        for path in possible_manifests:
            if os.path.exists(path):
                manifest_path = path
                break
        
        if manifest_path is None:
            raise ValueError(f"Manifest file not found. Tried: {possible_manifests}")
        
        args.manifest_path = manifest_path
    
    # Load manifest
    if args.manifest_path.startswith('s3://'):
        # Download from S3
        import tempfile
        s3_client = boto3.client('s3', region_name=args.region)
        bucket_name, key = args.manifest_path.replace('s3://', '').split('/', 1)
        
        with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.jsonl') as f:
            temp_path = f.name
            s3_client.download_file(bucket_name, key, temp_path)
            releases = load_releases_data(temp_path)
            os.unlink(temp_path)
    else:
        releases = load_releases_data(args.manifest_path)
    
    print(f"Loaded {len(releases)} releases")
    
    # Step 1: Download images
    if not args.skip_download:
        # Download images
        print(f"\n{'='*60}")
        print("Step 1: Download Images")
        print(f"{'='*60}")
        
        downloader = ImageDownloader(max_concurrent=args.max_concurrent)
        stats = asyncio.run(downloader.download_images(releases, args.images_dir))
        
        print(f"\nDownload Statistics:")
        print(f"  Downloaded: {stats['downloaded']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Skipped: {stats['skipped']}")
        
        # Upload to S3
        if not args.skip_upload:
            print(f"\n{'='*60}")
            print("Step 2: Upload Images to S3")
            print(f"{'='*60}")
            
            uploader = S3Uploader(args.bucket, args.s3_prefix, args.region)
            success = uploader.upload_directory(args.images_dir)
            
            if not success:
                raise RuntimeError("Failed to upload images to S3")
    elif not args.skip_upload:
        # Only upload if images already exist
        print(f"\n{'='*60}")
        print("Step 1: Upload Images to S3")
        print(f"{'='*60}")
        
        uploader = S3Uploader(args.bucket, args.s3_prefix, args.region)
        success = uploader.upload_directory(args.images_dir)
        
        if not success:
            raise RuntimeError("Failed to upload images to S3")
    
    # Step 2/3: Train model
    if not args.skip_training:
        train_model(
            releases=releases,
            images_dir=args.images_dir,
            model_dir=args.model_dir,
            epochs=args.epochs,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            test_size=args.test_size,
            num_workers=args.num_workers
        )
    
    # Step 3/4: Deploy model (optional - note: deployment from training job may have limitations)
    if not args.skip_deploy:
        print(f"\n{'='*60}")
        print("Note: Deployment from training job")
        print(f"{'='*60}")
        print("Deployment is better handled separately after training completes.")
        print("Model artifacts are saved to:", args.model_dir)
        print("To deploy manually, use:")
        print(f"  python sagemaker/deploy.py --model-path {args.model_dir}")
        
        # Optionally attempt deployment (may fail due to permissions/timeout)
        try:
            deploy_model(
                model_dir=args.model_dir,
                bucket=args.bucket,
                endpoint_name=args.endpoint_name,
                instance_type=args.endpoint_instance_type,
                region=args.region
            )
        except Exception as e:
            print(f"Warning: Deployment failed: {e}")
            print("Model artifacts are saved and can be deployed separately.")
    
    print(f"\n{'='*60}")
    print("Pipeline Complete!")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()

