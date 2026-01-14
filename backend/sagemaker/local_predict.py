#!/usr/bin/env python3
"""
Local SageMaker Inference Testing Script
Tests the inference handler locally
"""
import os
import sys
import json
import argparse
from pathlib import Path
from PIL import Image

# Add parent directory to path
sys.path.insert(0, os.path.dirname(__file__))

from inference import model_fn, input_fn, predict_fn, output_fn


def test_local_inference(model_dir, image_path, top_k=5):
    """Test inference locally"""
    print("=" * 60)
    print("Local SageMaker Inference Test")
    print("=" * 60)
    
    # Load model
    print(f"\nLoading model from: {model_dir}")
    model_bundle = model_fn(model_dir)
    print(f"✓ Model loaded with {model_bundle['metadata']['num_classes']} classes")
    
    # Load and process image
    print(f"\nLoading image: {image_path}")
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Determine content type
    content_type = 'image/jpeg'
    if image_path.lower().endswith('.png'):
        content_type = 'image/png'
    
    image = input_fn(image_data, content_type)
    print(f"✓ Image loaded: {image.size}")
    
    # Make prediction
    print("\nMaking prediction...")
    predictions = predict_fn(image, model_bundle)
    
    # Format output
    output, _ = output_fn(predictions, 'application/json')
    result = json.loads(output)
    
    # Display results
    print("\n" + "=" * 60)
    print("Prediction Results")
    print("=" * 60)
    
    for i, pred in enumerate(result['predictions'][:top_k], 1):
        print(f"\n{i}. {pred['title']}")
        print(f"   Artists: {', '.join(pred['artists'])}")
        print(f"   Confidence: {pred['confidence']*100:.2f}%")
        print(f"   Released: {pred['released']}")
        if pred['labels']:
            print(f"   Labels: {', '.join(pred['labels'])}")
    
    print("\n" + "=" * 60)
    
    return result


def main():
    parser = argparse.ArgumentParser(description='Test SageMaker inference locally')
    parser.add_argument('--image', '-i', type=str, required=True,
                        help='Path to image file for prediction')
    parser.add_argument('--model-dir', type=str, default=None,
                        help='Path to model directory (default: sagemaker/models)')
    parser.add_argument('--top-k', type=int, default=5,
                        help='Number of top predictions to show')
    
    args = parser.parse_args()
    
    # Set default model directory
    if args.model_dir is None:
        project_root = Path(__file__).parent.parent
        args.model_dir = str(project_root / 'sagemaker' / 'models')
    
    # Check if model exists
    model_path = Path(args.model_dir) / 'model.pth'
    if not model_path.exists():
        print(f"Error: Model not found at {model_path}")
        print("Please train the model first using:")
        print("  python sagemaker/local_train.py")
        sys.exit(1)
    
    # Check if image exists
    if not Path(args.image).exists():
        print(f"Error: Image not found at {args.image}")
        sys.exit(1)
    
    # Run inference
    test_local_inference(args.model_dir, args.image, args.top_k)


if __name__ == '__main__':
    main()

