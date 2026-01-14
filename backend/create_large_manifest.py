#!/usr/bin/env python3
"""
Create manifest file with 100,000 releases from Discogs
Uses Discogs search API to fetch releases efficiently
"""
import os
import json
import time
import requests
from typing import List, Dict
from dotenv import load_dotenv
from pathlib import Path
import sys

load_dotenv('.env.local')
load_dotenv()


def fetch_releases_batch(page: int, per_page: int, consumer_key: str, consumer_secret: str) -> List[Dict]:
    """Fetch a batch of releases from Discogs"""
    headers = {
        "User-Agent": "AlbumRecognitionApp/1.0",
        "Authorization": f"Discogs key={consumer_key}, secret={consumer_secret}"
    }
    
    # Search for releases with images (format=album gets studio albums)
    params = {
        'type': 'release',
        'format': 'album',
        'per_page': per_page,
        'page': page
    }
    
    try:
        url = "https://api.discogs.com/database/search"
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        
        data = response.json()
        releases = []
        
        for item in data.get('results', []):
            # Only include releases with covers
            if item.get('cover_image') and item.get('cover_image') != '':
                release = {
                    'release_id': item['id'],
                    'title': item.get('title', 'Unknown'),
                    'artists': [item.get('title', '').split(' - ')[0]] if ' - ' in item.get('title', '') else ['Unknown'],
                    'labels': [],
                    'released': item.get('year', 'Unknown'),
                    'cover_image': item.get('cover_image', ''),
                    'thumb': item.get('thumb', '')
                }
                releases.append(release)
        
        return releases
    except Exception as e:
        print(f"Error fetching page {page}: {str(e)}")
        return []


def create_manifest(
    target_count: int = 100000,
    output_path: str = "../data/releases_manifest.jsonl",
    checkpoint_path: str = "../data/manifest_checkpoint.json"
):
    """
    Create a manifest file with target_count releases
    
    Args:
        target_count: Number of releases to fetch
        output_path: Path to save manifest
        checkpoint_path: Path to save progress
    """
    consumer_key = os.getenv("DISCOGS_CONSUMER_KEY")
    consumer_secret = os.getenv("DISCOGS_CONSUMER_SECRET")
    
    if not consumer_key or not consumer_secret:
        print("Error: DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET not set")
        sys.exit(1)
    
    # Load checkpoint if exists
    start_page = 1
    collected_releases = []
    
    if os.path.exists(checkpoint_path):
        print(f"Found checkpoint at {checkpoint_path}")
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
            start_page = checkpoint.get('last_page', 1) + 1
            collected_releases = checkpoint.get('releases', [])
        print(f"Resuming from page {start_page}, already have {len(collected_releases)} releases")
    
    print(f"\n{'='*60}")
    print(f"Fetching {target_count} releases from Discogs")
    print(f"{'='*60}\n")
    
    per_page = 100  # Max allowed by Discogs
    page = start_page
    rate_limit_delay = 1.1  # Discogs allows ~60 requests/minute
    
    # Calculate estimates
    remaining = target_count - len(collected_releases)
    pages_needed = (remaining + per_page - 1) // per_page
    estimated_minutes = (pages_needed * rate_limit_delay) / 60
    
    print(f"Need {remaining} more releases")
    print(f"Estimated pages: {pages_needed}")
    print(f"Estimated time: {estimated_minutes:.1f} minutes (~{estimated_minutes/60:.1f} hours)")
    print(f"Rate limit: {rate_limit_delay}s between requests\n")
    
    start_time = time.time()
    
    try:
        while len(collected_releases) < target_count:
            print(f"Fetching page {page}... ({len(collected_releases)}/{target_count} releases)")
            
            # Fetch batch
            releases = fetch_releases_batch(page, per_page, consumer_key, consumer_secret)
            
            if not releases:
                print(f"No releases on page {page}, trying next page...")
                page += 1
                time.sleep(rate_limit_delay)
                continue
            
            # Add new releases
            for release in releases:
                if len(collected_releases) >= target_count:
                    break
                
                # Avoid duplicates
                if not any(r['release_id'] == release['release_id'] for r in collected_releases):
                    collected_releases.append(release)
            
            # Save checkpoint every 10 pages
            if page % 10 == 0:
                with open(checkpoint_path, 'w') as f:
                    json.dump({
                        'last_page': page,
                        'releases': collected_releases,
                        'timestamp': time.time()
                    }, f)
                
                # Progress update
                elapsed = time.time() - start_time
                rate = len(collected_releases) / elapsed if elapsed > 0 else 0
                remaining_time = (target_count - len(collected_releases)) / rate if rate > 0 else 0
                
                print(f"Progress: {len(collected_releases)}/{target_count} "
                      f"({len(collected_releases)/target_count*100:.1f}%) - "
                      f"ETA: {remaining_time/60:.1f} minutes")
            
            page += 1
            
            # Rate limiting
            time.sleep(rate_limit_delay)
            
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving checkpoint...")
        with open(checkpoint_path, 'w') as f:
            json.dump({
                'last_page': page,
                'releases': collected_releases,
                'timestamp': time.time()
            }, f)
        print(f"Checkpoint saved with {len(collected_releases)} releases")
        print(f"Run again to resume from page {page + 1}")
        sys.exit(0)
    
    # Save final manifest
    print(f"\n{'='*60}")
    print(f"Writing manifest to {output_path}")
    print(f"{'='*60}\n")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for release in collected_releases:
            f.write(json.dumps(release) + '\n')
    
    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    
    elapsed = time.time() - start_time
    
    print(f"✓ Created manifest with {len(collected_releases)} releases")
    print(f"✓ Time taken: {elapsed/60:.1f} minutes ({elapsed/3600:.2f} hours)")
    print(f"✓ Average rate: {len(collected_releases)/(elapsed/60):.1f} releases/minute")
    print(f"\nNext step: Download images")
    print(f"  python backend/batch_download_images.py")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Create Discogs releases manifest')
    parser.add_argument('--count', type=int, default=100000,
                        help='Number of releases to fetch (default: 100000)')
    parser.add_argument('--output', type=str, default='../data/releases_manifest.jsonl',
                        help='Output file path')
    
    args = parser.parse_args()
    
    create_manifest(target_count=args.count, output_path=args.output)

