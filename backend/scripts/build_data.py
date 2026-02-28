#!/usr/bin/env python3
"""
Build dataset from Discogs: XML → JSONL → download images.
Single entry point for data pipeline. Works locally and in SageMaker.
"""
import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load from backend/.env.local (works regardless of CWD)
load_dotenv(Path(__file__).resolve().parent.parent / ".env.local")
load_dotenv()

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.parser import (
    get_latest_dump_url,
    download_dump,
    process_dump_to_jsonl,
)
from data.enrich import enrich_manifest
from data.downloader import load_manifest, download_all


def main():
    parser = argparse.ArgumentParser(
        description="Build dataset: parse Discogs XML → JSONL → download images"
    )
    parser.add_argument(
        "--dump-file",
        type=str,
        default="data/discogs_releases.xml.gz",
        help="Path to XML dump (or where to save it)",
    )
    parser.add_argument(
        "--manifest",
        type=str,
        default="data/releases_manifest.jsonl",
        help="Output JSONL manifest path",
    )
    parser.add_argument(
        "--images-dir",
        type=str,
        default="data/images",
        help="Directory for downloaded images",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=500,
        help="Max releases to extract (default: 500)",
    )
    parser.add_argument(
        "--skip-download-dump",
        action="store_true",
        help="Skip dump download if file exists",
    )
    parser.add_argument(
        "--skip-download-images",
        action="store_true",
        help="Skip image download (only parse XML)",
    )
    parser.add_argument(
        "--skip-enrich",
        action="store_true",
        help="Skip Discogs API enrich (manifest will have no image URLs)",
    )
    parser.add_argument(
        "--dump-url",
        type=str,
        default=None,
        help="Direct URL to dump file",
    )
    parser.add_argument(
        "--concurrent",
        type=int,
        default=10,
        help="Concurrent image downloads",
    )

    args = parser.parse_args()

    # Resolve paths relative to project root
    project_root = Path(__file__).resolve().parent.parent.parent
    dump_path = project_root / args.dump_file
    manifest_path = project_root / args.manifest
    images_dir = project_root / args.images_dir

    print("\n" + "=" * 60)
    print("Build Dataset")
    print("=" * 60)
    print(f"Dump: {dump_path}")
    print(f"Manifest: {manifest_path}")
    print(f"Images: {images_dir}")
    print(f"Max releases: {args.count}")
    print("=" * 60 + "\n")

    # Step 1: Get dump if needed
    if not args.skip_download_dump or not dump_path.exists():
        url = args.dump_url or get_latest_dump_url()
        download_dump(url, str(dump_path))
    else:
        print(f"✓ Using existing dump: {dump_path}")

    # Step 2: Parse XML → JSONL
    process_dump_to_jsonl(
        dump_path=str(dump_path),
        output_path=str(manifest_path),
        max_releases=args.count,
    )

    # Step 3: Enrich with image URLs via Discogs API (XML dump has no images)
    if not args.skip_enrich:
        user_token = os.environ.get("DISCOGS_USER_TOKEN")
        key = os.environ.get("DISCOGS_CONSUMER_KEY")
        secret = os.environ.get("DISCOGS_CONSUMER_SECRET")
        if user_token or (key and secret):
            import asyncio
            checkpoint = str(Path(manifest_path).parent / "enrich_checkpoint.json")
            asyncio.run(enrich_manifest(
                str(manifest_path), str(manifest_path), key or "", secret or "", checkpoint,
                user_token=user_token,
            ))
        else:
            print("\n⚠ Skipping enrich: set DISCOGS_USER_TOKEN or DISCOGS_CONSUMER_KEY + DISCOGS_CONSUMER_SECRET")
            print("  User token: https://www.discogs.com/settings/developers → Generate new token")

    # Step 4: Download images (only for releases with cover_image)
    if not args.skip_download_images:
        print("\nDownloading images...")
        import asyncio
        stats = asyncio.run(
            download_all(
                str(manifest_path),
                str(images_dir),
                max_concurrent=args.concurrent,
            )
        )
        print(f"\n✓ Done: downloaded={stats['downloaded']}, "
              f"failed={stats['failed']}, skipped={stats['skipped']}")

    print("\n" + "=" * 60)
    print("Build complete!")
    print("=" * 60)
    print(f"Manifest: {manifest_path}")
    print(f"Images: {images_dir}")
    print("\nNext: train model with `python -m scripts.train`")


if __name__ == "__main__":
    main()
