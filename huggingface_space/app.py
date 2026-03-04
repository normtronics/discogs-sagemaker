"""
Album cover recognition – Hugging Face Space.
Loads model from Hub and runs inference via Gradio.
"""
import os
import json
import torch
from PIL import Image
from torchvision import transforms
from torchvision import models
import torch.nn as nn
from huggingface_hub import hf_hub_download
import gradio as gr

# Model repo – set via env REPO_ID or update here after uploading model
REPO_ID = os.environ.get("REPO_ID", "YOUR_USERNAME/dsicogs-album-classifier")

TRANSFORM = transforms.Compose([
    transforms.Resize(256),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
])


def create_model(num_classes: int, dropout: float = 0.4):
    """ResNet50 with custom fc (same as backend/ml/model.py)."""
    model = models.resnet50(weights=None)
    in_features = model.fc.in_features
    model.fc = nn.Sequential(
        nn.Dropout(p=dropout),
        nn.Linear(in_features, num_classes),
    )
    return model


def load_model_from_hub(repo_id: str):
    """Download model.pth and metadata.json from Hub and load."""
    model_path = hf_hub_download(repo_id=repo_id, filename="model.pth")
    meta_path = hf_hub_download(repo_id=repo_id, filename="metadata.json")

    with open(meta_path) as f:
        meta = json.load(f)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = create_model(meta["num_classes"])
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.to(device).eval()

    return {"model": model, "metadata": meta, "device": device}


def predict(image: Image.Image, top_k: int = 5):
    """Run inference on uploaded image."""
    if image is None:
        return "Please upload an image."

    bundle = getattr(predict, "model_bundle", None)
    if bundle is None:
        return "Model not loaded. Set REPO_ID in Space settings to your model repo."
    model = bundle["model"]
    meta = bundle["metadata"]
    device = bundle["device"]
    releases = meta.get("releases", [])

    img = image.convert("RGB")
    img_tensor = TRANSFORM(img).unsqueeze(0).to(device)

    with torch.no_grad():
        out = model(img_tensor)
        probs = torch.nn.functional.softmax(out, dim=1)
        top_probs, top_indices = torch.topk(probs, min(top_k, out.size(1)))

    lines = []
    for prob, idx in zip(top_probs[0], top_indices[0]):
        i = idx.item()
        r = releases[i] if i < len(releases) else {}
        title = r.get("title", "Unknown")
        artists = ", ".join(r.get("artists", [])) if r.get("artists") else "Unknown"
        conf = float(prob.item())
        lines.append(f"**{title}** – {artists} ({conf:.1%})")
    return "\n\n".join(lines) if lines else "No predictions."


# Load model at startup
def _load_bundle():
    if "YOUR_USERNAME" in REPO_ID:
        return None
    try:
        return load_model_from_hub(REPO_ID)
    except Exception as e:
        print(f"Model load failed: {e}")
        return None


predict.model_bundle = _load_bundle()


def build_ui():
    with gr.Blocks(title="Album Cover Recognition") as demo:
        gr.Markdown("# Album Cover Recognition\nUpload an album cover image to identify the release.")
        with gr.Row():
            inp = gr.Image(type="pil", label="Album cover")
            out = gr.Markdown(label="Predictions")
        top_k = gr.Slider(1, 10, value=5, step=1, label="Top-K results")
        btn = gr.Button("Identify")
        btn.click(fn=lambda img, k: predict(img, int(k)), inputs=[inp, top_k], outputs=out, api_name="predict")
    return demo


demo = build_ui()
demo.launch()
