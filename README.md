# Discogs Sage - Album Recognition App

AI-powered album cover recognition system using PyTorch, FastAPI, and Next.js.

## Features

- 🎵 Album cover recognition using deep learning
- 🖼️ Drag & drop image upload interface
- 📊 Confidence scores for top 5 predictions
- 🎨 Modern, responsive UI with dark mode support
- 🚀 FastAPI backend with PyTorch model serving
- 📦 Transfer learning with ResNet50

## Project Structure

```
discogs-sage-app/
├── backend/          # FastAPI + PyTorch backend
│   ├── main.py              # API endpoints
│   ├── model_service.py     # Model inference
│   ├── model_trainer.py     # Model training
│   ├── image_downloader.py  # Discogs image fetcher
│   ├── data_loader.py       # Data utilities
│   └── requirements.txt     # Python dependencies
├── frontend/         # Next.js frontend
│   └── src/
│       └── app/
│           └── page.tsx     # Main upload interface
└── data/            # Data files
    └── releases_manifest_50.jsonl  # First 50 releases
```

## Setup

### Backend

1. Navigate to backend directory:
```bash
cd backend
```

2. Create virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Copy environment file and add your Discogs API token:
```bash
cp .env.example .env.local
# Edit .env.local and add your DISCOGS_API_TOKEN
```

Get a Discogs API token from: https://www.discogs.com/settings/developers

5. Start the backend:
```bash
python main.py
```

The API will be available at `http://localhost:8000`

### Frontend

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start development server:
```bash
npm run dev
```

The app will be available at `http://localhost:3000`

## Usage

### 1. Download Album Images

First, download album cover images from Discogs:

```bash
curl -X POST http://localhost:8000/api/download-images
```

This will download images for the first 50 releases from your manifest file.

### 2. Train the Model

Train the classification model:

```bash
curl -X POST http://localhost:8000/api/train
```

This trains a ResNet50 model using transfer learning on the downloaded images. Training takes a few minutes.

### 3. Use the Web Interface

1. Open `http://localhost:3000` in your browser
2. Upload or drag & drop an album cover image
3. Click "Identify Album"
4. View the top 5 predictions with confidence scores

## API Endpoints

- `GET /` - API status
- `GET /api/releases` - List all releases in dataset
- `GET /api/health` - Health check
- `POST /api/download-images` - Download images from Discogs
- `POST /api/train` - Train classification model
- `POST /api/predict` - Predict album from uploaded image

## Architecture

### Backend
- **FastAPI**: Modern Python web framework
- **PyTorch**: Deep learning framework
- **ResNet50**: Pre-trained CNN for image classification
- **Transfer Learning**: Fine-tuned on album covers

### Frontend
- **Next.js 15**: React framework with App Router
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first styling
- **Modern UI**: Drag & drop, dark mode, responsive

## Model Details

- **Base Model**: ResNet50 pre-trained on ImageNet
- **Architecture**: Transfer learning with frozen early layers
- **Input**: 224x224 RGB images
- **Output**: Softmax probabilities over 50 album classes
- **Training**: Data augmentation with horizontal flips and color jitter
- **Optimizer**: Adam with learning rate scheduling

## Environment Variables

### Backend (.env.local)
- `DISCOGS_API_TOKEN`: Your Discogs API token
- `MODEL_PATH`: Path to trained model (default: `./models/album_classifier.pth`)
- `IMAGES_PATH`: Path to album images (default: `./data/images`)

### Frontend (.env.local)
- `NEXT_PUBLIC_API_URL`: Backend API URL (default: `http://localhost:8000`)

## Development

### Backend Development
```bash
cd backend
python main.py
```

### Frontend Development
```bash
cd frontend
npm run dev
```

### Testing the API
```bash
# Test prediction with curl
curl -X POST -F "file=@album_cover.jpg" http://localhost:8000/api/predict
```

## Future Enhancements

- [ ] Expand to full Discogs catalog
- [ ] Add batch prediction support
- [ ] Implement image similarity search
- [ ] Add user feedback for model improvement
- [ ] Deploy to AWS SageMaker for production
- [ ] Add caching for faster predictions
- [ ] Support for multi-image input

## License

MIT

