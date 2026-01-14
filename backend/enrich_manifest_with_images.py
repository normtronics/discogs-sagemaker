#!/usr/bin/env python3
"""
Enrich existing manifest with image URLs from Discogs API
Takes manifest without images and adds image URLs
"""
import os
import json
import asyncio
import aiohttp
from pathlib import Path
from dotenv import load_dotenv
import sys

load_dotenv('.env.local')
load_dotenv()


async def fetch_release_images(session, release_id, consumer_key, consumer_secret):
    """Fetch image URLs for a release from Discogs API"""
    headers = {
        "User-Agent": "AlbumRecognitionApp/1.0",
        "Authorization": f"Discogs key={consumer_key}, secret={consumer_secret}"
    }
    
    try:
        await asyncio.sleep(1.1)  # Rate limit: ~60 req/min
        
        url = f"https://api.discogs.com/releases/{release_id}"
        async with session.get(url, headers=headers, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                images = data.get("images", [])
                
                # Get primary or first image
                cover_image = None
                thumb = None
                
                for img in images:
                    if img.get("type") == "primary":
                        cover_image = img.get("uri")
                        thumb = img.get("uri150", img.get("uri"))
                        break
                
                if not cover_image and images:
                    cover_image = images[0].get("uri")
                    thumb = images[0].get("uri150", images[0].get("uri"))
                
                return {
                    "cover_image": cover_image,
                    "thumb": thumb,
                    "image_count": len(images)
                }
            else:
                print(f"  Failed to fetch {release_id}: HTTP {response.status}")
                return None
                
    except Exception as e:
        print(f"  Error fetching {release_id}: {str(e)[:50]}")
        return None


async def enrich_manifest(input_path, output_path, checkpoint_path):
    """Enrich manifest with image URLs"""
    
    consumer_key = os.getenv("DISCOGS_CONSUMER_KEY")
    consumer_secret = os.getenv("DISCOGS_CONSUMER_SECRET")
    
    if not consumer_key or not consumer_secret:
        print("Error: DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET not set")
        sys.exit(1)
    
    print(f"\n{'='*60}")
    print("Enriching Manifest with Image URLs")
    print(f"{'='*60}\n")
    print(f"Input: {input_path}")
    print(f"Output: {output_path}")
    
    # Load existing manifest
    releases = []
    with open(input_path, 'r') as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))
    
    print(f"Loaded {len(releases)} releases")
    
    # Load checkpoint if exists
    start_idx = 0
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
            start_idx = checkpoint.get('last_index', 0) + 1
        print(f"Resuming from index {start_idx}")
    
    # Estimate time
    remaining = len(releases) - start_idx
    minutes = remaining * 1.1 / 60  # 1.1 seconds per request
    print(f"Estimated time: {minutes:.1f} minutes ({minutes/60:.1f} hours)\n")
    
    enriched = []
    
    try:
        async with aiohttp.ClientSession() as session:
            for idx, release in enumerate(releases):
                if idx < start_idx:
                    # Skip already processed
                    enriched.append(release)
                    continue
                
                release_id = release['release_id']
                print(f"[{idx+1}/{len(releases)}] Fetching images for release {release_id}...")
                
                image_data = await fetch_release_images(
                    session, release_id, consumer_key, consumer_secret
                )
                
                if image_data and image_data['cover_image']:
                    # Add image URLs
                    release['cover_image'] = image_data['cover_image']
                    release['thumb'] = image_data['thumb']
                    release['image_count'] = image_data['image_count']
                    release['has_images'] = True
                    enriched.append(release)
                    print(f"  ✓ Found {image_data['image_count']} images")
                else:
                    # Keep release but mark as no images
                    release['has_images'] = False
                    release['image_count'] = 0
                    enriched.append(release)
                    print(f"  ✗ No images found")
                
                # Save checkpoint every 10 releases
                if (idx + 1) % 10 == 0:
                    with open(checkpoint_path, 'w') as f:
                        json.dump({'last_index': idx}, f)
                    print(f"  Checkpoint saved at {idx + 1}")
                
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving progress...")
        with open(checkpoint_path, 'w') as f:
            json.dump({'last_index': idx}, f)
        print(f"Checkpoint saved. Run again to resume from {idx + 1}")
        sys.exit(0)
    
    # Write enriched manifest
    print(f"\nWriting enriched manifest...")
    with open(output_path, 'w') as f:
        for release in enriched:
            f.write(json.dumps(release) + '\n')
    
    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    
    # Stats
    with_images = sum(1 for r in enriched if r.get('has_images'))
    
    print(f"\n{'='*60}")
    print("Enrichment Complete!")
    print(f"{'='*60}\n")
    print(f"Total releases: {len(enriched)}")
    print(f"With images: {with_images}")
    print(f"Without images: {len(enriched) - with_images}")
    print(f"\nNext: Download images")
    print(f"  python batch_download_images.py")


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Enrich manifest with image URLs')
    parser.add_argument(
        '--input', type=str, default='../data/releases_manifest_50.jsonl',
        help='Input manifest file'
    )
    parser.add_argument(
        '--output', type=str, default='../data/releases_manifest_enriched.jsonl',
        help='Output enriched manifest file'
    )
    parser.add_argument(
        '--checkpoint', type=str, default='../data/enrich_checkpoint.json',
        help='Checkpoint file path'
    )
    
    args = parser.parse_args()
    
    await enrich_manifest(args.input, args.output, args.checkpoint)


if __name__ == "__main__":
    asyncio.run(main())

