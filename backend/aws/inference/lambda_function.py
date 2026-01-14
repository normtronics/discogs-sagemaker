#!/usr/bin/env python3
"""
Lambda function to invoke SageMaker endpoint for image classification.
Called by API Gateway.
"""
import os
import json
import base64
import boto3
from botocore.exceptions import ClientError

# Initialize SageMaker Runtime client
sagemaker_runtime = boto3.client('sagemaker-runtime')

# Get endpoint name from environment
ENDPOINT_NAME = os.environ.get('SAGEMAKER_ENDPOINT_NAME', 'album-classifier')


def lambda_handler(event, context):
    """
    Lambda handler for API Gateway requests.
    
    Expected input (in order of preference):
    1. application/json with base64 encoded image (recommended)
       {
         "image": "base64_encoded_string",
         "content_type": "image/jpeg"  // optional
       }
    2. multipart/form-data with 'file' field (from frontend)
    3. Raw binary body (image bytes)
    
    Returns:
    - JSON response with predictions
    """
    try:
        # Get headers (normalize keys to lowercase)
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        content_type = headers.get('content-type', '')
        
        # Parse request body
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)
        elif isinstance(body, str):
            # Try to decode if it's a string representation of bytes
            try:
                body = base64.b64decode(body)
            except:
                pass  # Keep as string
        
        # Handle JSON with base64 image (recommended approach)
        if 'application/json' in content_type:
            try:
                if isinstance(body, bytes):
                    body_str = body.decode('utf-8')
                else:
                    body_str = body
                    
                body_json = json.loads(body_str)
                
                if 'image' in body_json:
                    # Base64 encoded image
                    image_b64 = body_json['image']
                    # Remove data URL prefix if present (e.g., "data:image/jpeg;base64,...")
                    if ',' in image_b64:
                        image_b64 = image_b64.split(',', 1)[1]
                    image_data = base64.b64decode(image_b64)
                    content_type_for_sagemaker = body_json.get('content_type', 'image/jpeg')
                else:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*',
                        },
                        'body': json.dumps({
                            'success': False,
                            'error': 'JSON body must contain "image" field with base64 encoded image',
                        }),
                    }
            except json.JSONDecodeError as e:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                    },
                    'body': json.dumps({
                        'success': False,
                        'error': f'Invalid JSON in request body: {str(e)}',
                    }),
                }
            except Exception as e:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                    },
                    'body': json.dumps({
                        'success': False,
                        'error': f'Error decoding image: {str(e)}',
                    }),
                }
        
        # Handle multipart/form-data
        elif 'multipart/form-data' in content_type:
            image_data = parse_multipart_form_data(body, content_type)
            
            if not image_data:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*',
                    },
                    'body': json.dumps({
                        'success': False,
                        'error': 'No image file found in multipart form data',
                    }),
                }
            
            # Determine content type from file (default to jpeg)
            content_type_for_sagemaker = 'image/jpeg'
            
        # Handle raw binary/image uploads
        else:
            # Use body as-is (for direct binary uploads)
            if isinstance(body, str):
                image_data = body.encode('utf-8')
            else:
                image_data = body
            content_type_for_sagemaker = content_type.split(';')[0] if content_type else 'image/jpeg'
        
        # Invoke SageMaker endpoint
        response = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType=content_type_for_sagemaker,
            Body=image_data,
        )
        
        # Parse response
        response_body = response['Body'].read()
        predictions = json.loads(response_body.decode('utf-8'))
        
        # Return success response
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': True,
                'predictions': predictions.get('predictions', predictions),
            }),
        }
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_message = e.response.get('Error', {}).get('Message', str(e))
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': False,
                'error': f'SageMaker error: {error_message}',
                'error_code': error_code,
            }),
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
            },
            'body': json.dumps({
                'success': False,
                'error': f'Internal error: {str(e)}',
            }),
        }


def parse_multipart_form_data(body, content_type):
    """
    Parse multipart/form-data body.
    This is a simplified parser - in production, use email.message or similar.
    
    Note: API Gateway with Lambda proxy integration doesn't parse multipart automatically.
    For production, consider:
    1. Using API Gateway mapping template to convert to JSON
    2. Using a library like python-multipart
    3. Having frontend send base64 encoded JSON instead
    """
    # Extract boundary from content-type header
    boundary = None
    for part in content_type.split(';'):
        part = part.strip()
        if part.startswith('boundary='):
            boundary = part.split('=', 1)[1].strip('"')
            break
    
    if not boundary:
        return None
    
    # Ensure body is bytes
    if isinstance(body, str):
        body = body.encode('utf-8')
    
    # Split by boundary
    boundary_bytes = f'--{boundary}'.encode()
    parts = body.split(boundary_bytes)
    
    # Find the file part
    for part in parts:
        if b'Content-Disposition: form-data' in part and b'name="file"' in part:
            # Extract file data (after headers and blank line)
            # Headers end with \r\n\r\n
            header_end = part.find(b'\r\n\r\n')
            if header_end != -1:
                file_data = part[header_end + 4:]  # Skip \r\n\r\n
                # Remove trailing boundary markers and whitespace
                file_data = file_data.rstrip(b'\r\n-')
                return file_data
    
    return None
