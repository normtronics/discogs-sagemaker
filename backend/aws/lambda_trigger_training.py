"""
AWS Lambda Function: Trigger SageMaker Training Job

Deploy this as a Lambda function to trigger training jobs
Can be invoked by EventBridge, API Gateway, or manually
"""
import os
import json
import boto3
from datetime import datetime


def lambda_handler(event, context):
    """
    Lambda handler to trigger SageMaker training job
    
    Environment Variables Required:
        - SAGEMAKER_ROLE: SageMaker execution role ARN
        - SAGEMAKER_BUCKET: S3 bucket for data/models
        - AWS_REGION: AWS region (default: us-east-1)
    
    Event Parameters (optional):
        - instance_type: EC2 instance type (default: ml.p3.2xlarge)
        - epochs: Training epochs (default: 10)
        - batch_size: Batch size (default: 16)
        - learning_rate: Learning rate (default: 0.001)
    """
    
    # Get configuration from environment
    role = os.environ.get('SAGEMAKER_ROLE')
    bucket = os.environ.get('BUCKET_NAME') or os.environ.get('SAGEMAKER_BUCKET')
    region = os.environ.get('AWS_REGION', 'us-east-1')
    
    if not role or not bucket:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'SAGEMAKER_ROLE and BUCKET_NAME must be set'
            })
        }
    
    # Extract parameters from event
    instance_type = event.get('instance_type', 'ml.p3.2xlarge')
    epochs = int(event.get('epochs', 10))
    batch_size = int(event.get('batch_size', 16))
    learning_rate = float(event.get('learning_rate', 0.001))
    
    # Generate unique job name
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    job_name = f'album-classifier-{timestamp}'
    
    # Configure training job
    training_config = {
        'TrainingJobName': job_name,
        'RoleArn': role,
        'AlgorithmSpecification': {
            'TrainingImage': get_training_image(region),
            'TrainingInputMode': 'File',
            'EnableSageMakerMetricsTimeSeries': True
        },
        'InputDataConfig': [
            {
                'ChannelName': 'training',
                'DataSource': {
                    'S3DataSource': {
                        'S3DataType': 'S3Prefix',
                        'S3Uri': f's3://{bucket}/album-classifier/data',
                        'S3DataDistributionType': 'FullyReplicated'
                    }
                },
                'ContentType': 'application/x-image',
                'CompressionType': 'None'
            }
        ],
        'OutputDataConfig': {
            'S3OutputPath': f's3://{bucket}/album-classifier/models'
        },
        'ResourceConfig': {
            'InstanceType': instance_type,
            'InstanceCount': 1,
            'VolumeSizeInGB': 50
        },
        'StoppingCondition': {
            'MaxRuntimeInSeconds': 86400  # 24 hours
        },
        'HyperParameters': {
            'epochs': str(epochs),
            'batch-size': str(batch_size),
            'learning-rate': str(learning_rate),
            'sagemaker_program': 'train.py',
            'sagemaker_submit_directory': f's3://{bucket}/album-classifier/code/sourcedir.tar.gz'
        },
        'EnableManagedSpotTraining': True,  # Use spot instances for cost savings
        'CheckpointConfig': {
            'S3Uri': f's3://{bucket}/album-classifier/checkpoints'
        }
    }
    
    # Start training job
    try:
        sagemaker_client = boto3.client('sagemaker', region_name=region)
        response = sagemaker_client.create_training_job(**training_config)
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Training job started successfully',
                'job_name': job_name,
                'training_job_arn': response['TrainingJobArn']
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': f'Failed to start training job: {str(e)}'
            })
        }


def get_training_image(region):
    """Get PyTorch training image URI for region"""
    # PyTorch 2.5.0 image URIs by region
    image_uris = {
        'us-east-1': '763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-gpu-py311',
        'us-west-2': '763104351884.dkr.ecr.us-west-2.amazonaws.com/pytorch-training:2.5.0-gpu-py311',
        'eu-west-1': '763104351884.dkr.ecr.eu-west-1.amazonaws.com/pytorch-training:2.5.0-gpu-py311',
    }
    
    return image_uris.get(region, image_uris['us-east-1'])

