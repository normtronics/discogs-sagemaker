#!/usr/bin/env python3
"""
Parse Discogs XML dump to JSONL manifest with album info and image URLs.
Images are extracted directly from the XML - no API calls needed.
"""
import os
import json
import gzip
import requests
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime


def get_latest_dump_url() -> str:
    """Get Discogs releases dump URL from data.discogs.com."""
    return "https://data.discogs.com/?download=data%2F2026%2Fdiscogs_20260101_releases.xml.gz"


def download_dump(url: str, output_path: str) -> str:
    """Download Discogs dump with progress."""
    if os.path.exists(output_path):
        print(f"✓ Using existing dump: {output_path}")
        return output_path

    print(f"Downloading {url}...")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    response = requests.get(url, stream=True, timeout=60)
    response.raise_for_status()
    total = int(response.headers.get("content-length", 0))

    with open(output_path, "wb") as f:
        downloaded = 0
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total and downloaded % (50 * 1024 * 1024) < 8192:
                    print(f"  {downloaded / (1024**2):.1f} / {total / (1024**2):.1f} MB")

    print(f"✓ Downloaded: {output_path}")
    return output_path


def parse_release(elem) -> Optional[Dict]:
    """Parse a release XML element into a dict with album info and image URLs."""
    try:
        release_id = elem.get("id")
        if not release_id:
            return None

        title_elem = elem.find("title")
        title = title_elem.text if title_elem is not None else "Unknown"

        artists = []
        artists_elem = elem.find("artists")
        if artists_elem is not None:
            for artist in artists_elem.findall("artist"):
                name_elem = artist.find("name")
                if name_elem is not None and name_elem.text:
                    artists.append(name_elem.text)
        if not artists:
            artists = ["Unknown Artist"]

        labels = []
        labels_elem = elem.find("labels")
        if labels_elem is not None:
            for label in labels_elem.findall("label"):
                name = label.get("name")
                if name:
                    labels.append(name)

        released_elem = elem.find("released")
        released = released_elem.text if released_elem is not None and released_elem.text else "Unknown"

        # Discogs XML dump does NOT include images - they must be fetched via API
        # Include all releases; enrich step adds cover_image/thumb via Discogs API
        return {
            "release_id": int(release_id),
            "title": title,
            "artists": artists,
            "labels": labels,
            "released": released,
            "cover_image": None,
            "thumb": None,
            "image_count": 0,
        }
    except Exception:
        return None


def process_dump_to_jsonl(
    dump_path: str,
    output_path: str,
    max_releases: int = 100000,
) -> int:
    """
    Process Discogs XML dump to JSONL manifest.
    Returns number of releases written.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    releases = []
    count = 0

    print(f"Parsing {dump_path}...")

    with gzip.open(dump_path, "rb") as f:
        context = iter(ET.iterparse(f, events=("start", "end")))
        event, root = next(context)

        for event, elem in context:
            if event == "end" and elem.tag == "release":
                data = parse_release(elem)
                if data:
                    releases.append(data)
                    count += 1
                    if count % 10000 == 0:
                        print(f"  {count:,} releases")
                    if count >= max_releases:
                        break
                elem.clear()
                root.clear()

    with open(output_path, "w") as f:
        for r in releases:
            f.write(json.dumps(r) + "\n")

    print(f"✓ Wrote {len(releases)} releases to {output_path}")
    return len(releases)
