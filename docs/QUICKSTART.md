# Quick Start Guide

Get the album recognition system running in 5 minutes!

## Prerequisites

- Python 3.8+
- Node.js 18+
- Discogs API credentials (configured)

## Step 1: Backend Setup (2 minutes)

```bash
cd backend

# Run setup script
./setup.sh

# Environment file already configured with your Discogs credentials

# Start the API server
./run.sh
```

The backend will be running at `http://localhost:8000`

## Step 2: Download Images & Train Model (5-10 minutes)

In a new terminal:

```bash
# Download album images from Discogs
curl -X POST http://localhost:8000/api/download-images

# Train the model (takes ~5 minutes)
curl -X POST http://localhost:8000/api/train
```

## Step 3: Frontend Setup (1 minute)

In a new terminal:

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server
npm run dev
```

The app will be running at `http://localhost:3000`

## Step 4: Try It Out!

1. Open `http://localhost:3000`
2. Upload or drag & drop an album cover image
3. Click "Identify Album"
4. See the top 5 predictions with confidence scores!

## Troubleshooting

### Backend won't start
- Make sure Python 3.8+ is installed: `python3 --version`
- Activate virtual environment: `source venv/bin/activate`
- Check if port 8000 is available

### Images won't download
- Verify your DISCOGS_API_TOKEN in `.env.local`
- Check API rate limits (1 request per second)
- Make sure `data/images` directory exists

### Model training fails
- Ensure images were downloaded first
- Check you have at least 10 valid images
- Verify PyTorch is installed: `python -c "import torch; print(torch.__version__)"`

### Frontend errors
- Verify backend is running at `http://localhost:8000`
- Check browser console for CORS errors
- Make sure Node.js 18+ is installed

## Next Steps

- Try different album covers
- Check prediction confidence scores
- Expand to more albums by updating the manifest file
- Deploy to production using AWS SageMaker

## API Testing

Test the API directly with curl:

```bash
# Check API health
curl http://localhost:8000/api/health

# Get all releases
curl http://localhost:8000/api/releases

# Test prediction
curl -X POST -F "file=@your_album.jpg" http://localhost:8000/api/predict
```

## Development Tips

### Watch backend logs
```bash
cd backend
./run.sh
```

### Auto-reload frontend
```bash
cd frontend
npm run dev
```

### Retrain model with new data
```bash
# Add more releases to releases_manifest_50.jsonl
# Download new images
curl -X POST http://localhost:8000/api/download-images
# Retrain
curl -X POST http://localhost:8000/api/train
```

