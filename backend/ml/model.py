"""Model architecture."""
import torch.nn as nn
from torchvision import models


def create_model(num_classes: int, dropout: float = 0.4):
    """Create ResNet50 for album classification."""
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)

    # Freeze early layers; unfreeze layer4 and fc for fine-tuning
    for name, param in model.named_parameters():
        if not name.startswith(("layer4.", "fc.")):
            param.requires_grad = False

    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, num_classes),
    )
    return model
