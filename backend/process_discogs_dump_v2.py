#!/usr/bin/env python3
"""
Process Discogs Data Dump to JSONL - Version 2
Improved with better debugging and error handling
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
        return output_path
    
    print("\nStarting download...")
    print("Note: This file is ~3-5 GB, may take 10-30 minutes\n")
    
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get('content-length', 0))
        total_mb = total_size / (1024 * 1024)
        
        downloaded = 0
        chunk_size = 8192
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        
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
    except Exception as e:
        print(f"✗ Download failed: {e}")
        if os.path.exists(output_path):
            os.remove(output_path)
        raise


def parse_release(release_elem, debug=False) -> Optional[Dict]:
    """Parse a release XML element into a dictionary"""
    try:
        release_id = release_elem.get('id')
        if not release_id:
            return None
        
        # Extract title
        title_elem = release_elem.find('title')
        title = title_elem.text if title_elem is not None and title_elem.text else "Unknown"
        
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
        
        # Extract images - CRITICAL!
        images = []
        images_elem = release_elem.find('images')
        
        if debug:
            print(f"\nDEBUG - First release:")
            print(f"  ID: {release_id}")
            print(f"  Title: {title}")
            print(f"  Artists: {artists}")
            print(f"  Has images element: {images_elem is not None}")
            if images_elem is not None:
                print(f"  Images found: {len(list(images_elem.findall('image')))}")
        
        if images_elem is not None:
            for image in images_elem.findall('image'):
                image_type = image.get('type', 'primary')
                uri = image.get('uri')
                uri150 = image.get('uri150')
                
                if uri:
                    images.append({
                        'type': image_type,
                        'uri': uri,
                        'uri150': uri150 or uri
                    })
        
        # Only include releases with images
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
        if debug:
            print(f"Error parsing release {release_id}: {e}")
        return None


def process_dump_to_jsonl(
    dump_path: str,
    output_path: str,
    max_releases: int = 100000,
    debug: bool = False
):
    """Process Discogs XML dump and create JSONL manifest"""
    print(f"\n{'='*60}")
    print("Processing Discogs Dump to JSONL")
    print(f"{'='*60}\n")
    print(f"Input: {dump_path}")
    print(f"Output: {output_path}")
    print(f"Max releases: {max_releases:,}")
    
    if not os.path.exists(dump_path):
        print(f"✗ Error: Dump file not found: {dump_path}")
        sys.exit(1)
    
    file_size = os.path.getsize(dump_path) / (1024 * 1024)
    print(f"File size: {file_size:.1f} MB")
    
    releases = []
    count = 0
    processed = 0
    skipped_no_images = 0
    parse_errors = 0
    
    print(f"\nParsing XML dump...")
    print("This may take 10-30 minutes for large dumps\n")
    
    try:
        # Open gzipped XML file
        print("Opening compressed file...")
        with gzip.open(dump_path, 'rb') as f:
            print("Starting XML parse...")
            
            # Use iterparse for memory efficiency
            for event, elem in ET.iterparse(f, events=('end',)):
                if elem.tag == 'release':
                    processed += 1
                    
                    # Debug first few releases
                    if debug and processed <= 3:
                        print(f"\nProcessing release #{processed}")
                    
                    # Parse release
                    release_data = parse_release(elem, debug=(debug and processed <= 3))
                    
                    if release_data:
                        releases.append(release_data)
                        count += 1
                        
                        # Progress update
                        if count % 1000 == 0:
                            print(f"Found: {count:,} releases with images "
                                  f"(scanned {processed:,} total)")
                        
                        # Check if we've reached the target
                        if count >= max_releases:
                            print(f"\n✓ Reached target of {max_releases:,} releases")
                            break
                    else:
                        skipped_no_images += 1
                    
                    # Clear element to free memory
                    elem.clear()
                    
                    # Early debug exit
                    if debug and processed >= 100:
                        print(f"\nDebug mode: stopping after 100 releases")
                        break
                
    except Exception as e:
        print(f"\n✗ Error processing dump: {e}")
        import traceback
        traceback.print_exc()
        
        if count > 0:
            print(f"\nPartial results: {count} releases collected before error")
        else:
            print("\nNo releases collected. Possible issues:")
            print("  1. XML file might be corrupted")
            print("  2. XML structure might have changed")
            print("  3. File might not be a valid Discogs dump")
            sys.exit(1)
    
    # Write JSONL output
    print(f"\n{'='*60}")
    print("Writing JSONL Manifest")
    print(f"{'='*60}\n")
    
    if count == 0:
        print("✗ Warning: No releases with images found!")
        print("\nPossible reasons:")
        print("  1. Dump file might be corrupted")
        print("  2. All releases in the sample lacked images")
        print("  3. XML structure might have changed")
        print("\nTry running with --debug flag for more information")
        return
    
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for release in releases:
            f.write(json.dumps(release) + '\n')
    
    print(f"✓ Wrote {len(releases):,} releases to {output_path}")
    print(f"✓ Scanned {processed:,} total releases")
    print(f"✓ Skipped {skipped_no_images:,} releases without images")
    print(f"✓ Parse errors: {parse_errors}")
    
    # Show sample
    if releases:
        print(f"\nSample release:")
        sample = releases[0]
        print(f"  ID: {sample['release_id']}")
        print(f"  Title: {sample['title']}")
        print(f"  Artists: {', '.join(sample['artists'])}")
        print(f"  Cover: {sample['cover_image'][:60]}...")
    
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
        help='Path to dump file'
    )
    parser.add_argument(
        '--download', action='store_true',
        help='Download the dump file first'
    )
    parser.add_argument(
        '--dump-url', type=str,
        default='https://discogs-data-dumps.s3.us-west-2.amazonaws.com/data/2025/discogs_20250101_releases.xml.gz',
        help='URL to Discogs dump file'
    )
    parser.add_argument(
        '--debug', action='store_true',
        help='Enable debug mode (verbose output)'
    )
    
    args = parser.parse_args()
    
    # Download dump if requested
    if args.download:
        dump_path = download_dump(args.dump_url, args.dump_file)
    else:
        dump_path = args.dump_file
        if not os.path.exists(dump_path):
            print(f"✗ Dump file not found: {dump_path}")
            print(f"\nDownload it first:")
            print(f"  python {sys.argv[0]} --download")
            print(f"\nOr download manually from:")
            print(f"  {args.dump_url}")
            sys.exit(1)
        print(f"\nUsing existing dump file: {dump_path}")
    
    # Process dump
    process_dump_to_jsonl(
        dump_path=dump_path,
        output_path=args.output,
        max_releases=args.count,
        debug=args.debug
    )


if __name__ == "__main__":
    main()

