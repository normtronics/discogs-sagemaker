import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as apigateway from 'aws-cdk-lib/aws-apigateway';
import * as logs from 'aws-cdk-lib/aws-logs';
import { Construct } from 'constructs';
import * as path from 'path';

export interface InferenceStackProps extends cdk.StackProps {
  endpointName: string;
  sagemakerRoleArn?: string; // Optional, for reference
}

export class InferenceStack extends cdk.Stack {
  public readonly apiGateway: apigateway.RestApi;
  public readonly lambdaFunction: lambda.Function;

  constructor(scope: Construct, id: string, props: InferenceStackProps) {
    super(scope, id, props);

    const { endpointName } = props;

    // Lambda execution role
    const lambdaRole = new iam.Role(this, 'PredictFunctionRole', {
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      description: 'Role for Lambda function to invoke SageMaker endpoints',
      managedPolicies: [
        iam.ManagedPolicy.fromAwsManagedPolicyName('service-role/AWSLambdaBasicExecutionRole'),
      ],
    });

    // Add SageMaker Runtime invoke permission
    lambdaRole.addToPolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: [
        'sagemaker-runtime:InvokeEndpoint',
      ],
      resources: [
        `arn:aws:sagemaker:${this.region}:${this.account}:endpoint/${endpointName}`,
        // Also allow wildcard for flexibility (can restrict later)
        `arn:aws:sagemaker:${this.region}:${this.account}:endpoint/*`,
      ],
    }));

    // Lambda function for invoking SageMaker endpoint
    this.lambdaFunction = new lambda.Function(this, 'PredictFunction', {
      runtime: lambda.Runtime.PYTHON_3_11,
      handler: 'lambda_function.lambda_handler',
      code: lambda.Code.fromAsset(path.join(__dirname, '../../backend/aws/inference')),
      role: lambdaRole,
      timeout: cdk.Duration.seconds(30), // SageMaker endpoints can take time
      memorySize: 512,
      environment: {
        SAGEMAKER_ENDPOINT_NAME: endpointName,
        AWS_REGION: this.region,
      },
      description: 'Invokes SageMaker endpoint for image classification',
      logRetention: logs.RetentionDays.ONE_WEEK,
    });

    // API Gateway REST API
    this.apiGateway = new apigateway.RestApi(this, 'PredictApi', {
      restApiName: 'Album Classifier Inference API',
      description: 'API Gateway for SageMaker inference endpoint',
      defaultCorsPreflightOptions: {
        allowOrigins: apigateway.Cors.ALL_ORIGINS, // Restrict in production
        allowMethods: apigateway.Cors.ALL_METHODS,
        allowHeaders: [
          'Content-Type',
          'X-Amz-Date',
          'Authorization',
          'X-Api-Key',
          'X-Amz-Security-Token',
        ],
        maxAge: cdk.Duration.days(1),
      },
      deployOptions: {
        stageName: 'prod',
        loggingLevel: apigateway.MethodLoggingLevel.INFO,
        dataTraceEnabled: true,
        metricsEnabled: true,
      },
    });

    // Create /predict resource
    const predictResource = this.apiGateway.root.addResource('predict');

    // Add POST method with Lambda integration
    predictResource.addMethod('POST', new apigateway.LambdaIntegration(this.lambdaFunction, {
      proxy: true, // Pass through request/response as-is
      integrationOptions: {
        timeout: cdk.Duration.seconds(29), // Slightly less than Lambda timeout
        requestTemplates: {
          'multipart/form-data': JSON.stringify({
            // API Gateway will pass multipart form data to Lambda
            // Lambda will parse it
          }),
        },
      },
    }), {
      methodResponses: [
        {
          statusCode: '200',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
        {
          statusCode: '400',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
        {
          statusCode: '500',
          responseParameters: {
            'method.response.header.Access-Control-Allow-Origin': true,
          },
        },
      ],
    });

    // Grant API Gateway permission to invoke Lambda
    this.lambdaFunction.addPermission('AllowApiGatewayInvoke', {
      principal: new iam.ServicePrincipal('apigateway.amazonaws.com'),
      sourceArn: `${this.apiGateway.arnForExecuteApi()}/*/*`,
    });

    // Outputs
    new cdk.CfnOutput(this, 'ApiGatewayUrl', {
      value: this.apiGateway.url,
      description: 'API Gateway endpoint URL',
      exportName: 'InferenceApiGatewayUrl',
    });

    new cdk.CfnOutput(this, 'ApiGatewayPredictUrl', {
      value: `${this.apiGateway.url}predict`,
      description: 'Full URL for prediction endpoint',
      exportName: 'InferenceApiPredictUrl',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionArn', {
      value: this.lambdaFunction.functionArn,
      description: 'ARN of the Lambda function',
      exportName: 'InferenceLambdaArn',
    });

    new cdk.CfnOutput(this, 'LambdaFunctionName', {
      value: this.lambdaFunction.functionName,
      description: 'Name of the Lambda function',
      exportName: 'InferenceLambdaName',
    });

    new cdk.CfnOutput(this, 'SageMakerEndpointName', {
      value: endpointName,
      description: 'SageMaker endpoint name',
      exportName: 'SageMakerEndpointName',
    });
  }
}
