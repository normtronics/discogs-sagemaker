#!/usr/bin/env python3
"""
Batch download images for large manifests (100k+ releases)
Optimized for resumable, parallel downloads with progress tracking
"""
import os
import json
import time
import asyncio
import aiohttp
import aiofiles
from pathlib import Path
from typing import List, Dict
from PIL import Image
from io import BytesIO
import sys
from dotenv import load_dotenv

load_dotenv('.env.local')
load_dotenv()


class BatchImageDownloader:
    def __init__(
        self,
        manifest_path: str,
        images_dir: str,
        batch_size: int = 100,
        max_concurrent: int = 10,
        checkpoint_interval: int = 100
    ):
        self.manifest_path = manifest_path
        self.images_dir = images_dir
        self.batch_size = batch_size
        self.max_concurrent = max_concurrent
        self.checkpoint_interval = checkpoint_interval
        self.checkpoint_path = f"{images_dir}/download_checkpoint.json"
        
        self.stats = {
            'downloaded': 0,
            'failed': 0,
            'skipped': 0,
            'total': 0
        }
    
    def load_releases(self) -> List[Dict]:
        """Load releases from manifest"""
        releases = []
        with open(self.manifest_path, 'r') as f:
            for line in f:
                if line.strip():
                    releases.append(json.loads(line))
        return releases
    
    def load_checkpoint(self) -> int:
        """Load checkpoint to resume from"""
        if os.path.exists(self.checkpoint_path):
            with open(self.checkpoint_path, 'r') as f:
                checkpoint = json.load(f)
                print(f"Found checkpoint: {checkpoint['downloaded']} images already downloaded")
                return checkpoint.get('last_index', 0) + 1
        return 0
    
    def save_checkpoint(self, last_index: int):
        """Save progress checkpoint"""
        with open(self.checkpoint_path, 'w') as f:
            json.dump({
                'last_index': last_index,
                'downloaded': self.stats['downloaded'],
                'failed': self.stats['failed'],
                'skipped': self.stats['skipped'],
                'timestamp': time.time()
            }, f)
    
    async def download_single_image(
        self,
        session: aiohttp.ClientSession,
        idx: int,
        image_url: str,
        save_path: str
    ) -> bool:
        """Download a single image"""
        try:
            # Skip if already exists
            if os.path.exists(save_path):
                return True
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "image/*",
                "Referer": "https://www.discogs.com/"
            }
            
            async with session.get(image_url, headers=headers, timeout=30) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    # Verify it's a valid image
                    img = Image.open(BytesIO(content))
                    img.verify()
                    
                    # Convert to RGB and save
                    img = Image.open(BytesIO(content)).convert("RGB")
                    img.save(save_path, "JPEG", quality=90)
                    
                    return True
                else:
                    print(f"Failed {idx}: HTTP {response.status}")
                    return False
                    
        except Exception as e:
            print(f"Error {idx}: {str(e)[:50]}")
            if os.path.exists(save_path):
                os.remove(save_path)
            return False
    
    async def download_batch(
        self,
        session: aiohttp.ClientSession,
        releases: List[Dict],
        start_idx: int,
        end_idx: int
    ):
        """Download a batch of images concurrently"""
        tasks = []
        
        for idx in range(start_idx, end_idx):
            if idx >= len(releases):
                break
            
            release = releases[idx]
            save_path = os.path.join(self.images_dir, f"{idx}.jpg")
            
            # Use cover_image or thumb
            image_url = release.get('cover_image') or release.get('thumb')
            
            if not image_url or image_url == '':
                self.stats['failed'] += 1
                continue
            
            # Skip if already exists
            if os.path.exists(save_path):
                self.stats['skipped'] += 1
                continue
            
            task = self.download_single_image(session, idx, image_url, save_path)
            tasks.append((idx, task))
        
        # Download with concurrency limit
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def bounded_download(idx, task):
            async with semaphore:
                success = await task
                if success:
                    self.stats['downloaded'] += 1
                else:
                    self.stats['failed'] += 1
                return success
        
        results = await asyncio.gather(
            *[bounded_download(idx, task) for idx, task in tasks],
            return_exceptions=True
        )
        
        return results
    
    async def download_all(self):
        """Download all images with progress tracking"""
        print(f"\n{'='*60}")
        print("Batch Image Downloader")
        print(f"{'='*60}\n")
        
        # Setup
        Path(self.images_dir).mkdir(parents=True, exist_ok=True)
        releases = self.load_releases()
        start_idx = self.load_checkpoint()
        
        self.stats['total'] = len(releases)
        
        print(f"Total releases: {len(releases)}")
        print(f"Starting from index: {start_idx}")
        print(f"Batch size: {self.batch_size}")
        print(f"Max concurrent: {self.max_concurrent}")
        print(f"Images directory: {self.images_dir}\n")
        
        # Estimate
        remaining = len(releases) - start_idx
        # Conservative estimate: 2-5 seconds per image with concurrency
        estimated_seconds = (remaining / self.max_concurrent) * 3
        estimated_hours = estimated_seconds / 3600
        
        print(f"Estimated time: {estimated_hours:.1f} hours\n")
        print(f"{'='*60}\n")
        
        start_time = time.time()
        last_checkpoint = start_idx
        
        try:
            async with aiohttp.ClientSession() as session:
                idx = start_idx
                
                while idx < len(releases):
                    batch_start = idx
                    batch_end = min(idx + self.batch_size, len(releases))
                    
                    print(f"Batch {idx//self.batch_size + 1}: "
                          f"Processing {batch_start}-{batch_end} "
                          f"({idx}/{len(releases)}, {idx/len(releases)*100:.1f}%)")
                    
                    # Download batch
                    await self.download_batch(session, releases, batch_start, batch_end)
                    
                    # Update progress
                    elapsed = time.time() - start_time
                    rate = (idx - start_idx) / elapsed if elapsed > 0 else 0
                    remaining_time = (len(releases) - idx) / rate if rate > 0 else 0
                    
                    print(f"  Downloaded: {self.stats['downloaded']}, "
                          f"Failed: {self.stats['failed']}, "
                          f"Skipped: {self.stats['skipped']}")
                    print(f"  Rate: {rate:.1f} images/sec, "
                          f"ETA: {remaining_time/3600:.1f} hours\n")
                    
                    # Save checkpoint periodically
                    if idx - last_checkpoint >= self.checkpoint_interval:
                        self.save_checkpoint(idx)
                        last_checkpoint = idx
                    
                    idx = batch_end
                    
                    # Small delay between batches
                    await asyncio.sleep(0.5)
                    
        except KeyboardInterrupt:
            print("\n\nInterrupted! Saving checkpoint...")
            self.save_checkpoint(idx)
            print(f"Checkpoint saved at index {idx}")
            print(f"Run again to resume")
            sys.exit(0)
        
        # Final stats
        elapsed = time.time() - start_time
        
        print(f"\n{'='*60}")
        print("Download Complete!")
        print(f"{'='*60}\n")
        print(f"Total releases: {self.stats['total']}")
        print(f"Downloaded: {self.stats['downloaded']}")
        print(f"Failed: {self.stats['failed']}")
        print(f"Skipped: {self.stats['skipped']}")
        print(f"Time taken: {elapsed/3600:.2f} hours")
        print(f"Average rate: {self.stats['downloaded']/(elapsed/60):.1f} images/minute")
        
        # Clean up checkpoint
        if os.path.exists(self.checkpoint_path):
            os.remove(self.checkpoint_path)


async def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Batch download album cover images')
    parser.add_argument('--manifest', type=str, default='../data/releases_manifest_enriched.jsonl',
                        help='Path to releases manifest')
    parser.add_argument('--images-dir', type=str, default='./data/images',
                        help='Directory to save images')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Batch size for processing')
    parser.add_argument('--concurrent', type=int, default=10,
                        help='Max concurrent downloads')
    
    args = parser.parse_args()
    
    downloader = BatchImageDownloader(
        manifest_path=args.manifest,
        images_dir=args.images_dir,
        batch_size=args.batch_size,
        max_concurrent=args.concurrent
    )
    
    await downloader.download_all()


if __name__ == "__main__":
    asyncio.run(main())

