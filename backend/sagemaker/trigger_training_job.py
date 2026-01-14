#!/usr/bin/env python3
"""
Trigger SageMaker Training Job
Can be called from Lambda, EventBridge, or CLI
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
    # __file__ is backend/sagemaker/trigger_training_job.py
    # parent is backend/sagemaker/, parent.parent is backend/
    backend_root = Path(__file__).parent.parent
    env_path = backend_root / '.env.local'
    
    if env_path.exists():
        load_dotenv(env_path)


def create_training_job(
    job_name=None,
    instance_type='ml.p3.2xlarge',
    instance_count=1,
    epochs=10,
    batch_size=16,
    learning_rate=0.001,
    region=None,
    role=None,
    bucket=None,
    wait=False
):
    """
    Create and start a SageMaker training job
    
    Args:
        job_name: Unique name for training job (auto-generated if None)
        instance_type: EC2 instance type for training
        instance_count: Number of instances
        epochs: Number of training epochs
        batch_size: Training batch size
        learning_rate: Learning rate
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
        job_name = f'album-classifier-{timestamp}'
    
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
        entry_point='train.py',
        source_dir=str(Path(__file__).parent),
        role=role,
        instance_type=instance_type,
        instance_count=instance_count,
        framework_version='2.5.1',  # Updated: 2.5.0 not supported
        py_version='py311',
        hyperparameters={
            'epochs': epochs,
            'batch-size': batch_size,
            'learning-rate': learning_rate,
        },
        output_path=output_uri,
        code_location=code_uri,
        sagemaker_session=sagemaker_session,
        base_job_name='album-classifier',
        max_run=86400,  # 24 hours max
        use_spot_instances=True,  # Use spot instances for cost savings
        max_wait=86400,  # Wait time for spot instances
        checkpoint_s3_uri=f's3://{bucket}/album-classifier/checkpoints',
    )
    
    print(f"Starting training job: {job_name}")
    print(f"Instance type: {instance_type}")
    print(f"Data location: {data_uri}")
    print(f"Output location: {output_uri}")
    print(f"Hyperparameters:")
    print(f"  - Epochs: {epochs}")
    print(f"  - Batch size: {batch_size}")
    print(f"  - Learning rate: {learning_rate}")
    
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


def lambda_handler(event, context):
    """
    AWS Lambda handler for triggering training jobs
    
    Event format:
    {
        "instance_type": "ml.p3.2xlarge",
        "epochs": 10,
        "batch_size": 16,
        "learning_rate": 0.001
    }
    """
    load_config()
    
    # Extract parameters from event
    instance_type = event.get('instance_type', 'ml.p3.2xlarge')
    epochs = int(event.get('epochs', 10))
    batch_size = int(event.get('batch_size', 16))
    learning_rate = float(event.get('learning_rate', 0.001))
    
    try:
        result = create_training_job(
            instance_type=instance_type,
            epochs=epochs,
            batch_size=batch_size,
            learning_rate=learning_rate,
            wait=False
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Training job started successfully',
                'job_name': result['job_name'],
                'status': result['status']
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Failed to start training job',
                'error': str(e)
            })
        }


def main():
    """CLI interface for triggering training jobs"""
    parser = argparse.ArgumentParser(description='Trigger SageMaker training job')
    
    parser.add_argument('--job-name', type=str, default=None,
                        help='Training job name (auto-generated if not provided)')
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
    print("Triggering SageMaker Training Job")
    print("="*60)
    
    # Create training job
    result = create_training_job(
        job_name=args.job_name,
        instance_type=args.instance_type,
        instance_count=args.instance_count,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        region=args.region,
        role=args.role,
        bucket=args.bucket,
        wait=args.wait
    )
    
    print("\n" + "="*60)
    print("Training Job Started!")
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

