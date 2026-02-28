#!/usr/bin/env python3
"""Lambda: invoke SageMaker endpoint for image classification."""
import os
import json
import base64
import boto3
from botocore.exceptions import ClientError

sagemaker_runtime = boto3.client('sagemaker-runtime')
ENDPOINT_NAME = os.environ.get('SAGEMAKER_ENDPOINT_NAME', 'album-classifier')


def lambda_handler(event, context):
    try:
        headers = {k.lower(): v for k, v in event.get('headers', {}).items()}
        content_type = headers.get('content-type', '')
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)

        if 'application/json' in content_type:
            data = json.loads(body.decode() if isinstance(body, bytes) else body)
            if 'image' not in data:
                return _err(400, 'JSON must contain "image" field with base64 image')
            b64 = data['image']
            if ',' in b64:
                b64 = b64.split(',', 1)[1]
            image_data = base64.b64decode(b64)
            ct = data.get('content_type', 'image/jpeg')
        elif 'multipart/form-data' in content_type:
            image_data = _parse_multipart(body, content_type)
            if not image_data:
                return _err(400, 'No image in multipart form')
            ct = 'image/jpeg'
        else:
            image_data = body if isinstance(body, bytes) else body.encode()
            ct = content_type.split(';')[0] or 'image/jpeg'

        resp = sagemaker_runtime.invoke_endpoint(
            EndpointName=ENDPOINT_NAME,
            ContentType=ct,
            Body=image_data,
        )
        out = json.loads(resp['Body'].read().decode())
        return _ok(out.get('predictions', out))
    except ClientError as e:
        return _err(500, e.response.get('Error', {}).get('Message', str(e)))
    except Exception as e:
        return _err(500, str(e))


def _ok(predictions):
    return {'statusCode': 200, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'success': True, 'predictions': predictions})}


def _err(code, msg):
    return {'statusCode': code, 'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*'}, 'body': json.dumps({'success': False, 'error': msg})}


def _parse_multipart(body, content_type):
    boundary = None
    for p in content_type.split(';'):
        p = p.strip()
        if p.startswith('boundary='):
            boundary = p.split('=', 1)[1].strip('"')
            break
    if not boundary:
        return None
    body = body.encode() if isinstance(body, str) else body
    for part in body.split(f'--{boundary}'.encode()):
        if b'name="file"' in part:
            i = part.find(b'\r\n\r\n')
            if i != -1:
                return part[i + 4:].rstrip(b'\r\n-')
    return None
