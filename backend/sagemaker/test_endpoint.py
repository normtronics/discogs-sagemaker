#!/usr/bin/env python3
"""
Test SageMaker Endpoint
Send test images to deployed endpoint
"""
import os
import json
import argparse
import boto3
from pathlib import Path
from dotenv import load_dotenv


def load_config():
    """Load configuration from env.local"""
    # __file__ is backend/sagemaker/test_endpoint.py
    # parent is backend/sagemaker/, parent.parent is backend/
    backend_root = Path(__file__).parent.parent
    env_path = backend_root / '.env.local'
    
    if env_path.exists():
        load_dotenv(env_path)


def test_endpoint(endpoint_name, image_path, region='us-east-1'):
    """Test SageMaker endpoint with an image"""
    print("=" * 60)
    print("Testing SageMaker Endpoint")
    print("=" * 60)
    
    # Create SageMaker runtime client
    client = boto3.client('sagemaker-runtime', region_name=region)
    
    # Read image
    print(f"\nLoading image: {image_path}")
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Determine content type
    content_type = 'image/jpeg'
    if image_path.lower().endswith('.png'):
        content_type = 'image/png'
    
    print(f"Content Type: {content_type}")
    print(f"Image Size: {len(image_data)} bytes")
    print(f"Endpoint: {endpoint_name}")
    
    # Invoke endpoint
    print("\nInvoking endpoint...")
    response = client.invoke_endpoint(
        EndpointName=endpoint_name,
        ContentType=content_type,
        Accept='application/json',
        Body=image_data
    )
    
    # Parse response
    result = json.loads(response['Body'].read().decode())
    
    # Display results
    print("\n" + "=" * 60)
    print("Prediction Results")
    print("=" * 60)
    
    if result.get('success'):
        for i, pred in enumerate(result['predictions'], 1):
            print(f"\n{i}. {pred['title']}")
            print(f"   Artists: {', '.join(pred['artists'])}")
            print(f"   Confidence: {pred['confidence']*100:.2f}%")
            print(f"   Released: {pred['released']}")
            if pred.get('labels'):
                print(f"   Labels: {', '.join(pred['labels'])}")
    else:
        print("Error:", result.get('error', 'Unknown error'))
    
    print("\n" + "=" * 60)
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Test SageMaker endpoint')
    parser.add_argument('--endpoint', '-e', type=str, required=True,
                        help='SageMaker endpoint name')
    parser.add_argument('--image', '-i', type=str, required=True,
                        help='Path to image file')
    parser.add_argument('--region', type=str, default=None,
                        help='AWS region (default: from env or us-east-1)')
    
    args = parser.parse_args()
    
    # Load config
    load_config()
    
    # Get region
    region = args.region or os.getenv('AWS_REGION', 'us-east-1')
    
    # Check if image exists
    if not Path(args.image).exists():
        print(f"Error: Image not found at {args.image}")
        return
    
    # Test endpoint
    test_endpoint(args.endpoint, args.image, region)


if __name__ == '__main__':
    main()

