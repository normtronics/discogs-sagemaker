#!/usr/bin/env python3
"""
Download album cover images from manifest URLs.
Works locally and in SageMaker Processing.
Use --use-requests if aiohttp fails to connect (e.g. SSL/proxy issues where curl works).
"""
import os
import json
import asyncio
import logging
import ssl
from pathlib import Path
from typing import List, Dict
from PIL import Image
from io import BytesIO

logger = logging.getLogger(__name__)

# Try certifi for SSL certs (helps when Python can't find system certs)
try:
    import certifi
    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    SSL_CONTEXT = None


def load_manifest(path: str) -> List[Dict]:
    """Load releases from JSONL manifest."""
    releases = []
    with open(path) as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))
    return releases


def _download_image_requests(
    url: str,
    save_path: str,
    verify_ssl: bool = True,
    request_delay: float = 0.2,
    max_retries: int = 3,
) -> bool:
    """Download using requests (works when aiohttp fails, e.g. SSL/proxy)."""
    import requests
    import time

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "image/*",
        "Referer": "https://www.discogs.com/",
    }
    if os.path.exists(save_path):
        return True

    for attempt in range(max_retries):
        try:
            time.sleep(request_delay)
            resp = requests.get(url, headers=headers, timeout=30, verify=verify_ssl)
            if resp.status_code == 429:
                wait = 2 ** attempt
                logger.warning(f"Rate limited (429), retry {attempt + 1}/{max_retries} after {wait}s")
                time.sleep(wait)
                continue
            if resp.status_code != 200:
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False
            content = resp.content
            img = Image.open(BytesIO(content))
            img.verify()
            img = Image.open(BytesIO(content)).convert("RGB")
            img.save(save_path, "JPEG", quality=90)
            return True
        except Exception as e:
            logger.debug(f"Error {save_path}: {str(e)[:80]}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                logger.warning(f"Failed {save_path}: {str(e)[:80]}")
    if os.path.exists(save_path):
        os.remove(save_path)
    return False


async def download_image(
    session,
    url: str,
    save_path: str,
    semaphore: asyncio.Semaphore,
    request_delay: float = 0.2,
    max_retries: int = 3,
    use_requests: bool = False,
    verify_ssl: bool = True,
) -> bool:
    """Download a single image with retries and delay."""
    import aiohttp

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Accept": "image/*",
        "Referer": "https://www.discogs.com/",
    }
    if os.path.exists(save_path):
        return True

    if use_requests:
        async with semaphore:
            await asyncio.sleep(request_delay)
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                lambda: _download_image_requests(url, save_path, verify_ssl, 0, max_retries),
            )

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
    use_requests: bool = False,
    verify_ssl: bool = True,
) -> Dict[str, int]:
    """
    Download all images from manifest.
    Returns stats: downloaded, failed, skipped.
    use_requests: Use requests lib instead of aiohttp (fixes SSL/proxy when curl works but Python fails).
    """
    import aiohttp

    Path(images_dir).mkdir(parents=True, exist_ok=True)
    releases = load_manifest(manifest_path)
    semaphore = asyncio.Semaphore(max_concurrent)
    stats = {"downloaded": 0, "failed": 0, "skipped": 0}

    async def _run_batches(session):
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
                            use_requests=use_requests,
                            verify_ssl=verify_ssl,
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

    if use_requests:
        await _run_batches(None)
    else:
        connector = aiohttp.TCPConnector(ssl=SSL_CONTEXT) if SSL_CONTEXT else None
        async with aiohttp.ClientSession(connector=connector) as session:
            await _run_batches(session)

    return stats
