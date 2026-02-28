#!/usr/bin/env python3
"""Download images from manifest. Run from project root or backend."""
import sys
import asyncio
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.downloader import download_all


def main():
    parser = argparse.ArgumentParser(description="Download images from manifest")
    parser.add_argument("--manifest", default="data/releases_manifest.jsonl", help="Manifest path")
    parser.add_argument("--images-dir", default="data/images", help="Images output dir")
    parser.add_argument("--concurrent", type=int, default=10, help="Concurrent downloads")
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent.parent.parent
    manifest_path = project_root / args.manifest
    images_dir = project_root / args.images_dir

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}")
        sys.exit(1)

    print(f"Manifest: {manifest_path}")
    print(f"Images: {images_dir}\n")
    stats = asyncio.run(download_all(str(manifest_path), str(images_dir), max_concurrent=args.concurrent))
    print(f"\nDone: downloaded={stats['downloaded']}, failed={stats['failed']}, skipped={stats['skipped']}")


if __name__ == "__main__":
    main()
