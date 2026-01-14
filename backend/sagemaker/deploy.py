#!/usr/bin/env python3
"""
Deploy model to SageMaker endpoint
Handles training jobs and endpoint deployment
"""
import os
import json
import argparse
import boto3
import sagemaker
from sagemaker.pytorch import PyTorch, PyTorchModel
from sagemaker.local import LocalSession
from pathlib import Path
from dotenv import load_dotenv


def load_config():
    """Load configuration from env.local"""
    # __file__ is backend/sagemaker/deploy.py
    # parent is backend/sagemaker/, parent.parent is backend/
    backend_root = Path(__file__).parent.parent
    env_path = backend_root / '.env.local'
    
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✓ Loaded configuration from {env_path}")
    else:
        print(f"Warning: {env_path} not found, using environment variables")


def get_sagemaker_session(local_mode=False):
    """Get SageMaker session"""
    if local_mode:
        return LocalSession()
    
    boto_session = boto3.Session(region_name=os.getenv('AWS_REGION', 'us-east-1'))
    return sagemaker.Session(boto_session=boto_session)


def create_training_job(args):
    """Create and run SageMaker training job"""
    print("=" * 60)
    print("Creating SageMaker Training Job")
    print("=" * 60)
    
    # Get session
    session = get_sagemaker_session(args.local_mode)
    role = os.getenv('SAGEMAKER_ROLE', 'arn:aws:iam::YOUR_ACCOUNT:role/SageMakerRole')
    
    if not args.local_mode and 'YOUR_ACCOUNT' in role:
        raise ValueError("Please set SAGEMAKER_ROLE in .env.local")
    
    # Setup paths
    # __file__ is backend/sagemaker/deploy.py
    # parent is backend/sagemaker/, parent.parent is backend/
    backend_root = Path(__file__).parent.parent
    source_dir = str(Path(__file__).parent)
    
    # S3 paths
    bucket = os.getenv('BUCKET_NAME') or os.getenv('SAGEMAKER_BUCKET')
    if not bucket and not args.local_mode:
        raise ValueError("Please set BUCKET_NAME in .env.local")
    
    if args.local_mode:
        data_path = f"file://{backend_root}/data"
        output_path = f"file://{backend_root}/sagemaker/output"
    else:
        data_path = f"s3://{bucket}/album-classifier/data"
        output_path = f"s3://{bucket}/album-classifier/output"
    
    print(f"\nConfiguration:")
    print(f"  Local Mode: {args.local_mode}")
    print(f"  Data Path: {data_path}")
    print(f"  Output Path: {output_path}")
    print(f"  Instance Type: {args.instance_type}")
    print(f"  Epochs: {args.epochs}")
    
    # Create PyTorch estimator
    estimator = PyTorch(
        entry_point='train.py',
        source_dir=source_dir,
        role=role,
        instance_type=args.instance_type,
        instance_count=1,
        framework_version='2.5.1',  # Updated: 2.5.0 not supported, use 2.5.1
        py_version='py311',
        hyperparameters={
            'epochs': args.epochs,
            'batch-size': args.batch_size,
            'learning-rate': args.learning_rate,
        },
        output_path=output_path,
        sagemaker_session=session,
    )
    
    # Start training
    print("\n" + "=" * 60)
    print("Starting Training Job...")
    print("=" * 60 + "\n")
    
    estimator.fit({'training': data_path}, wait=True)
    
    print("\n" + "=" * 60)
    print("Training Job Complete!")
    print("=" * 60)
    
    return estimator


def deploy_model(estimator, args):
    """Deploy model to SageMaker endpoint"""
    print("\n" + "=" * 60)
    print("Deploying Model to Endpoint")
    print("=" * 60)
    
    endpoint_name = args.endpoint_name
    if not endpoint_name:
        import time
        endpoint_name = f"album-classifier-{int(time.time())}"
    
    print(f"\nEndpoint Name: {endpoint_name}")
    print(f"Instance Type: {args.endpoint_instance_type}")
    
    # Deploy model
    predictor = estimator.deploy(
        initial_instance_count=1,
        instance_type=args.endpoint_instance_type,
        endpoint_name=endpoint_name,
    )
    
    print("\n" + "=" * 60)
    print("Deployment Complete!")
    print("=" * 60)
    print(f"Endpoint Name: {endpoint_name}")
    print(f"\nTo test the endpoint, run:")
    print(f"  python sagemaker/test_endpoint.py --endpoint {endpoint_name} --image path/to/image.jpg")
    
    return predictor


def main():
    parser = argparse.ArgumentParser(description='Deploy model to SageMaker')
    
    # Mode
    parser.add_argument('--local-mode', action='store_true',
                        help='Run in local mode (for testing)')
    
    # Training arguments
    parser.add_argument('--skip-training', action='store_true',
                        help='Skip training and only deploy existing model')
    parser.add_argument('--instance-type', type=str, default='ml.m5.xlarge',
                        help='Instance type for training')
    parser.add_argument('--epochs', type=int, default=10,
                        help='Number of training epochs')
    parser.add_argument('--batch-size', type=int, default=8,
                        help='Training batch size')
    parser.add_argument('--learning-rate', type=float, default=0.001,
                        help='Learning rate')
    
    # Deployment arguments
    parser.add_argument('--skip-deploy', action='store_true',
                        help='Skip deployment after training')
    parser.add_argument('--endpoint-name', type=str, default=None,
                        help='Name for the endpoint')
    parser.add_argument('--endpoint-instance-type', type=str, default='ml.m5.large',
                        help='Instance type for endpoint')
    
    args = parser.parse_args()
    
    # Load configuration
    load_config()
    
    # Override local mode settings
    if args.local_mode:
        args.instance_type = 'local'
        args.endpoint_instance_type = 'local'
    
    # Train model
    if not args.skip_training:
        estimator = create_training_job(args)
    else:
        print("Skipping training...")
        # TODO: Load existing model for deployment
        return
    
    # Deploy model
    if not args.skip_deploy:
        predictor = deploy_model(estimator, args)
    else:
        print("\nSkipping deployment...")
        print(f"Model artifacts saved to: {estimator.model_data}")


if __name__ == '__main__':
    main()

