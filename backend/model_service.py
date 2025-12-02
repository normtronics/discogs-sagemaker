import torch
import torch.nn as nn
from torchvision import models, transforms
from PIL import Image
import os
from typing import List, Dict, Optional


class AlbumClassifier:
    """Album classification service using ResNet50"""
    
    def __init__(self, model_path: str, num_classes: int, images_path: str):
        self.model_path = model_path
        self.num_classes = num_classes
        self.images_path = images_path
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Image preprocessing
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225]
            )
        ])
        
        # Load model if exists
        self.model = self._load_model()
    
    def _create_model(self) -> nn.Module:
        """Create a ResNet50 model for classification"""
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        
        # Replace the final fully connected layer
        num_features = model.fc.in_features
        model.fc = nn.Linear(num_features, self.num_classes)
        
        return model.to(self.device)
    
    def _load_model(self) -> Optional[nn.Module]:
        """Load model from disk if it exists"""
        if not os.path.exists(self.model_path):
            print(f"Model not found at {self.model_path}. Please train the model first.")
            return None
        
        try:
            model = self._create_model()
            model.load_state_dict(torch.load(self.model_path, map_location=self.device))
            model.eval()
            print(f"Model loaded successfully from {self.model_path}")
            return model
        except Exception as e:
            print(f"Error loading model: {str(e)}")
            return None
    
    def predict(self, image: Image.Image, top_k: int = 5) -> List[Dict]:
        """
        Predict album from image
        
        Args:
            image: PIL Image
            top_k: Number of top predictions to return
        
        Returns:
            List of predictions with confidence scores
        """
        if self.model is None:
            raise ValueError("Model not loaded. Please train the model first.")
        
        # Preprocess image
        image_tensor = self.transform(image).unsqueeze(0).to(self.device)
        
        # Get predictions
        with torch.no_grad():
            outputs = self.model(image_tensor)
            probabilities = torch.nn.functional.softmax(outputs, dim=1)
            
            # Get top k predictions
            top_probs, top_indices = torch.topk(probabilities, min(top_k, self.num_classes))
            
            predictions = []
            for prob, idx in zip(top_probs[0], top_indices[0]):
                predictions.append({
                    "class_idx": idx.item(),
                    "confidence": prob.item()
                })
        
        return predictions
    
    def predict_from_path(self, image_path: str, top_k: int = 5) -> List[Dict]:
        """Predict album from image file path"""
        image = Image.open(image_path).convert("RGB")
        return self.predict(image, top_k)

