import os
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import torch
from PIL import Image
import io
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path

from model_service import AlbumClassifier
from data_loader import load_releases_data

# Load .env.local file (falls back to .env if not found)
load_dotenv('.env.local')
load_dotenv()  # Fallback to .env

app = FastAPI(title="Album Recognition API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001"
    ],  # Allow common Next.js ports
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instance
classifier = None
releases_data = None


@app.on_event("startup")
async def startup_event():
    """Initialize model and data on startup"""
    global classifier, releases_data
    
    model_path = os.getenv("MODEL_PATH", "./models/album_classifier.pth")
    images_path = os.getenv("IMAGES_PATH", "./data/images")
    
    # Load releases data - try multiple possible paths
    possible_manifests = [
        "../data/releases_manifest_enriched.jsonl",
        "../data/releases_manifest.jsonl",
        "../data/releases_metadata.jsonl",
        "../data/releases_manifest_50.jsonl",
    ]
    
    releases_data = None
    for manifest_path in possible_manifests:
        try:
            if os.path.exists(manifest_path):
                releases_data = load_releases_data(manifest_path)
                print(f"Loaded {len(releases_data)} releases from {manifest_path}")
                break
        except:
            continue
    
    if not releases_data:
        print("Warning: No manifest file found, using empty dataset")
        releases_data = []
    
    # Initialize classifier
    classifier = AlbumClassifier(
        model_path=model_path,
        num_classes=len(releases_data),
        images_path=images_path
    )
    
    print(f"Loaded {len(releases_data)} releases")


@app.get("/")
async def root():
    return {"message": "Album Recognition API is running"}


@app.get("/api/releases")
async def get_releases():
    """Get list of all releases in the dataset"""
    if releases_data is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    return {
        "count": len(releases_data),
        "releases": releases_data
    }


@app.post("/api/download-images")
async def download_images():
    """Download images from Discogs for all releases"""
    from image_downloader import download_all_images
    
    if releases_data is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        consumer_key = os.getenv("DISCOGS_CONSUMER_KEY")
        consumer_secret = os.getenv("DISCOGS_CONSUMER_SECRET")
        
        if not consumer_key or not consumer_secret:
            raise HTTPException(status_code=400, detail="DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET not set")
        
        images_path = os.getenv("IMAGES_PATH", "./data/images")
        results = await download_all_images(releases_data, images_path, consumer_key, consumer_secret)
        
        return {
            "success": True,
            "downloaded": results["downloaded"],
            "failed": results["failed"],
            "total": len(releases_data)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/train")
async def train_model():
    """Train the album classification model"""
    from model_trainer import train_model
    
    if releases_data is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        images_path = os.getenv("IMAGES_PATH", "./data/images")
        model_path = os.getenv("MODEL_PATH", "./models/album_classifier.pth")
        
        # Create models directory if it doesn't exist
        Path(model_path).parent.mkdir(parents=True, exist_ok=True)
        
        results = train_model(images_path, releases_data, model_path)
        
        # Reload the classifier with the new model
        global classifier
        classifier = AlbumClassifier(
            model_path=model_path,
            num_classes=len(releases_data),
            images_path=images_path
        )
        
        return {
            "success": True,
            "message": "Model trained successfully",
            "accuracy": results.get("accuracy", 0),
            "epochs": results.get("epochs", 0)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/predict")
async def predict_album(file: UploadFile = File(...)):
    """Predict album from uploaded image"""
    if classifier is None or releases_data is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    try:
        # Read image file
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Get predictions
        predictions = classifier.predict(image, top_k=5)
        
        # Format results
        results = []
        for pred in predictions:
            release = releases_data[pred["class_idx"]]
            results.append({
                "release_id": release["release_id"],
                "title": release["title"],
                "artists": release["artists"],
                "confidence": pred["confidence"],
                "labels": release.get("labels", []),
                "released": release.get("released", "Unknown")
            })
        
        return {
            "success": True,
            "predictions": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    model_loaded = classifier is not None and classifier.model is not None
    data_loaded = releases_data is not None
    
    return {
        "status": "healthy" if (model_loaded and data_loaded) else "degraded",
        "model_loaded": model_loaded,
        "data_loaded": data_loaded,
        "num_releases": len(releases_data) if releases_data else 0
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

