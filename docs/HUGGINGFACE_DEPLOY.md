# Deploy to Hugging Face

Deploy the album classifier to Hugging Face: push the model to the Hub and run a Gradio Space that exposes an API.

## Overview

| Step | What | Result |
|------|------|--------|
| 1 | Push model to Hub | `model.pth` + `metadata.json` in a model repo |
| 2 | Create Gradio Space | Web UI + API at `https://huggingface.co/spaces/username/space-name` |

Gradio Spaces automatically expose an API. You can call it from Python, JavaScript, or cURL.

## 1. Push Model to Hugging Face Hub

### Prerequisites

- Trained model in `models/` (or your `--model-dir`): `model.pth` and `metadata.json`
- Hugging Face account and token

### Install dependency

```bash
pip install huggingface_hub
```

### Login

```bash
huggingface-cli login
```

Or set `HF_TOKEN`:

```bash
export HF_TOKEN=hf_xxxxxxxxxxxx
```

### Upload

```bash
cd backend
python scripts/push_to_huggingface.py \
  --model-dir models \
  --repo-id YOUR_USERNAME/dsicogs-album-classifier
```

Use `--private` for a private model repo.

## 2. Create Gradio Space

### Option A: Hugging Face Web UI

1. Go to [huggingface.co/spaces](https://huggingface.co/spaces)
2. **Create new Space**
3. Name: `dsicogs-album-classifier` (or similar)
4. SDK: **Gradio**
5. Hardware: **CPU basic** (or GPU for faster inference)
6. Create Space

### Option B: Push from local

```bash
cd huggingface_space
```

Edit `app.py` and set `REPO_ID` to your model repo, or add a Space secret:

- **Settings → Repository secrets** → Add `REPO_ID` = `YOUR_USERNAME/dsicogs-album-classifier`

Then push the Space files:

```bash
# Clone your Space repo first, then:
cp app.py requirements.txt README.md /path/to/your-space-repo/
cd /path/to/your-space-repo
git add .
git commit -m "Add album classifier Space"
git push
```

### Space files

| File | Purpose |
|------|---------|
| `app.py` | Gradio app; loads model from Hub, runs inference |
| `requirements.txt` | gradio, torch, torchvision, huggingface_hub, Pillow |
| `README.md` | Space description (optional) |

## 3. Use the API

Once the Space is running, it exposes an API.

### Python (gradio_client)

```bash
pip install gradio_client
```

```python
from gradio_client import Client, handle_file

client = Client("YOUR_USERNAME/dsicogs-album-classifier")
result = client.predict(handle_file("path/to/album_cover.jpg"), 5, api_name="predict")
print(result)
```

Use `handle_file()` for local image paths. The second argument (5) is `top_k`; omit it to use the default.

### cURL

```bash
# Get the API info from the Space's "View API" page, then:
curl -X POST "https://YOUR_USERNAME-dsicogs-album-classifier.hf.space/api/predict" \
  -H "Content-Type: application/json" \
  -d '{"data": ["path/to/image.jpg"]}'
```

### JavaScript

```bash
npm install @gradio/client
```

```javascript
import { Client } from "@gradio/client";

const app = await Client.connect("YOUR_USERNAME/dsicogs-album-classifier");
const result = await app.predict("/predict", "path/to/image.jpg");
console.log(result);
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    HUGGING FACE DEPLOYMENT                       │
└─────────────────────────────────────────────────────────────────┘

  Your machine                    Hugging Face
  ┌─────────────────┐             ┌─────────────────────────────────┐
  │ push_to_        │   upload    │  Model repo                     │
  │ huggingface.py  │ ─────────►  │  (model.pth, metadata.json)     │
  └─────────────────┘             └─────────────────────────────────┘
                                            │
                                            │ hf_hub_download
                                            ▼
                                  ┌─────────────────────────────────┐
                                  │  Gradio Space                   │
                                  │  - Loads model at startup       │
                                  │  - Web UI + API                 │
                                  └─────────────────────────────────┘
                                            │
                                            │ HTTPS
                                            ▼
                                  Browser / gradio_client / cURL
```

## Cost

- **Model repo**: Free
- **Gradio Space**: Free tier (CPU basic); paid for GPU or higher limits

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `Model not loaded` | Set `REPO_ID` in Space settings to your model repo |
| `HF_TOKEN` required | Run `huggingface-cli login` or set `HF_TOKEN` |
| Space fails to load model | Ensure model repo is public, or use a token in the Space |
| Slow first request | Model loads on first request; subsequent requests are faster |
