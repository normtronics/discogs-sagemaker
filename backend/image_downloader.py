import os
import requests
import time
from pathlib import Path
from typing import List, Dict
import asyncio
import aiofiles
from PIL import Image
from io import BytesIO


async def download_image(url: str, save_path: str) -> bool:
    """Download a single image from URL"""
    try:
        # Increased rate limiting - be more respectful to avoid blocks
        await asyncio.sleep(2)
        
        # More realistic browser headers to avoid CDN blocks
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.discogs.com/",
            "Sec-Fetch-Dest": "image",
            "Sec-Fetch-Mode": "no-cors",
            "Sec-Fetch-Site": "same-site"
        }
        
        response = requests.get(url, headers=headers, stream=True, timeout=15)
        response.raise_for_status()
        
        # Download and save image in chunks
        with open(save_path, "wb") as file:
            for chunk in response.iter_content(1024):
                file.write(chunk)
        
        # Verify it's a valid image
        img = Image.open(save_path)
        img.verify()
        
        # Re-open and ensure RGB format
        img = Image.open(save_path).convert("RGB")
        img.save(save_path, "JPEG")
        
        return True
    except Exception as e:
        print(f"Failed to download {url}: {str(e)}")
        # Clean up failed download
        if os.path.exists(save_path):
            os.remove(save_path)
        return False


async def get_release_images(release_id: int, consumer_key: str, consumer_secret: str) -> List[str]:
    """Fetch image URLs for a release from Discogs API"""
    headers = {
        "User-Agent": "AlbumRecognitionApp/1.0",
        "Authorization": f"Discogs key={consumer_key}, secret={consumer_secret}"
    }
    
    try:
        # Add rate limiting for API calls (Discogs requires 1 req/sec)
        await asyncio.sleep(1.5)
        
        url = f"https://api.discogs.com/releases/{release_id}"
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        images = data.get("images", [])
        
        # Return primary image URLs
        image_urls = [img["uri"] for img in images if img.get("type") == "primary"]
        if not image_urls and images:
            # If no primary, use the first image
            image_urls = [images[0]["uri"]]
        
        return image_urls
    except Exception as e:
        print(f"Failed to fetch images for release {release_id}: {str(e)}")
        return []


async def download_all_images(releases: List[Dict], images_dir: str, consumer_key: str, consumer_secret: str) -> Dict:
    """Download images for all releases"""
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    
    results = {
        "downloaded": 0,
        "failed": 0,
        "skipped": 0
    }
    
    for idx, release in enumerate(releases):
        release_id = release["release_id"]
        save_path = os.path.join(images_dir, f"{idx}.jpg")
        
        # Skip if already downloaded
        if os.path.exists(save_path):
            print(f"Skipping {release_id} - already exists")
            results["skipped"] += 1
            continue
        
        print(f"Processing {idx + 1}/{len(releases)}: Release {release_id} - {release['title']}")
        
        # Get image URLs from Discogs API
        image_urls = await get_release_images(release_id, consumer_key, consumer_secret)
        
        if not image_urls:
            print(f"No images found for release {release_id}")
            results["failed"] += 1
            continue
        
        # Download the first available image
        success = await download_image(image_urls[0], save_path)
        
        if success:
            results["downloaded"] += 1
            print(f"Downloaded image for {release['title']}")
        else:
            results["failed"] += 1
    
    return results


if __name__ == "__main__":
    # For standalone testing
    import sys
    from dotenv import load_dotenv
    from data_loader import load_releases_data
    
    load_dotenv()
    
    consumer_key = os.getenv("DISCOGS_CONSUMER_KEY")
    consumer_secret = os.getenv("DISCOGS_CONSUMER_SECRET")
    
    if not consumer_key or not consumer_secret:
        print("Error: DISCOGS_CONSUMER_KEY and DISCOGS_CONSUMER_SECRET not set")
        sys.exit(1)
    
    releases = load_releases_data("../data/releases_manifest_50.jsonl")
    results = asyncio.run(download_all_images(releases, "./data/images", consumer_key, consumer_secret))
    
    print(f"\nResults: {results}")

