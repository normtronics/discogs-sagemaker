#!/usr/bin/env python3
"""
Download album cover images from manifest URLs.
Works locally and in SageMaker Processing.
"""
import os
import json
import asyncio
import logging
import aiohttp
from pathlib import Path
from typing import List, Dict
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)


def load_manifest(path: str) -> List[Dict]:
    """Load releases from JSONL manifest."""
    releases = []
    with open(path) as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))
    return releases


async def download_image(
    session: aiohttp.ClientSession,
    url: str,
    save_path: str,
    semaphore: asyncio.Semaphore,
    request_delay: float = 0.2,
    max_retries: int = 3,
) -> bool:
    """Download a single image with retries and delay."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "image/*",
        "Referer": "https://www.discogs.com/",
    }
    if os.path.exists(save_path):
        return True

    last_error = None
    for attempt in range(max_retries):
        try:
            async with semaphore:
                await asyncio.sleep(request_delay)
                async with session.get(url, headers=headers, timeout=30) as resp:
                    if resp.status == 429:
                        wait = 2 ** attempt
                        logger.warning(f"Rate limited (429), retry {attempt + 1}/{max_retries} after {wait}s: {save_path}")
                        await asyncio.sleep(wait)
                        continue
                    if resp.status != 200:
                        last_error = f"HTTP {resp.status}"
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        logger.debug(f"Failed {save_path}: {last_error}")
                        return False
                    content = await resp.read()
            img = Image.open(BytesIO(content))
            img.verify()
            img = Image.open(BytesIO(content)).convert("RGB")
            img.save(save_path, "JPEG", quality=90)
            return True
        except asyncio.TimeoutError:
            last_error = "timeout"
            logger.debug(f"Timeout {save_path} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.warning(f"Failed {save_path}: {last_error}")
        except Exception as e:
            last_error = str(e)[:80]
            logger.debug(f"Error {save_path}: {last_error}")
            if attempt < max_retries - 1:
                await asyncio.sleep(2 ** attempt)
            else:
                logger.warning(f"Failed {save_path}: {last_error}")

    if os.path.exists(save_path):
        os.remove(save_path)
    return False


async def download_all(
    manifest_path: str,
    images_dir: str,
    max_concurrent: int = 10,
    batch_size: int = 100,
    request_delay: float = 0.2,
    max_retries: int = 3,
) -> Dict[str, int]:
    """
    Download all images from manifest.
    Returns stats: downloaded, failed, skipped.
    """
    Path(images_dir).mkdir(parents=True, exist_ok=True)
    releases = load_manifest(manifest_path)
    semaphore = asyncio.Semaphore(max_concurrent)
    stats = {"downloaded": 0, "failed": 0, "skipped": 0}

    async with aiohttp.ClientSession() as session:
        for start in range(0, len(releases), batch_size):
            end = min(start + batch_size, len(releases))
            batch = releases[start:end]

            tasks = []
            for idx, release in enumerate(batch):
                i = start + idx
                urls = release.get("images")
                if not urls:
                    url = release.get("cover_image") or release.get("thumb")
                    urls = [url] if url else []
                if not urls:
                    stats["failed"] += 1
                    continue
                for img_idx, url in enumerate(urls):
                    # Single image: {i}.jpg; multi: {i}_0.jpg, {i}_1.jpg, ...
                    suffix = f"_{img_idx}.jpg" if len(urls) > 1 else ".jpg"
                    save_path = os.path.join(images_dir, f"{i}{suffix}")
                    if os.path.exists(save_path):
                        stats["skipped"] += 1
                        continue
                    tasks.append((
                        i,
                        download_image(
                            session, url, save_path, semaphore,
                            request_delay=request_delay,
                            max_retries=max_retries,
                        ),
                    ))

            results = await asyncio.gather(*[t[1] for t in tasks])
            for i, ok in zip([t[0] for t in tasks], results):
                if ok:
                    stats["downloaded"] += 1
                else:
                    stats["failed"] += 1

            if (start + batch_size) % 500 == 0 or end == len(releases):
                print(f"  {end}/{len(releases)} - downloaded: {stats['downloaded']}, "
                      f"failed: {stats['failed']}, skipped: {stats['skipped']}")

    return stats
