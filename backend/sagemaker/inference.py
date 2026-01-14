#!/usr/bin/env python3
"""
SageMaker Inference Handler for Album Classification
Handles model loading and prediction requests
"""
import os
import json
import io
import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image


def model_fn(model_dir):
    """
    Load the PyTorch model from the `model_dir` directory.
    Called once when the endpoint is initialized.
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    # Load metadata
    metadata_path = os.path.join(model_dir, 'metadata.json')
    with open(metadata_path, 'r') as f:
        metadata = json.load(f)
    
    num_classes = metadata['num_classes']
    
    # Create model architecture
    model = models.resnet50(weights=None)
    num_features = model.fc.in_features
    model.fc = nn.Linear(num_features, num_classes)
    
    # Load model weights
    model_path = os.path.join(model_dir, 'model.pth')
    model.load_state_dict(torch.load(model_path, map_location=device))
    model = model.to(device)
    model.eval()
    
    print(f"Model loaded successfully with {num_classes} classes")
    
    # Return model and metadata as a tuple
    return {
        'model': model,
        'metadata': metadata,
        'device': device
    }


def input_fn(request_body, request_content_type):
    """
    Deserialize and prepare the prediction input.
    
    Args:
        request_body: The request body
        request_content_type: The content type (e.g., 'application/x-image', 'image/jpeg')
    
    Returns:
        PIL Image
    """
    if request_content_type in ['application/x-image', 'image/jpeg', 'image/png', 'image/jpg']:
        image = Image.open(io.BytesIO(request_body)).convert('RGB')
        return image
    elif request_content_type == 'application/json':
        # Handle base64 encoded images in JSON
        import base64
        data = json.loads(request_body)
        
        if 'image' in data:
            image_data = base64.b64decode(data['image'])
            image = Image.open(io.BytesIO(image_data)).convert('RGB')
            return image
        else:
            raise ValueError("JSON must contain 'image' field with base64 encoded image data")
    else:
        raise ValueError(f"Unsupported content type: {request_content_type}")


def predict_fn(input_data, model_bundle):
    """
    Apply model to the incoming request
    
    Args:
        input_data: PIL Image from input_fn
        model_bundle: Dictionary containing model, metadata, and device
    
    Returns:
        Predictions dictionary
    """
    model = model_bundle['model']
    metadata = model_bundle['metadata']
    device = model_bundle['device']
    releases = metadata['releases']
    
    # Image preprocessing
    transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    # Prepare input tensor
    image_tensor = transform(input_data).unsqueeze(0).to(device)
    
    # Get predictions
    with torch.no_grad():
        outputs = model(image_tensor)
        probabilities = torch.nn.functional.softmax(outputs, dim=1)
        
        # Get top 5 predictions
        top_k = min(5, len(releases))
        top_probs, top_indices = torch.topk(probabilities, top_k)
        
        predictions = []
        for prob, idx in zip(top_probs[0], top_indices[0]):
            idx_item = idx.item()
            release = releases[idx_item]
            predictions.append({
                "release_id": release.get("release_id", ""),
                "title": release.get("title", "Unknown"),
                "artists": release.get("artists", []),
                "confidence": float(prob.item()),
                "labels": release.get("labels", []),
                "released": release.get("released", "Unknown"),
                "class_idx": idx_item
            })
    
    return predictions


def output_fn(predictions, accept):
    """
    Serialize the prediction result
    
    Args:
        predictions: The output from predict_fn
        accept: The requested content type (e.g., 'application/json')
    
    Returns:
        Serialized predictions
    """
    if accept == 'application/json':
        return json.dumps({
            'success': True,
            'predictions': predictions
        }), accept
    else:
        raise ValueError(f"Unsupported accept type: {accept}")


# Alternative: Single handler function for simpler use cases
def handler(data, context):
    """
    Alternative handler that combines all steps.
    This is useful for custom inference containers.
    """
    # Get model from context
    model_bundle = context.model
    
    # Process request
    if context.request_content_type in ['application/x-image', 'image/jpeg', 'image/png']:
        input_data = input_fn(data, context.request_content_type)
    else:
        raise ValueError(f"Unsupported content type: {context.request_content_type}")
    
    # Make prediction
    predictions = predict_fn(input_data, model_bundle)
    
    # Return response
    return output_fn(predictions, context.accept_header)

