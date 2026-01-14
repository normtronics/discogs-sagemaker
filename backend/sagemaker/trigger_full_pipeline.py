#!/usr/bin/env python3
"""
Trigger Full Pipeline SageMaker Training Job
Downloads images, uploads to S3, trains model, and deploys
"""
import os
import json
import argparse
import boto3
import sagemaker
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv


def load_config():
    """Load configuration from env.local"""
    backend_root = Path(__file__).parent.parent
    env_path = backend_root / '.env.local'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded configuration from {env_path}")
    else:
        print(f"Warning: {env_path} not found, using environment variables")


def create_full_pipeline_job(
    job_name=None,
    manifest_path=None,
    instance_type='ml.p3.2xlarge',
    instance_count=1,
    epochs=10,
    batch_size=16,
    learning_rate=0.001,
    max_concurrent_downloads=10,
    skip_download=False,
    skip_upload=False,
    skip_training=False,
    skip_deploy=False,
    endpoint_instance_type='ml.m5.large',
    region=None,
    role=None,
    bucket=None,
    wait=False
):
    """
    Create and start a full pipeline SageMaker training job
    
    Args:
        job_name: Unique name for training job (auto-generated if None)
        manifest_path: Path to manifest file (S3 or local)
        instance_type: EC2 instance type for training
        instance_count: Number of instances
        epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate
        max_concurrent_downloads: Max concurrent image downloads
        skip_download: Skip image download step
        skip_upload: Skip S3 upload step
        skip_training: Skip training step
        skip_deploy: Skip deployment step
        endpoint_instance_type: Instance type for endpoint
        region: AWS region
        role: SageMaker execution role ARN
        bucket: S3 bucket for data/models
        wait: Wait for job completion
    
    Returns:
        Training job name and status
    """
    # Set defaults
    region = region or os.getenv('AWS_REGION', 'us-east-1')
    role = role or os.getenv('SAGEMAKER_ROLE')
    bucket = bucket or os.getenv('BUCKET_NAME') or os.getenv('SAGEMAKER_BUCKET')
    
    if not role:
        raise ValueError("SAGEMAKER_ROLE not set in environment")
    if not bucket:
        raise ValueError("BUCKET_NAME not set in environment")
    
    # Generate job name if not provided
    if job_name is None:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        job_name = f'album-classifier-full-{timestamp}'
    
    # Set default manifest path if not provided
    if manifest_path is None:
        # Try to find manifest in S3 or use default
        manifest_path = f's3://{bucket}/album-classifier/data/releases_manifest_enriched.jsonl'
    
    # Initialize SageMaker session
    boto_session = boto3.Session(region_name=region)
    sagemaker_session = sagemaker.Session(boto_session=boto_session)
    
    # Configure paths
    data_uri = f's3://{bucket}/album-classifier/data'
    output_uri = f's3://{bucket}/album-classifier/models'
    code_uri = f's3://{bucket}/album-classifier/code'
    
    # Get PyTorch image URI
    from sagemaker.pytorch import PyTorch
    
    # Create estimator
    estimator = PyTorch(
        entry_point='full_pipeline_train.py',
        source_dir=str(Path(__file__).parent),
        role=role,
        instance_type=instance_type,
        instance_count=instance_count,
        framework_version='2.5.1',
        py_version='py311',
        hyperparameters={
            'epochs': str(epochs),
            'batch-size': str(batch_size),
            'learning-rate': str(learning_rate),
            'manifest-path': manifest_path,
            'max-concurrent': str(max_concurrent_downloads),
            'skip-download': 'true' if skip_download else 'false',
            'skip-upload': 'true' if skip_upload else 'false',
            'skip-training': 'true' if skip_training else 'false',
            'skip-deploy': 'true' if skip_deploy else 'false',
            'endpoint-instance-type': endpoint_instance_type,
        },
        output_path=output_uri,
        code_location=code_uri,
        sagemaker_session=sagemaker_session,
        base_job_name='album-classifier-full',
        max_run=86400 * 2,  # 48 hours max (for large downloads)
        use_spot_instances=True,  # Use spot instances for cost savings
        max_wait=86400 * 2,  # Wait time for spot instances
        checkpoint_s3_uri=f's3://{bucket}/album-classifier/checkpoints',
        volume_size=100,  # Larger volume for image storage
    )
    
    print(f"Starting full pipeline training job: {job_name}")
    print(f"Instance type: {instance_type}")
    print(f"Manifest path: {manifest_path}")
    print(f"Data location: {data_uri}")
    print(f"Output location: {output_uri}")
    print(f"Hyperparameters:")
    print(f"  - Epochs: {epochs}")
    print(f"  - Batch size: {batch_size}")
    print(f"  - Learning rate: {learning_rate}")
    print(f"  - Max concurrent downloads: {max_concurrent_downloads}")
    print(f"  - Skip download: {skip_download}")
    print(f"  - Skip upload: {skip_upload}")
    print(f"  - Skip training: {skip_training}")
    print(f"  - Skip deploy: {skip_deploy}")
    
    # Start training
    estimator.fit(
        {'training': data_uri},
        job_name=job_name,
        wait=wait,
        logs='All' if wait else None
    )
    
    return {
        'job_name': estimator.latest_training_job.name,
        'status': 'InProgress' if not wait else 'Completed',
        'model_data': estimator.model_data if wait else None
    }


