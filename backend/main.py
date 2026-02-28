"""
FastAPI service for album recognition.
Works locally. For SageMaker, use API Gateway + Lambda → SageMaker endpoint.
"""
import os
import io
from pathlib import Path

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from dotenv import load_dotenv

# Load from backend/.env.local (works regardless of CWD)
_env_local = Path(__file__).resolve().parent / ".env.local"
load_dotenv(_env_local)
load_dotenv()

from ml.inference import model_fn, predict_fn
from data.downloader import load_manifest, download_all
from data.enrich import enrich_manifest

app = FastAPI(title="Album Recognition API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://127.0.0.1:3000", "http://127.0.0.1:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_model_bundle = None
_releases = None


def _get_model():
    global _model_bundle, _releases
    if _model_bundle is None:
        model_dir = os.getenv("MODEL_PATH", "models")
        if not os.path.exists(os.path.join(model_dir, "model.pth")):
            return None, None
        _model_bundle = model_fn(model_dir)
        _releases = _model_bundle.get("metadata", {}).get("releases", [])
    return _model_bundle, _releases


@app.on_event("startup")
async def startup():
    _get_model()


@app.get("/")
async def root():
    return {"message": "Album Recognition API is running"}


@app.get("/api/health")
async def health():
    bundle, releases = _get_model()
    return {
        "status": "healthy" if bundle else "degraded",
        "model_loaded": bundle is not None,
        "data_loaded": releases is not None,
        "num_releases": len(releases) if releases else 0,
    }


@app.get("/api/releases")
async def get_releases():
    _, releases = _get_model()
    if releases is None:
        raise HTTPException(503, "Service not initialized")
    return {"count": len(releases), "releases": releases}


@app.post("/api/enrich-manifest")
async def enrich_manifest_endpoint():
    """Fetch image URLs from Discogs API and update manifest."""
    user_token = os.getenv("DISCOGS_USER_TOKEN")
    key = os.getenv("DISCOGS_CONSUMER_KEY")
    secret = os.getenv("DISCOGS_CONSUMER_SECRET")
    if not user_token and (not key or not secret):
        raise HTTPException(400, "Set DISCOGS_USER_TOKEN or DISCOGS_CONSUMER_KEY + DISCOGS_CONSUMER_SECRET")

    project_root = Path(__file__).resolve().parent.parent
    manifest_path = str(project_root / "data" / "releases_manifest.jsonl")
    if not os.path.exists(manifest_path):
        raise HTTPException(400, f"Manifest not found: {manifest_path}")

    try:
        checkpoint_path = str(Path(manifest_path).parent / "enrich_checkpoint.json")
        with_images = await enrich_manifest(
            manifest_path, manifest_path, key or "", secret or "", checkpoint_path,
            user_token=user_token,
        )
        return {"success": True, "releases_with_images": with_images}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/download-images")
async def download_images():
    """Download images from Discogs URLs in the manifest."""
    project_root = Path(__file__).resolve().parent.parent
    manifest_path = os.getenv("MANIFEST_PATH") or str(project_root / "data" / "releases_manifest.jsonl")
    images_dir = os.getenv("IMAGES_PATH") or str(project_root / "data" / "images")

    if not os.path.exists(manifest_path):
        raise HTTPException(400, f"Manifest not found: {manifest_path}")

    try:
        stats = await download_all(manifest_path, images_dir)
        return {
            "success": True,
            "downloaded": stats["downloaded"],
            "failed": stats["failed"],
            "skipped": stats["skipped"],
        }
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    bundle, releases = _get_model()
    if bundle is None or releases is None:
        raise HTTPException(503, "Model not loaded. Train first.")

    contents = await file.read()
    image = Image.open(io.BytesIO(contents)).convert("RGB")
    predictions = predict_fn(image, bundle)
    return {"success": True, "predictions": predictions}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
