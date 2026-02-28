#!/usr/bin/env python3
"""
Enrich manifest with image URLs from Discogs API.
Uses python3-discogs-client (https://github.com/joalla/discogs_client).
Supports checkpoint/resume for long runs.
"""
import os
import json
import asyncio
import time
from typing import Dict, Optional


def _fetch_release_images_discogs_client(
    release_id: int,
    user_token: str,
) -> Optional[Dict]:
    """Fetch image URLs using python3-discogs-client."""
    import discogs_client

    d = discogs_client.Client(
        "AlbumRecognitionApp/1.0",
        user_token=user_token,
    )
    d.set_timeout(connect=10, read=30)

    try:
        release = d.release(release_id)
        images = list(release.images) if release.images else []

        cover_image = thumb = None
        for img in images:
            if img.get("type") == "primary":
                cover_image = img.get("uri")
                thumb = img.get("uri150", img.get("uri"))
                break
        if not cover_image and images:
            cover_image = images[0].get("uri")
            thumb = images[0].get("uri150", images[0].get("uri"))

        image_urls = []
        seen = set()
        for img in images:
            uri = img.get("uri")
            if uri and uri not in seen:
                seen.add(uri)
                image_urls.append(uri)

        return {
            "cover_image": cover_image,
            "thumb": thumb,
            "images": image_urls,
            "image_count": len(image_urls),
        }
    except Exception as e:
        print(f"  Error fetching {release_id}: {str(e)[:80]}")
        return None


async def _fetch_release_images_aiohttp(
    session,
    release_id: int,
    consumer_key: str,
    consumer_secret: str,
) -> Optional[Dict]:
    """Fallback: fetch via aiohttp (consumer key/secret)."""
    import aiohttp

    headers = {
        "User-Agent": "AlbumRecognitionApp/1.0",
        "Authorization": f"Discogs key={consumer_key}, secret={consumer_secret}",
    }
    try:
        await asyncio.sleep(1.1)
        url = f"https://api.discogs.com/releases/{release_id}"
        async with session.get(url, headers=headers, timeout=15) as resp:
            if resp.status != 200:
                print(f"  Failed to fetch {release_id}: HTTP {resp.status}")
                return None
            data = await resp.json()
    except Exception as e:
        print(f"  Error fetching {release_id}: {str(e)[:80]}")
        return None

    images = data.get("images", [])
    cover_image = thumb = None
    for img in images:
        if img.get("type") == "primary":
            cover_image = img.get("uri")
            thumb = img.get("uri150", img.get("uri"))
            break
    if not cover_image and images:
        cover_image = images[0].get("uri")
        thumb = images[0].get("uri150", images[0].get("uri"))

    image_urls = []
    seen = set()
    for img in images:
        uri = img.get("uri")
        if uri and uri not in seen:
            seen.add(uri)
            image_urls.append(uri)

    return {
        "cover_image": cover_image,
        "thumb": thumb,
        "images": image_urls,
        "image_count": len(image_urls),
    }


async def enrich_manifest(
    input_path: str,
    output_path: str,
    consumer_key: str,
    consumer_secret: str,
    checkpoint_path: Optional[str] = None,
    user_token: Optional[str] = None,
) -> int:
    """
    Add image URLs to manifest via Discogs API.
    Prefers python3-discogs-client (user_token). Falls back to aiohttp (consumer_key/secret).
    Supports checkpoint/resume. Returns number of releases with images.
    """
    if checkpoint_path is None:
        checkpoint_path = f"{output_path}.checkpoint"

    releases = []
    with open(input_path) as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))

    start_idx = 0
    if os.path.exists(checkpoint_path):
        with open(checkpoint_path) as f:
            checkpoint = json.load(f)
            start_idx = checkpoint.get("last_index", 0) + 1
        print(f"Resuming from index {start_idx}")

    remaining = len(releases) - start_idx
    rate_per_min = 60 if user_token else 55
    minutes = remaining / rate_per_min
    print(f"Estimated time: {minutes:.1f} minutes ({minutes/60:.1f} hours)\n")

    enriched = []
    idx = 0

    use_discogs_client = bool(user_token)
    if use_discogs_client:
        print("Using python3-discogs-client (user_token)")
    else:
        print("Using aiohttp (consumer_key/consumer_secret)")

    try:
        if use_discogs_client:
            loop = asyncio.get_event_loop()
            for idx, release in enumerate(releases):
                if idx < start_idx:
                    enriched.append(release)
                    continue

                release_id = release["release_id"]
                print(f"[{idx+1}/{len(releases)}] Fetching images for release {release_id}...")

                image_data = await loop.run_in_executor(
                    None,
                    lambda rid=release_id: _fetch_release_images_discogs_client(rid, user_token),
                )
                time.sleep(1.1)

                if image_data and image_data.get("cover_image"):
                    release["cover_image"] = image_data["cover_image"]
                    release["thumb"] = image_data["thumb"]
                    release["images"] = image_data.get("images", [image_data["cover_image"]])
                    release["image_count"] = image_data["image_count"]
                    release["has_images"] = True
                    print(f"  ✓ Found {image_data['image_count']} images")
                else:
                    release["cover_image"] = None
                    release["thumb"] = None
                    release["images"] = []
                    release["image_count"] = 0
                    release["has_images"] = False
                    print(f"  ✗ No images found")

                enriched.append(release)

                if (idx + 1) % 10 == 0:
                    with open(checkpoint_path, "w") as f:
                        json.dump({"last_index": idx}, f)
                    print(f"  Checkpoint saved at {idx + 1}")

        else:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                for idx, release in enumerate(releases):
                    if idx < start_idx:
                        enriched.append(release)
                        continue

                    release_id = release["release_id"]
                    print(f"[{idx+1}/{len(releases)}] Fetching images for release {release_id}...")

                    image_data = await _fetch_release_images_aiohttp(
                        session, release_id, consumer_key, consumer_secret
                    )

                    if image_data and image_data.get("cover_image"):
                        release["cover_image"] = image_data["cover_image"]
                        release["thumb"] = image_data["thumb"]
                        release["images"] = image_data.get("images", [image_data["cover_image"]])
                        release["image_count"] = image_data["image_count"]
                        release["has_images"] = True
                        print(f"  ✓ Found {image_data['image_count']} images")
                    else:
                        release["cover_image"] = None
                        release["thumb"] = None
                        release["images"] = []
                        release["image_count"] = 0
                        release["has_images"] = False
                        print(f"  ✗ No images found")

                    enriched.append(release)

                    if (idx + 1) % 10 == 0:
                        with open(checkpoint_path, "w") as f:
                            json.dump({"last_index": idx}, f)
                        print(f"  Checkpoint saved at {idx + 1}")

    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving progress...")
        with open(checkpoint_path, "w") as f:
            json.dump({"last_index": idx}, f)
        print(f"Checkpoint saved. Run again to resume from {idx + 1}")
        raise SystemExit(0)

    with open(output_path, "w") as f:
        for r in enriched:
            f.write(json.dumps(r) + "\n")

    if os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    with_images = sum(1 for r in enriched if r.get("has_images"))
    print(f"\nTotal: {len(enriched)}, With images: {with_images}, Without: {len(enriched) - with_images}")
    return with_images
