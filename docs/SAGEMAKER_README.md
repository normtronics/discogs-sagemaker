# How SageMaker Works in This Project

This guide explains how AWS SageMaker fits into the album recognition app—from training to deployment.

## Overview

The app can run in three modes:

| Mode | Training | Inference | Use Case |
|------|----------|-----------|----------|
| **Local** | Your Mac | FastAPI (`main.py`) | Development, offline |
| **SageMaker** | AWS GPU/CPU instances | SageMaker endpoint | Production, scalable |
| **Hugging Face** | Your Mac (or SageMaker) | Gradio Space + API | Free hosting, easy sharing |

SageMaker handles the heavy lifting: training on powerful instances and serving predictions via a managed endpoint. For a simpler deployment, see [HUGGINGFACE_DEPLOY.md](HUGGINGFACE_DEPLOY.md).

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         TRAINING (one-time or periodic)                  │
└─────────────────────────────────────────────────────────────────────────┘

  Your machine                    S3                         SageMaker
  ┌─────────────┐              ┌─────────┐                  ┌──────────────┐
  │ prepare_for │   upload     │  data/  │    training job  │  Training    │
  │ _studio.sh  │ ──────────►  │  code/  │ ◄───────────────  │  Job         │
  │             │              │         │                  │  (GPU/CPU)   │
  └─────────────┘              └────┬────┘                  └──────┬───────┘
                                   │                              │
                                   │         model artifacts      │
                                   │ ◄────────────────────────────┘
                                   │   (model.pth, metadata.json)
                                   ▼
                              ┌─────────┐
                              │ models/ │
                              └─────────┘


┌─────────────────────────────────────────────────────────────────────────┐
│                         INFERENCE (after deployment)                      │
└─────────────────────────────────────────────────────────────────────────┘

  Your machine                    S3                         SageMaker
  ┌─────────────┐              ┌─────────┐                  ┌──────────────┐
  │  Frontend   │   HTTP POST  │         │                  │  Endpoint     │
  │  (browser)  │ ──────────►  │  API    │ ───────────────► │  (model.pth   │
  │             │              │ Gateway │   Lambda         │   loaded)    │
  │             │ ◄──────────  │  +      │ ◄──────────────  │              │
  │             │   JSON       │ Lambda  │   predictions    └──────────────┘
  └─────────────┘              └─────────┘
```

## How It Works

### 1. Training (SageMaker Training Job)

Training runs on AWS, not your laptop:

1. **Prepare** – Run `prepare_for_studio.sh` to upload your data and code to S3:

   ```bash
   ./prepare_for_studio.sh your-bucket-name
   ```

   This uploads:
   - `data/releases_manifest.jsonl` → `s3://bucket/data/`
   - `data/images/` → `s3://bucket/data/images/`
   - `backend/ml/`, `train.py`, `inference.py` → `s3://bucket/code/sourcedir.tar.gz`

2. **Launch** – From SageMaker Studio or a notebook, create a training job:

   ```python
   from sagemaker.pytorch import PyTorch

   estimator = PyTorch(
       entry_point='train.py',
       source_dir='s3://your-bucket/code/sourcedir.tar.gz',
       role=role,
       instance_type='ml.m5.xlarge',  # or ml.p3.2xlarge for GPU
       framework_version='2.5.0',
       py_version='py311',
   )
   estimator.fit({'training': 's3://your-bucket/data/'})
   ```

3. **Output** – SageMaker saves the trained model to S3 (e.g. `s3://bucket/models/.../output/model.tar.gz`).

**Why SageMaker for training?**
- GPU instances for faster training
- No need to keep your laptop running
- Scales to large datasets

### 2. Deployment (SageMaker Endpoint)

Once training is done, you deploy the model as an endpoint:

```python
from sagemaker.pytorch import PyTorchModel

model = PyTorchModel(
    model_data=estimator.model_data,
    role=role,
    entry_point='inference.py',
    framework_version='2.5.0',
    py_version='py311',
)

predictor = model.deploy(
    initial_instance_count=1,
    instance_type='ml.m5.large',
    endpoint_name='album-classifier'
)
```

The endpoint is a **server** that loads your model and responds to prediction requests.

### 3. Inference (API Gateway + Lambda)

The frontend calls your API, not SageMaker directly:

```text
User uploads image → Next.js API route → Lambda → SageMaker InvokeEndpoint → Predictions
```

- **API Gateway** – Public HTTP endpoint
- **Lambda** – Receives the image, calls SageMaker `InvokeEndpoint`, returns JSON
- **SageMaker** – Runs the model inference

This keeps AWS credentials on the server and avoids CORS issues.

## Key Files

| File | Purpose |
|------|---------|
| `backend/train.py` | SageMaker entry point; calls `ml.train` |
| `backend/ml/train.py` | Training logic (reads `SM_CHANNEL_TRAINING` from S3) |
| `backend/inference.py` | SageMaker entry point; defines `model_fn`, `input_fn`, `predict_fn` |
| `backend/ml/inference.py` | Inference logic (loads model, runs prediction) |
| `prepare_for_studio.sh` | Uploads data + code to S3 |
| `infrastructure/lib/inference-stack.ts` | CDK: API Gateway + Lambda to invoke endpoint |

## SageMaker Environment Variables

When training runs on SageMaker, these are set automatically:

| Variable | Value | Meaning |
|----------|-------|---------|
| `SM_CHANNEL_TRAINING` | Path to S3 data | Where your manifest and images live |
| `SM_MODEL_DIR` | `/opt/ml/model` | Where to save the trained model |

Your `ml/train.py` uses these:

```python
data_dir = os.environ.get("SM_CHANNEL_TRAINING", "data")
model_dir = os.environ.get("SM_MODEL_DIR", "models")
```

## Quick Start

1. **Create S3 bucket** and run `prepare_for_studio.sh`
2. **Open SageMaker Studio** and run the notebook in `notebooks/studio_notebook.ipynb`
3. **Deploy** endpoint from the notebook
4. **Deploy** API Gateway + Lambda: `cd infrastructure && npm run deploy -- --context endpointName=album-classifier`
5. **Configure** frontend with the API Gateway URL

## Detailed Guides

| Guide | Purpose |
|-------|---------|
| [HUGGINGFACE_DEPLOY.md](HUGGINGFACE_DEPLOY.md) | Deploy model to Hugging Face + Gradio API |
| [SAGEMAKER_QUICK_START.md](SAGEMAKER_QUICK_START.md) | 5-step quick reference |
| [SAGEMAKER_COMPLETE_SETUP.md](SAGEMAKER_COMPLETE_SETUP.md) | Full setup walkthrough |
| [STUDIO_WALKTHROUGH.md](STUDIO_WALKTHROUGH.md) | SageMaker Studio step-by-step |
| [DEPLOY_INFERENCE.md](DEPLOY_INFERENCE.md) | API Gateway + Lambda deployment |
| [README_SAGEMAKER.md](README_SAGEMAKER.md) | Frontend integration with SageMaker |

## Cost

- **Training**: ~$0.23/hr (CPU) or ~$3/hr (GPU)
- **Endpoint**: ~$0.12/hr (ml.m5.large)
- **Tip**: Delete endpoints when not in use to avoid charges
