#!/usr/bin/env python3
"""
Extract release metadata from Discogs dump (without requiring images)
Images will be fetched later via API
"""
import os
import json
import gzip
import xml.etree.ElementTree as ET
from pathlib import Path
import sys


def extract_releases(dump_path, output_path, max_releases=100000):
    """Extract release metadata from dump"""
    print(f"\n{'='*60}")
    print("Extracting Releases from Discogs Dump")
    print(f"{'='*60}\n")
    print(f"Input: {dump_path}")
    print(f"Output: {output_path}")
    print(f"Max releases: {max_releases:,}\n")
    
    if not os.path.exists(dump_path):
        print(f"✗ Dump file not found: {dump_path}")
        sys.exit(1)
    
    releases = []
    count = 0
    
    print("Parsing XML dump...\n")
    
    try:
        with gzip.open(dump_path, 'rb') as f:
            for event, elem in ET.iterparse(f, events=('end',)):
                if elem.tag == 'release':
                    try:
                        release_id = elem.get('id')
                        if not release_id:
                            continue
                        
                        # Extract title
                        title_elem = elem.find('title')
                        title = title_elem.text if title_elem is not None else "Unknown"
                        
                        # Extract artists
                        artists = []
                        artists_elem = elem.find('artists')
                        if artists_elem is not None:
                            for artist in artists_elem.findall('artist'):
                                name_elem = artist.find('name')
                                if name_elem is not None and name_elem.text:
                                    artists.append(name_elem.text)
                        
                        if not artists:
                            artists = ["Unknown Artist"]
                        
                        # Extract labels
                        labels = []
                        labels_elem = elem.find('labels')
                        if labels_elem is not None:
                            for label in labels_elem.findall('label'):
                                name = label.get('name')
                                if name:
                                    labels.append(name)
                        
                        # Extract release date
                        released = "Unknown"
                        released_elem = elem.find('released')
                        if released_elem is not None and released_elem.text:
                            released = released_elem.text
                        
                        # Extract country
                        country = "Unknown"
                        country_elem = elem.find('country')
                        if country_elem is not None and country_elem.text:
                            country = country_elem.text
                        
                        # Extract master_id
                        master_id = 0
                        master_id_elem = elem.find('master_id')
                        if master_id_elem is not None and master_id_elem.text:
                            try:
                                master_id = int(master_id_elem.text)
                            except:
                                pass
                        
                        # Create release dict (no images yet)
                        release = {
                            'release_id': int(release_id),
                            'master_id': master_id,
                            'title': title,
                            'artists': artists,
                            'labels': labels,
                            'released': released,
                            'country': country,
                            'has_images': False,  # Will be updated via API
                            'image_count': 0
                        }
                        
                        releases.append(release)
                        count += 1
                        
                        # Progress
                        if count % 10000 == 0:
                            print(f"Extracted: {count:,} releases")
                        
                        # Check target
                        if count >= max_releases:
                            print(f"\n✓ Reached target of {max_releases:,} releases")
                            break
                        
                    except Exception as e:
                        # Skip problematic releases
                        pass
                    
                    elem.clear()
                    
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # Write output
    print(f"\nWriting to {output_path}...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        for release in releases:
            f.write(json.dumps(release) + '\n')
    
    print(f"\n{'='*60}")
    print("Extraction Complete!")
    print(f"{'='*60}\n")
    print(f"✓ Extracted {len(releases):,} releases")
    print(f"✓ Saved to: {output_path}")
    
    # Show sample
    if releases:
        print(f"\nSample release:")
        sample = releases[0]
        print(f"  ID: {sample['release_id']}")
        print(f"  Title: {sample['title']}")
        print(f"  Artists: {', '.join(sample['artists'][:2])}")
        print(f"  Released: {sample['released']}")
    
    print(f"\nNext step: Add image URLs via API")
    print(f"  python3 enrich_manifest_with_images.py \\")
    print(f"    --input {output_path} \\")
    print(f"    --output ../data/releases_manifest_enriched.jsonl")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Extract release metadata from Discogs dump')
    parser.add_argument('--dump-file', type=str, default='../data/discogs_releases.xml.gz',
                        help='Path to dump file')
    parser.add_argument('--output', type=str, default='../data/releases_metadata.jsonl',
                        help='Output JSONL file')
    parser.add_argument('--count', type=int, default=100000,
                        help='Max releases to extract')
    
    args = parser.parse_args()
    
    extract_releases(args.dump_file, args.output, args.count)


if __name__ == "__main__":
    main()

