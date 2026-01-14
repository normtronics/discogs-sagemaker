"""
AWS Lambda Function: Trigger Full Pipeline SageMaker Training Job

Deploy this as a Lambda function to trigger the full pipeline training job
that downloads images, uploads to S3, trains model, and deploys.

Can be invoked by:
- EventBridge (scheduled)
- API Gateway (on-demand)
- Manual invocation
"""
import os
import json
import boto3
import sagemaker
import tempfile
import tarfile
from datetime import datetime
from pathlib import Path


def lambda_handler(event, context):
    """
    Lambda handler to trigger full pipeline SageMaker training job
    
    Environment Variables Required:
        - SAGEMAKER_ROLE: SageMaker execution role ARN
        - BUCKET_NAME or SAGEMAKER_BUCKET: S3 bucket for data/models
        - AWS_REGION: AWS region (default: us-east-1)
    
    Event Parameters (optional):
        - manifest_path: Path to manifest file in S3 (default: auto-detect)
        - instance_type: EC2 instance type (default: ml.p3.2xlarge)
        - epochs: Training epochs (default: 10)
        - batch_size: Batch size (default: 16)
        - learning_rate: Learning rate (default: 0.001)
        - max_concurrent_downloads: Concurrent downloads (default: 10)
        - skip_download: Skip download step (default: false)
        - skip_upload: Skip upload step (default: false)
        - skip_training: Skip training step (default: false)
        - skip_deploy: Skip deployment step (default: false)
        - endpoint_instance_type: Endpoint instance type (default: ml.m5.large)
    """
    
    # Get configuration from environment
    role = os.environ.get('SAGEMAKER_ROLE')
    bucket = os.environ.get('BUCKET_NAME') or os.environ.get('SAGEMAKER_BUCKET')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not role or not bucket:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'SAGEMAKER_ROLE and BUCKET_NAME must be set in environment variables'
            })
        }
    
    # Extract parameters from event
    manifest_path = event.get('manifest_path', f's3://{bucket}/album-classifier/data/releases_manifest_enriched.jsonl')
    instance_type = event.get('instance_type', 'ml.p3.2xlarge')
    epochs = int(event.get('epochs', 10))
    batch_size = int(event.get('batch_size', 16))
    learning_rate = float(event.get('learning_rate', 0.001))
    max_concurrent_downloads = int(event.get('max_concurrent_downloads', 10))
    skip_download = event.get('skip_download', False)
    skip_upload = event.get('skip_upload', False)
    skip_training = event.get('skip_training', False)
    skip_deploy = event.get('skip_deploy', False)
    endpoint_instance_type = event.get('endpoint_instance_type', 'ml.m5.large')
    
    # Generate unique job name
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    job_name = f'album-classifier-full-{timestamp}'
    
    try:
        # Initialize SageMaker session
        boto_session = boto3.Session(region_name=region)
        sagemaker_session = sagemaker.Session(boto_session=boto_session)
        
        # Configure paths
        data_uri = f's3://{bucket}/album-classifier/data'
        output_uri = f's3://{bucket}/album-classifier/models'
        code_uri = f's3://{bucket}/album-classifier/code'
        
        # Import PyTorch estimator
        from sagemaker.pytorch import PyTorch
        
        # Download source code from S3 to temporary directory
        # Source code should be uploaded via upload_source_to_s3.sh
        
        s3_client = boto3.client('s3', region_name=region)
        source_s3_path = f's3://{bucket}/album-classifier/source/source.tar.gz'
        
        # Create temporary directory for source code
        with tempfile.TemporaryDirectory() as temp_dir:
            source_tar_path = os.path.join(temp_dir, 'source.tar.gz')
            source_extract_path = os.path.join(temp_dir, 'source')
            
            # Download source code from S3
            try:
                s3_client.download_file(bucket, 'album-classifier/source/source.tar.gz', source_tar_path)
            except Exception as e:
                # If tar.gz doesn't exist, try downloading individual files
                # This is a fallback - prefer using upload_source_to_s3.sh
                return {
                    'statusCode': 500,
                    'body': json.dumps({
                        'error': f'Source code not found in S3. Please run upload_source_to_s3.sh first. Error: {str(e)}'
                    })
                }
            
            # Extract source code
            os.makedirs(source_extract_path, exist_ok=True)
            with tarfile.open(source_tar_path, 'r:gz') as tar:
                tar.extractall(source_extract_path)
            
            # Create estimator with local source directory
            estimator = PyTorch(
                entry_point='full_pipeline_train.py',
                source_dir=source_extract_path,
                role=role,
                instance_type=instance_type,
                instance_count=1,
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
                max_run=86400 * 2,  # 48 hours max
                use_spot_instances=True,
                max_wait=86400 * 2,
                checkpoint_s3_uri=f's3://{bucket}/album-classifier/checkpoints',
                volume_size=100,  # Larger volume for image storage
            )
            
            # Start training (this will upload source code automatically)
            estimator.fit(
                {'training': data_uri},
                job_name=job_name,
                wait=False  # Don't wait in Lambda
            )
        
        # Start training
        estimator.fit(
            {'training': data_uri},
            job_name=job_name,
            wait=False  # Don't wait in Lambda
        )
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Full pipeline training job started successfully',
                'job_name': job_name,
                'training_job_arn': estimator.latest_training_job.arn,
                'status': 'InProgress',
                'manifest_path': manifest_path,
                'instance_type': instance_type,
                'monitor_command': f'aws sagemaker describe-training-job --training-job-name {job_name}'
            })
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to start training job: {str(e)}',
                'type': type(e).__name__
            })
        }

