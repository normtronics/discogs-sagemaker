#!/usr/bin/env python3
"""
Push trained model (model.pth + metadata.json) to Hugging Face Hub.
Creates a model repo if it doesn't exist.

Usage:
  python push_to_huggingface.py --model-dir models --repo-id username/dsicogs-album-classifier
  HF_TOKEN=hf_xxx python push_to_huggingface.py --model-dir models --repo-id username/dsicogs-album-classifier
"""
import argparse
import os
from pathlib import Path

# Load .env.local from backend/
_backend = Path(__file__).resolve().parent.parent
_env = _backend / ".env.local"
if _env.exists():
    from dotenv import load_dotenv
    load_dotenv(_env)

try:
    from huggingface_hub import HfApi, create_repo
except ImportError:
    raise SystemExit("Install: pip install huggingface_hub")


def main():
    p = argparse.ArgumentParser(description="Push model to Hugging Face Hub")
    p.add_argument("--model-dir", type=str, default="models", help="Local dir with model.pth and metadata.json")
    p.add_argument("--repo-id", type=str, required=True, help="Hugging Face repo, e.g. username/dsicogs-album-classifier")
    p.add_argument("--private", action="store_true", help="Create private repo")
    args = p.parse_args()

    model_dir = Path(args.model_dir)
    model_path = model_dir / "model.pth"
    meta_path = model_dir / "metadata.json"

    if not model_path.exists():
        raise SystemExit(f"Model not found: {model_path}")
    if not meta_path.exists():
        raise SystemExit(f"Metadata not found: {meta_path}")

    token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN or HUGGING_FACE_HUB_TOKEN (huggingface-cli login or env var)")

    api = HfApi(token=token)

    # Create repo if needed
    try:
        create_repo(args.repo_id, private=args.private, token=token, exist_ok=True)
    except Exception as e:
        print(f"Note: {e}")

    # Upload files
    print(f"Uploading to {args.repo_id}...")
    api.upload_file(
        path_or_fileobj=str(model_path),
        path_in_repo="model.pth",
        repo_id=args.repo_id,
        repo_type="model",
        token=token,
    )
    api.upload_file(
        path_or_fileobj=str(meta_path),
        path_in_repo="metadata.json",
        repo_id=args.repo_id,
        repo_type="model",
        token=token,
    )
    print(f"✓ Model uploaded to https://huggingface.co/{args.repo_id}")


if __name__ == "__main__":
    main()
