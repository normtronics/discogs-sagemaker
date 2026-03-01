"""Model architecture."""
import os
import torch
import torch.nn as nn
from torchvision import models

RESNET50_FILENAME = "resnet50-0676ba61.pth"
RESNET50_URL = "https://download.pytorch.org/models/resnet50-0676ba61.pth"


def _load_pretrained_weights(model: nn.Module) -> None:
    """Load ImageNet pretrained weights from local file or download."""
    import os as _os

    # Check env var, then torch hub cache
    local_path = _os.environ.get("RESNET50_WEIGHTS_PATH")
    if not local_path:
        cache_dir = torch.hub.get_dir()
        local_path = _os.path.join(cache_dir, "checkpoints", RESNET50_FILENAME)

    if _os.path.exists(local_path):
        state_dict = torch.load(local_path, map_location="cpu", weights_only=True)
        # Remove fc layer (we replace it); load rest with strict=False
        state_dict.pop("fc.weight", None)
        state_dict.pop("fc.bias", None)
        model.load_state_dict(state_dict, strict=False)
        return

    # Fallback: download (requires network)
    model.load_state_dict(
        torch.hub.load_state_dict_from_url(RESNET50_URL, map_location="cpu", weights_only=True),
        strict=False,
    )


def create_model(num_classes: int, dropout: float = 0.4):
    """Create ResNet50 for album classification."""
    model = models.resnet50(weights=None)
    _load_pretrained_weights(model)

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
