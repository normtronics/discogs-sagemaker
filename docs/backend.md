# Backend

Simplified backend: build data, train model, serve predictions. Works locally and in SageMaker.

## Structure

```
backend/
├── data/           # Data pipeline
│   ├── parser.py   # XML → JSONL (Discogs dump)
│   └── downloader.py  # Download images
├── ml/             # Training & inference
│   ├── dataset.py  # Dataset, load_releases_data
│   ├── model.py    # ResNet50
│   ├── train.py    # Training (local + SageMaker)
│   └── inference.py  # Prediction (local + SageMaker)
├── scripts/
│   ├── build_data.py  # CLI: XML → JSONL → images
│   └── train.py       # CLI: train model
├── main.py         # FastAPI service
└── requirements.txt
```

## Quick Start

### 1. Build data (XML → JSONL → images)

```bash
# From project root
python backend/scripts/build_data.py --count 500

# Options:
#   --dump-file    Path to XML dump (default: data/discogs_releases.xml.gz)
#   --manifest     Output JSONL (default: data/releases_manifest.jsonl)
#   --images-dir   Images output (default: data/images)
#   --count        Max releases (default: 500)
#   --skip-download-dump   Use existing dump
#   --skip-download-images Only parse XML, don't download images
```

### 2. Train model

```bash
cd backend
python -m scripts.train --data-dir ../data --model-dir models

# Or from project root:
python backend/scripts/train.py --data-dir data --model-dir backend/models
```

### 3. Run service (local)

```bash
cd backend
python main.py
# API at http://localhost:8000
```

### 4. SageMaker

- **Training**: Package `ml/` folder, use `train.py` as entry point
- **Inference**: Use `inference.py` (model_fn, input_fn, predict_fn, output_fn)
- **API**: Deploy InferenceStack (API Gateway + Lambda → SageMaker endpoint)

## Environment

- `MODEL_PATH` - Model directory (default: models)
- `DISCOGS_*` - Not needed for XML dump (images come from XML)
