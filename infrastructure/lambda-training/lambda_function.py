"""Lambda: trigger SageMaker training job. Requires code at s3://bucket/code/sourcedir.tar.gz"""
import os
import json
import boto3
from datetime import datetime

def lambda_handler(event, context):
    role = os.environ["SAGEMAKER_ROLE"]
    bucket = os.environ["BUCKET_NAME"]
    region = os.environ.get("AWS_REGION", "us-east-1")
    job_name = f"album-classifier-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    code_uri = f"s3://{bucket}/code/sourcedir.tar.gz"

    sm = boto3.client("sagemaker", region_name=region)
    sm.create_training_job(
        TrainingJobName=job_name,
        RoleArn=role,
        AlgorithmSpecification={
            "TrainingImage": "763104351884.dkr.ecr.us-east-1.amazonaws.com/pytorch-training:2.5.0-cpu-py311",
            "TrainingInputMode": "File",
        },
        InputDataConfig=[
            {
                "ChannelName": "training",
                "DataSource": {
                    "S3DataSource": {
                        "S3DataType": "S3Prefix",
                        "S3Uri": f"s3://{bucket}/data/",
                        "S3DataDistributionType": "FullyReplicated",
                    }
                },
            }
        ],
        OutputDataConfig={"S3OutputPath": f"s3://{bucket}/models/"},
        ResourceConfig={
            "InstanceType": event.get("instance_type", "ml.m5.xlarge"),
            "InstanceCount": 1,
            "VolumeSizeInGB": 50,
        },
        StoppingCondition={"MaxRuntimeInSeconds": 86400},
        HyperParameters={
            "sagemaker_submit_directory": code_uri,
            "sagemaker_program": "train.py",
            "epochs": str(event.get("epochs", 10)),
            "batch-size": str(event.get("batch_size", 16)),
            "learning-rate": str(event.get("learning_rate", 0.001)),
        },
    )
    return {"statusCode": 200, "body": json.dumps({"job_name": job_name})}