def main():
    """CLI interface for triggering full pipeline jobs"""
    parser = argparse.ArgumentParser(description='Trigger full pipeline SageMaker training job')
    
    parser.add_argument('--job-name', type=str, default=None,
                        help='Training job name (auto-generated if not provided)')
    parser.add_argument('--manifest-path', type=str, default=None,
                        help='Path to manifest file (S3 or local, default: S3)')
    parser.add_argument('--instance-type', type=str, default='ml.p3.2xlarge',
                        help='Instance type for training')
    parser.add_argument('--instance-count', type=int, default=1,
                        help='Number of instances')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=16,
                        help='Training batch size')
    parser.add_argument('--learning-rate', type=float, default=0.001,
                        help='Learning rate')
    parser.add_argument('--max-concurrent-downloads', type=int, default=10,
                        help='Max concurrent image downloads')
    
    # Skip flags
    parser.add_argument('--skip-download', action='store_true',
                        help='Skip image download step')
    parser.add_argument('--skip-upload', action='store_true',
                        help='Skip S3 upload step')
    parser.add_argument('--skip-training', action='store_true',
                        help='Skip training step')
    parser.add_argument('--skip-deploy', action='store_true',
                        help='Skip deployment step')
    
    parser.add_argument('--endpoint-instance-type', type=str, default='ml.m5.large',
                        help='Instance type for endpoint')
    parser.add_argument('--wait', action='store_true',
                        help='Wait for training to complete')
    parser.add_argument('--region', type=str, default=None,
                        help='AWS region')
    parser.add_argument('--role', type=str, default=None,
                        help='SageMaker execution role ARN')
    parser.add_argument('--bucket', type=str, default=None,
                        help='S3 bucket name')
    
    args = parser.parse_args()
    
    # Load configuration
    load_config()
    
    print("="*60)
    print("Triggering Full Pipeline SageMaker Training Job")
    print("="*60)
    
    # Create training job
    result = create_full_pipeline_job(
        job_name=args.job_name,
        manifest_path=args.manifest_path,
        instance_type=args.instance_type,
        instance_count=args.instance_count,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        max_concurrent_downloads=args.max_concurrent_downloads,
        skip_download=args.skip_download,
        skip_upload=args.skip_upload,
        skip_training=args.skip_training,
        skip_deploy=args.skip_deploy,
        endpoint_instance_type=args.endpoint_instance_type,
        region=args.region,
        role=args.role,
        bucket=args.bucket,
        wait=args.wait
    )
    
    print("\n" + "="*60)
    print("Full Pipeline Training Job Started!")
    print("="*60)
    print(f"Job Name: {result['job_name']}")
    print(f"Status: {result['status']}")
    
    if result.get('model_data'):
        print(f"Model Data: {result['model_data']}")
    
    print("\nMonitor progress:")
    print(f"  aws sagemaker describe-training-job --training-job-name {result['job_name']}")
    print("\nView logs:")
    print(f"  aws logs tail /aws/sagemaker/TrainingJobs/{result['job_name']} --follow")
    
    return result


if __name__ == '__main__':
    main()

