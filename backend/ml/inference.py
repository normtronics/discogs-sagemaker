#!/usr/bin/env python3
"""
Inference for album classifier. Works locally and in SageMaker.
SageMaker uses model_fn, input_fn, predict_fn, output_fn.
"""
import io
import json
import logging
import os
import torch
from PIL import Image
from torchvision import transforms

from .model import create_model

logger = logging.getLogger(__name__)

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def model_fn(model_dir: str):
    """Load model. Called once by SageMaker."""
    logger.info(f"Loading model from {model_dir}")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    with open(os.path.join(model_dir, "metadata.json")) as f:
        meta = json.load(f)

    model = create_model(meta["num_classes"])
    model.load_state_dict(torch.load(os.path.join(model_dir, "model.pth"), map_location=device))
    model.to(device).eval()

    return {"model": model, "metadata": meta, "device": device}


def input_fn(request_body, content_type="application/x-image"):
    """Deserialize input."""
    if content_type in ("application/x-image", "image/jpeg", "image/jpg", "image/png"):
        if isinstance(request_body, bytes):
            return Image.open(io.BytesIO(request_body)).convert("RGB")
        else:
            return Image.open(request_body).convert("RGB")
    if content_type == "application/json":
        data = json.loads(request_body)
        if "image" in data:
            import base64
            raw = base64.b64decode(data["image"])
            return Image.open(io.BytesIO(raw)).convert("RGB")
    raise ValueError(f"Unsupported content type: {content_type}")


def predict_fn(input_data, model_bundle):
    """Run prediction."""
    model = model_bundle["model"]
    meta = model_bundle["metadata"]
    device = model_bundle["device"]
    releases = meta.get("releases", [])

    img_tensor = TRANSFORM(input_data).unsqueeze(0).to(device)
    with torch.no_grad():
        out = model(img_tensor)
        probs = torch.nn.functional.softmax(out, dim=1)
        top_probs, top_indices = torch.topk(probs, min(5, out.size(1)))

    predictions = []
    for prob, idx in zip(top_probs[0], top_indices[0]):
        i = idx.item()
        r = releases[i] if i < len(releases) else {}
        predictions.append({
            "release_id": r.get("release_id", ""),
            "title": r.get("title", "Unknown"),
            "artists": r.get("artists", []),
            "confidence": float(prob.item()),
            "labels": r.get("labels", []),
            "released": r.get("released", "Unknown"),
            "class_idx": i,
        })

    return predictions


def output_fn(predictions, accept="application/json"):
    """Serialize output."""
    if accept == "application/json":
        return json.dumps({"success": True, "predictions": predictions}), accept
    raise ValueError(f"Unsupported accept: {accept}")


# Local use: load model and predict
def load_local(model_dir: str, device=None):
    """Load model for local inference."""
    bundle = model_fn(model_dir)
    return bundle


def predict_local(bundle, image: Image.Image, top_k: int = 5):
    """Predict from PIL Image."""
    if isinstance(image, Image.Image):
        image = image.convert("RGB")
    preds = predict_fn(image, bundle)
    return preds[:top_k]
