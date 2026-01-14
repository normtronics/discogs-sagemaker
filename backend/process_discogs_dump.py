#!/usr/bin/env python3
"""
Process Discogs Data Dump to JSONL
Downloads the latest Discogs release dump and extracts first N releases with images

Data dumps from: https://discogs-data-dumps.s3.us-west-2.amazonaws.com/index.html?prefix=data/2025/
License: CC0 No Rights Reserved
"""
import os
import json
import gzip
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional
import sys
from datetime import datetime


def get_latest_dump_url(year: int = 2025) -> str:
    """
    Get the latest Discogs releases dump URL
    
    The dumps are named like: discogs_20250101_releases.xml.gz
    """
    # Monthly dumps are typically posted early in the month
    # Format: discogs_YYYYMMDD_releases.xml.gz
    
    # For 2025, check January dump
    base_url = "https://data.discogs.com"
    
    # Try January 2025 first
    possible_dates = [
        "20250101",  # January 1
        "20241201",  # December 2024
        "20241101",  # November 2024
    ]
    
    for date in possible_dates:
        url = f"{base_url}/discogs_{date}_releases.xml.gz"
        try:
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                print(f"Found dump: {url}")
                return url
        except:
            continue
    
    # Default to a known good URL
    return "https://discogs-data-dumps.s3.us-west-2.amazonaws.com/data/2025/discogs_20250101_releases.xml.gz"


