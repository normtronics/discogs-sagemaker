#!/usr/bin/env python3
"""
SageMaker Processing entry point: build dataset and sync to S3.

Runs build_data.py under /opt/ml/processing/work, pulls/pushes checkpoints
from s3://BUCKET/PREFIX so the job survives processing instance restarts
and output is ready for training without a separate upload step.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

WORK_ROOT = Path("/opt/ml/processing/work")
OUTPUT_ROOT = Path("/opt/ml/processing/output")
BACKEND_EXTRACT = WORK_ROOT / "backend"


def _extract_backend(tar_path: Path) -> Path:
    """Extract backend tarball uploaded via ProcessingInput."""
    import tarfile
    import shutil

    if BACKEND_EXTRACT.exists():
        shutil.rmtree(BACKEND_EXTRACT)
    BACKEND_EXTRACT.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tar:
        tar.extractall(WORK_ROOT)
    if not (BACKEND_EXTRACT / "scripts" / "build_data.py").exists():
        raise FileNotFoundError(f"Invalid backend tar: {tar_path}")
    print(f"✓ Extracted backend to {BACKEND_EXTRACT}")
    return BACKEND_EXTRACT


def _find_backend_tar() -> Path:
    """Locate backend tarball from ProcessingInput mount."""
    candidates = [
        Path("/opt/ml/processing/input/backend_pkg/processing_backend.tar.gz"),
        Path("/opt/ml/processing/input/backend_pkg"),
    ]
    for c in candidates:
        if c.is_file():
            return c
        if c.is_dir():
            for f in c.glob("*.tar.gz"):
                return f
    raise FileNotFoundError(
        "Backend tarball not found. Notebook must upload code/processing_backend.tar.gz "
        "and pass it as a ProcessingInput."
    )


def _pip_install(backend_dir: Path) -> None:
    req = backend_dir / "requirements-processing.txt"
    if req.exists():
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-q", "-r", str(req)],
            check=True,
        )


def _s3_key(prefix: str, name: str) -> str:
    prefix = prefix.strip("/")
    return f"{prefix}/{name}" if prefix else name


def _download_if_exists(s3, bucket: str, key: str, dest: Path) -> bool:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        s3.download_file(bucket, key, str(dest))
        print(f"  ↓ s3://{bucket}/{key}")
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] in ("404", "NoSuchKey"):
            return False
        raise


def _upload_file(s3, bucket: str, key: str, src: Path) -> None:
    if src.exists():
        s3.upload_file(str(src), bucket, key)
        print(f"  ↑ s3://{bucket}/{key}")


def _sync_images_up(s3, bucket: str, prefix: str, images_dir: Path) -> int:
    count = 0
    if not images_dir.is_dir():
        return 0
    for path in images_dir.iterdir():
        if path.is_file():
            _upload_file(s3, bucket, _s3_key(prefix, f"images/{path.name}"), path)
            count += 1
    return count


def _sync_from_s3(s3, bucket: str, prefix: str, work: Path) -> None:
    data = work / "data"
    data.mkdir(parents=True, exist_ok=True)
    print("Pulling resume state from S3...")
    _download_if_exists(s3, bucket, _s3_key(prefix, "enrich_checkpoint.json"), data / "enrich_checkpoint.json")
    _download_if_exists(s3, bucket, _s3_key(prefix, "releases_manifest.jsonl"), data / "releases_manifest.jsonl")
    _download_if_exists(s3, bucket, _s3_key(prefix, "discogs_releases.xml.gz"), data / "discogs_releases.xml.gz")

    images_dir = data / "images"
    images_dir.mkdir(exist_ok=True)
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=_s3_key(prefix, "images/")):
        for obj in page.get("Contents", []):
            name = Path(obj["Key"]).name
            if name:
                dest = images_dir / name
                if not dest.exists():
                    s3.download_file(bucket, obj["Key"], str(dest))


def _sync_to_s3(s3, bucket: str, prefix: str, work: Path) -> None:
    data = work / "data"
    print("Pushing results to S3...")
    _upload_file(s3, bucket, _s3_key(prefix, "releases_manifest.jsonl"), data / "releases_manifest.jsonl")
    _upload_file(s3, bucket, _s3_key(prefix, "enrich_checkpoint.json"), data / "enrich_checkpoint.json")
    n = _sync_images_up(s3, bucket, prefix, data / "images")
    print(f"  ↑ {n} image(s)")


def _copy_to_processing_output(work: Path) -> None:
    """SageMaker ProcessingOutput uploads /opt/ml/processing/output at job end."""
    import shutil

    out_data = OUTPUT_ROOT / "data"
    out_data.mkdir(parents=True, exist_ok=True)
    src = work / "data"
    if not src.exists():
        return
    for name in ("releases_manifest.jsonl", "enrich_checkpoint.json"):
        f = src / name
        if f.exists():
            shutil.copy2(f, out_data / name)
    src_images = src / "images"
    if src_images.is_dir():
        shutil.copytree(src_images, out_data / "images", dirs_exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build dataset on SageMaker Processing")
    parser.add_argument("--s3-bucket", required=True)
    parser.add_argument("--s3-prefix", default="data")
    parser.add_argument("--count", type=int, default=500)
    parser.add_argument("--skip-download-dump", action="store_true")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-2"))
    args = parser.parse_args()

    if not os.environ.get("DISCOGS_USER_TOKEN") and not (
        os.environ.get("DISCOGS_CONSUMER_KEY") and os.environ.get("DISCOGS_CONSUMER_SECRET")
    ):
        raise RuntimeError("Set DISCOGS_USER_TOKEN in the processing job environment")

    WORK_ROOT.mkdir(parents=True, exist_ok=True)
    backend_dir = _extract_backend(_find_backend_tar())
    _pip_install(backend_dir)
    s3 = boto3.client("s3", region_name=args.region)

    _sync_from_s3(s3, args.s3_bucket, args.s3_prefix, WORK_ROOT)

    cmd = [
        sys.executable,
        str(backend_dir / "scripts" / "build_data.py"),
        "--project-root",
        str(WORK_ROOT),
        "--count",
        str(args.count),
    ]
    if args.skip_download_dump or (WORK_ROOT / "data" / "discogs_releases.xml.gz").exists():
        cmd.append("--skip-download-dump")

    print("\nRunning build_data.py...")
    print(" ", " ".join(cmd))
    subprocess.run(cmd, check=True, env={**os.environ, "PYTHONPATH": str(backend_dir)})

    _sync_to_s3(s3, args.s3_bucket, args.s3_prefix, WORK_ROOT)
    _copy_to_processing_output(WORK_ROOT)
    print("\n✓ Processing build complete")


if __name__ == "__main__":
    main()
