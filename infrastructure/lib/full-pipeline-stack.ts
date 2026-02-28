import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as s3 from 'aws-cdk-lib/aws-s3';
import { Construct } from 'constructs';
import * as path from 'path';

export interface FullPipelineStackProps extends cdk.StackProps {
  bucketName: string;
  sagemakerRoleArn: string;
}

export class FullPipelineStack extends cdk.Stack {
  public readonly lambdaFunction: lambda.Function;
  public readonly eventBridgeRule: events.Rule;

  constructor(scope: Construct, id: string, props: FullPipelineStackProps) {
    super(scope, id, props);

    const { bucketName, sagemakerRoleArn } = props;

    // Reference existing S3 bucket or create new one
    const bucket = s3.Bucket.fromBucketName(this, 'S3Bucket', bucketName);

    // Lambda execution role
    const lambdaRole = new iam.Role(this, 'LambdaExecutionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Role for Lambda function to trigger SageMaker training jobs',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add SageMaker permissions
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'sagemaker:CreateTrainingJob',
        'sagemaker:DescribeTrainingJob',
        'sagemaker:StopTrainingJob',
        'sagemaker:CreateModel',
        'sagemaker:CreateEndpoint',
        'sagemaker:CreateEndpointConfig',
        'sagemaker:DescribeEndpoint',
        'sagemaker:UpdateEndpoint',
      ],
      resources: ['*'],
    }));

    // Add S3 permissions
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        's3:GetObject',
        's3:PutObject',
        's3:ListBucket',
        's3:GetObjectVersion',
      ],
      resources: [
        bucket.bucketArn,
        `${bucket.bucketArn}/*`,
      ],
    }));

    // Add permission to pass SageMaker role
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['iam:PassRole'],
      resources: [sagemakerRoleArn],
    }));

    // Lambda function to trigger training
    this.lambdaFunction = new lambda.Function(this, 'TriggerFullPipelineFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../lambda-training')),
      role: lambdaRole,
      timeout: cdk.Duration.minutes(15),
      memorySize: 512,
      environment: {
        SAGEMAKER_ROLE: sagemakerRoleArn,
        BUCKET_NAME: bucketName,
        AWS_REGION: this.region,
      },
      description: 'Triggers full pipeline SageMaker training job',
    });

    // EventBridge rule for scheduled training (optional)
    const enableSchedule = cdk.Stack.of(this).node.tryGetContext('enableSchedule') === 'true' || false;
    this.eventBridgeRule = new events.Rule(this, 'WeeklyTrainingSchedule', {
      description: 'Trigger full pipeline training weekly',
      schedule: events.Schedule.cron({
        minute: '0',
        hour: '2',
        day: '?',
        month: '*',
        weekDay: 'MON',
      }),
      enabled: enableSchedule, // Disabled by default - enable via context
    });

    // Add Lambda as target for EventBridge
    this.eventBridgeRule.addTarget(new targets.LambdaFunction(this.lambdaFunction, {
      event: events.RuleTargetInput.fromObject({
        instance_type: 'ml.p3.2xlarge',
        epochs: 10,
        batch_size: 16,
        learning_rate: 0.001,
      }),
    }));

    // Grant EventBridge permission to invoke Lambda
    this.lambdaFunction.addPermission('AllowEventBridge', {
      principal: new iam.ServicePrincipal('events.amazonaws.com'),
      sourceArn: this.eventBridgeRule.ruleArn,
    });

    // Outputs
    new cdk.CfnOutput(this, 'LambdaFunctionArn', {
      value: this.lambdaFunction.functionArn,
      description: 'ARN of the Lambda function',
      exportName: 'FullPipelineLambdaArn',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: this.lambdaFunction.functionName,
      description: 'Name of the Lambda function',
      exportName: 'FullPipelineLambdaName',
    });

    new cdk.CfnOutput(this, 'EventBridgeRuleArn', {
      value: this.eventBridgeRule.ruleArn,
      description: 'ARN of the EventBridge rule',
      exportName: 'FullPipelineEventBridgeRuleArn',
    });

    new cdk.CfnOutput(this, 'InvokeCommand', {
      value: `aws lambda invoke --function-name ${this.lambdaFunction.functionName} --payload '{}' /tmp/output.json`,
      description: 'Command to invoke Lambda function',
    });
  }
}

