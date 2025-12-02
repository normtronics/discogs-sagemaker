# Album Recognition API

FastAPI backend for album cover recognition using PyTorch and transfer learning.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env.local` and add your Discogs credentials:
```bash
cp .env.example .env.local
```

3. Get Discogs API credentials from: https://www.discogs.com/settings/developers

## Usage

### 1. Start the API server
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### 2. Download album images
```bash
curl -X POST http://localhost:8000/api/download-images
```

This will download images from Discogs for the first 50 releases.

### 3. Train the model
```bash
curl -X POST http://localhost:8000/api/train
```

This trains a ResNet50 model using transfer learning on the downloaded images.

### 4. Make predictions
Upload an image to get album predictions:
```bash
curl -X POST -F "file=@album_cover.jpg" http://localhost:8000/api/predict
```

## API Endpoints

- `GET /` - API status
- `GET /api/releases` - List all releases in dataset
- `POST /api/download-images` - Download images from Discogs
- `POST /api/train` - Train classification model
- `POST /api/predict` - Predict album from uploaded image
- `GET /api/health` - Health check

## Architecture

- **FastAPI**: Web framework for the API
- **PyTorch**: Deep learning framework
- **ResNet50**: Pre-trained model for transfer learning
- **Discogs API**: Source for album images

## Environment Variables

- `DISCOGS_CONSUMER_KEY`: Your Discogs consumer key
- `DISCOGS_CONSUMER_SECRET`: Your Discogs consumer secret
- `MODEL_PATH`: Path to save/load the trained model (default: `./models/album_classifier.pth`)
- `IMAGES_PATH`: Path to store downloaded images (default: `./data/images`)

