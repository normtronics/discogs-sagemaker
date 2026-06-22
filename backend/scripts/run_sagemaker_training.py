#!/usr/bin/env python3
"""
Upload dataset + code to S3 and launch a SageMaker training job.

Run from SageMaker Studio (remote Cursor) or anywhere with AWS creds:

  cd backend
  pip install sagemaker boto3
  python scripts/run_sagemaker_training.py --bucket discogs-sage-993268716868

In Studio, the execution role is detected automatically.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import boto3
import sagemaker
from sagemaker.pytorch import PyTorch

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


def _ensure_bucket(s3, bucket: str, region: str) -> None:
    try:
        s3.head_bucket(Bucket=bucket)
        print(f"✓ Bucket s3://{bucket}")
    except s3.exceptions.ClientError:
        print(f"Creating bucket s3://{bucket} ({region})...")
        if region == "us-east-1":
            s3.create_bucket(Bucket=bucket)
        else:
            s3.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": region},
            )


def _upload_data(s3, bucket: str) -> None:
    manifest = REPO_ROOT / "data" / "releases_manifest.jsonl"
    enriched = REPO_ROOT / "data" / "releases_manifest_enriched.jsonl"
    images = REPO_ROOT / "data" / "images"

    if enriched.exists():
        src, key = enriched, "data/releases_manifest_enriched.jsonl"
    elif manifest.exists():
        src, key = manifest, "data/releases_manifest.jsonl"
    else:
        raise FileNotFoundError(
            "No manifest under data/. Run from repo root:\n"
            "  python backend/scripts/build_data.py --count 500\n"
            "Set DISCOGS_USER_TOKEN in backend/.env.local first."
        )

    print(f"Uploading manifest → s3://{bucket}/{key}")
    s3.upload_file(str(src), bucket, key)

    if not images.is_dir() or not any(images.iterdir()):
        raise FileNotFoundError(
            f"No images in {images}. Re-run build_data without --skip-download-images."
        )

    print(f"Syncing images → s3://{bucket}/data/images/")
    subprocess.run(
        ["aws", "s3", "sync", str(images), f"s3://{bucket}/data/images/", "--exclude", "*.DS_Store"],
        check=True,
    )


def _upload_code(s3, bucket: str) -> str:
    """Package ml/, data/, train.py, inference.py and upload tarball."""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        for name in ("ml", "data", "train.py", "inference.py"):
            src = BACKEND_DIR / name
            if src.is_dir():
                subprocess.run(["cp", "-r", str(src), str(root / name)], check=True)
            else:
                subprocess.run(["cp", str(src), str(root / name)], check=True)

        archive = root / "sourcedir.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            for item in root.iterdir():
                if item.name != "sourcedir.tar.gz":
                    tar.add(item, arcname=item.name)

        s3_key = "code/sourcedir.tar.gz"
        print(f"Uploading code → s3://{bucket}/{s3_key}")
        s3.upload_file(str(archive), bucket, s3_key)
    return f"s3://{bucket}/code/sourcedir.tar.gz"


def _resolve_role(role_arg: str | None) -> str:
    if role_arg:
        return role_arg
    try:
        return sagemaker.get_execution_role()
    except Exception:
        env_role = os.environ.get("SAGEMAKER_ROLE")
        if env_role:
            return env_role
        raise RuntimeError(
            "Could not detect SageMaker role. In Studio this is automatic; "
            "else pass --role or set SAGEMAKER_ROLE."
        ) from None


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload to S3 and start SageMaker training")
    parser.add_argument("--bucket", required=True, help="S3 bucket name (not s3:// prefix)")
    parser.add_argument("--region", default=os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
    parser.add_argument("--role", default=None, help="IAM role ARN (auto in Studio)")
    parser.add_argument("--instance-type", default="ml.m5.xlarge")
    parser.add_argument("--epochs", type=int, default=10)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--skip-upload", action="store_true", help="Skip S3 upload (data+code already there)")
    parser.add_argument("--job-name", default="album-classifier")
    args = parser.parse_args()

    session = sagemaker.Session(boto_session=boto3.Session(region_name=args.region))
    s3 = session.boto_session.client("s3")

    if not args.skip_upload:
        _ensure_bucket(s3, args.bucket, args.region)
        _upload_data(s3, args.bucket)
        code_s3 = _upload_code(s3, args.bucket)
    else:
        code_s3 = f"s3://{args.bucket}/code/sourcedir.tar.gz"
        print(f"Skipping upload; using {code_s3}")

    role = _resolve_role(args.role)
    print(f"✓ Role: {role}")

    # Local source_dir is more reliable than passing the S3 tarball path to the SDK.
    estimator = PyTorch(
        entry_point="train.py",
        source_dir=str(BACKEND_DIR),
        role=role,
        instance_type=args.instance_type,
        instance_count=1,
        framework_version="2.4.0",  # sagemaker 2.232.x image map (2.5.0 unsupported)
        py_version="py311",
        hyperparameters={
            "epochs": str(args.epochs),
            "batch-size": str(args.batch_size),
        },
        output_path=f"s3://{args.bucket}/models/",
        sagemaker_session=session,
        base_job_name=args.job_name,
        max_run=86400,
    )

    print("\nStarting training job...")
    print(f"  Data:   s3://{args.bucket}/data/")
    print(f"  Output: s3://{args.bucket}/models/")
    print(f"  Instance: {args.instance_type}\n")

    estimator.fit({"training": f"s3://{args.bucket}/data/"})

    print("\n✓ Training complete")
    print(f"  Model artifact: {estimator.model_data}")
    print("\nDeploy from notebooks/studio_notebook.ipynb (Step 2) or:")
    print("  from sagemaker.pytorch import PyTorchModel")
    print(f"  model = PyTorchModel(model_data='{estimator.model_data}', ...)")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)
