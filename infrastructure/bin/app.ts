#!/usr/bin/env node
import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { FullPipelineStack } from '../lib/full-pipeline-stack';
import { InferenceStack } from '../lib/inference-stack';

const app = new cdk.App();

// Get configuration from context or environment
const account = process.env.CDK_DEFAULT_ACCOUNT || process.env.AWS_ACCOUNT_ID;
const region = process.env.CDK_DEFAULT_REGION || process.env.AWS_REGION || 'us-east-1';
const bucketName = app.node.tryGetContext('bucketName') || process.env.BUCKET_NAME;
const sagemakerRoleArn = app.node.tryGetContext('sagemakerRoleArn') || process.env.SAGEMAKER_ROLE;
const endpointName = app.node.tryGetContext('endpointName') || process.env.SAGEMAKER_ENDPOINT_NAME;

// Full Pipeline Stack (for training)
if (bucketName && sagemakerRoleArn) {
  new FullPipelineStack(app, 'FullPipelineStack', {
    env: {
      account,
      region,
    },
    bucketName,
    sagemakerRoleArn,
    description: 'Full pipeline infrastructure for SageMaker training: download images, upload to S3, train model, deploy',
  });
}

// Inference Stack (for API Gateway + Lambda → SageMaker)
if (endpointName) {
  new InferenceStack(app, 'InferenceStack', {
    env: {
      account,
      region,
    },
    endpointName,
    sagemakerRoleArn, // Optional, for reference
    description: 'API Gateway + Lambda infrastructure for invoking SageMaker inference endpoint',
  });
}

app.synth();


