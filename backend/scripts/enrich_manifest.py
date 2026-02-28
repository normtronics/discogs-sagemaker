#!/usr/bin/env python3
"""
Enrich manifest with image URLs from Discogs API.
Takes manifest without images and adds image URLs.
Supports checkpoint/resume for long runs.
"""
import os
import sys
import asyncio
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load from backend/.env.local (works regardless of CWD)
_env_local = Path(__file__).resolve().parent.parent / ".env.local"
load_dotenv(_env_local)
load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.enrich import enrich_manifest


def main():
    parser = argparse.ArgumentParser(description="Enrich manifest with image URLs from Discogs API")
    parser.add_argument("--input", default="data/releases_manifest.jsonl", help="Input manifest file")
    parser.add_argument("--output", default="data/releases_manifest_enriched.jsonl", help="Output enriched manifest")
    parser.add_argument("--checkpoint", default="data/enrich_checkpoint.json", help="Checkpoint file for resume")
    args = parser.parse_args()

    key = os.environ.get("DISCOGS_CONSUMER_KEY")
    secret = os.environ.get("DISCOGS_CONSUMER_SECRET")
    if not key or not secret:
        print("Error: DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET not set")
        sys.exit(1)

    project_root = Path(__file__).resolve().parent.parent.parent
    input_path = project_root / args.input
    output_path = project_root / args.output
    checkpoint_path = project_root / args.checkpoint

    if not input_path.exists():
        print(f"Manifest not found: {input_path}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print("Enriching Manifest with Image URLs")
    print(f"{'='*60}\n")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}\n")

    asyncio.run(
        enrich_manifest(
            str(input_path),
            str(output_path),
            key,
            secret,
            str(checkpoint_path),
        )
    )

    print(f"\nNext: Download images")
    print(f"  python backend/scripts/download_images.py --manifest data/releases_manifest_enriched.jsonl")


if __name__ == "__main__":
    main()