def download_dump(url: str, output_path: str) -> str:
    """Download Discogs dump file with progress"""
    print(f"\n{'='*60}")
    print("Downloading Discogs Data Dump")
    print(f"{'='*60}\n")
    print(f"URL: {url}")
    print(f"Output: {output_path}")
    
    # Check if already downloaded
    if os.path.exists(output_path):
        file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"\n✓ File already exists ({file_size_mb:.1f} MB)")
        print("Skipping download. Delete the file to re-download.")
        return output_path
    
    print("\nStarting download...")
    print("Note: This file is large (~3-5 GB), may take 10-30 minutes\n")
    
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    
    total_size = int(response.headers.get('content-length', 0))
    total_mb = total_size / (1024 * 1024)
    
    downloaded = 0
    chunk_size = 8192
    
    with open(output_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                
                # Progress update every 50MB
                if downloaded % (50 * 1024 * 1024) < chunk_size:
                    progress_mb = downloaded / (1024 * 1024)
                    percent = (downloaded / total_size * 100) if total_size > 0 else 0
                    print(f"Downloaded: {progress_mb:.1f} MB / {total_mb:.1f} MB ({percent:.1f}%)")
    
    print(f"\n✓ Download complete: {output_path}")
    return output_path


def parse_release(release_elem) -> Optional[Dict]:
    """Parse a release XML element into a dictionary"""
    try:
        release_id = release_elem.get('id')
        if not release_id:
            return None
        
        # Extract title
        title_elem = release_elem.find('title')
        title = title_elem.text if title_elem is not None else "Unknown"
        
        # Extract artists
        artists = []
        artists_elem = release_elem.find('artists')
        if artists_elem is not None:
            for artist in artists_elem.findall('artist'):
                name_elem = artist.find('name')
                if name_elem is not None and name_elem.text:
                    artists.append(name_elem.text)
        
        if not artists:
            artists = ["Unknown Artist"]
        
        # Extract labels
        labels = []
        labels_elem = release_elem.find('labels')
        if labels_elem is not None:
            for label in labels_elem.findall('label'):
                name = label.get('name')
                if name:
                    labels.append(name)
        
        # Extract release date
        released = "Unknown"
        released_elem = release_elem.find('released')
        if released_elem is not None and released_elem.text:
            released = released_elem.text
        
        # Extract images - CRITICAL for training!
        images = []
        images_elem = release_elem.find('images')
        if images_elem is not None:
            for image in images_elem.findall('image'):
                image_type = image.get('type')
                uri = image.get('uri')
                uri150 = image.get('uri150')  # Thumbnail
                
                if uri:
                    images.append({
                        'type': image_type,
                        'uri': uri,
                        'uri150': uri150
                    })
        
        # Only include releases with images (needed for training)
        if not images:
            return None
        
        # Get primary image or first image
        cover_image = None
        thumb = None
        for img in images:
            if img['type'] == 'primary':
                cover_image = img['uri']
                thumb = img['uri150']
                break
        
        if not cover_image and images:
            cover_image = images[0]['uri']
            thumb = images[0]['uri150']
        
        return {
            'release_id': int(release_id),
            'title': title,
            'artists': artists,
            'labels': labels,
            'released': released,
            'cover_image': cover_image,
            'thumb': thumb,
            'image_count': len(images)
        }
        
    except Exception as e:
        # Skip problematic releases
        return None


def process_dump_to_jsonl(
    dump_path: str,
    output_path: str,
    max_releases: int = 100000,
    checkpoint_path: Optional[str] = None
):
    """
    Process Discogs XML dump and create JSONL manifest
    
    Args:
        dump_path: Path to the .xml.gz dump file
        output_path: Path to save JSONL output
        max_releases: Maximum number of releases to extract
        checkpoint_path: Path to save progress
    """
    print(f"\n{'='*60}")
    print("Processing Discogs Dump to JSONL")
    print(f"{'='*60}\n")
    print(f"Input: {dump_path}")
    print(f"Output: {output_path}")
    print(f"Max releases: {max_releases:,}")
    
    if checkpoint_path is None:
        checkpoint_path = f"{output_path}.checkpoint"
    
    # Check for checkpoint
    start_count = 0
    processed_ids = set()
    
    if os.path.exists(checkpoint_path):
        print(f"\nFound checkpoint: {checkpoint_path}")
        with open(checkpoint_path, 'r') as f:
            checkpoint = json.load(f)
            start_count = checkpoint.get('count', 0)
            processed_ids = set(checkpoint.get('processed_ids', []))
        print(f"Resuming from {start_count} releases")
    
    releases = []
    count = start_count
    processed = 0
    skipped_no_images = 0
    
    print(f"\nParsing XML dump (this may take 10-30 minutes)...")
    print("Progress updates every 10,000 releases\n")
    
    try:
        # Open gzipped XML file
        with gzip.open(dump_path, 'rb') as f:
            # Use iterparse for memory efficiency
            context = ET.iterparse(f, events=('start', 'end'))
            context = iter(context)
            
            # Get root
            event, root = next(context)
            
            for event, elem in context:
                if event == 'end' and elem.tag == 'release':
                    release_id = elem.get('id')
                    
                    # Skip if already processed
                    if release_id in processed_ids:
                        root.clear()
                        continue
                    
                    processed += 1
                    
                    # Parse release
                    release_data = parse_release(elem)
                    
                    if release_data:
                        releases.append(release_data)
                        processed_ids.add(release_id)
                        count += 1
                        
                        # Progress update
                        if count % 10000 == 0:
                            print(f"Processed: {count:,} releases with images "
                                  f"(scanned {processed:,} total, "
                                  f"skipped {processed - count:,} without images)")
                            
                            # Save checkpoint
                            with open(checkpoint_path, 'w') as cf:
                                json.dump({
                                    'count': count,
                                    'processed_ids': list(processed_ids),
                                    'timestamp': datetime.now().isoformat()
                                }, cf)
                        
                        # Check if we've reached the target
                        if count >= max_releases:
                            print(f"\n✓ Reached target of {max_releases:,} releases")
                            break
                    else:
                        skipped_no_images += 1
                    
                    # Clear element to free memory
                    elem.clear()
                    root.clear()
                    
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving checkpoint...")
        with open(checkpoint_path, 'w') as cf:
            json.dump({
                'count': count,
                'processed_ids': list(processed_ids),
                'timestamp': datetime.now().isoformat()
            }, cf)
        print(f"Checkpoint saved with {count} releases")
        print("Run again to resume")
        sys.exit(0)
    
    # Write JSONL output
    print(f"\n{'='*60}")
    print("Writing JSONL Manifest")
    print(f"{'='*60}\n")
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for release in releases:
            f.write(json.dumps(release) + '\n')
    
    # Clean up checkpoint
    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)
    
    print(f"✓ Wrote {len(releases):,} releases to {output_path}")
    print(f"✓ Processed {processed:,} total releases")
    print(f"✓ Skipped {skipped_no_images:,} releases without images")
    print(f"\nNext step: Download images")
    print(f"  python backend/batch_download_images.py")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Process Discogs data dump to JSONL manifest'
    )
    parser.add_argument(
        '--count', type=int, default=100000,
        help='Number of releases to extract (default: 100000)'
    )
    parser.add_argument(
        '--output', type=str, default='../data/releases_manifest.jsonl',
        help='Output JSONL file path'
    )
    parser.add_argument(
        '--dump-file', type=str, default='../data/discogs_releases.xml.gz',
        help='Path to save/use dump file'
    )
    parser.add_argument(
        '--skip-download', action='store_true',
        help='Skip download if dump file exists'
    )
    parser.add_argument(
        '--dump-url', type=str, default=None,
        help='Direct URL to Discogs dump file'
    )
    
    args = parser.parse_args()
    
    # Get dump URL
    if args.dump_url:
        dump_url = args.dump_url
    else:
        dump_url = get_latest_dump_url()
    
    # Download dump if needed
    if not args.skip_download or not os.path.exists(args.dump_file):
        dump_path = download_dump(dump_url, args.dump_file)
    else:
        dump_path = args.dump_file
        print(f"\nUsing existing dump file: {dump_path}")
    
    # Process dump
    process_dump_to_jsonl(
        dump_path=dump_path,
        output_path=args.output,
        max_releases=args.count
    )
    
    print(f"\n{'='*60}")
    print("✓ Complete!")
    print(f"{'='*60}\n")
    print(f"Manifest created: {args.output}")
    print(f"Ready to download images!")


if __name__ == "__main__":
    main()

