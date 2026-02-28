#!/usr/bin/env python3
"""
Train album classifier. Works locally and in SageMaker.
"""
import os
import json
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader

from .dataset import load_releases_data, create_datasets
from .model import create_model


def _find_manifest(data_dir: str) -> str:
    """Find manifest file in data dir."""
    names = [
        "releases_manifest_enriched.jsonl",
        "releases_manifest.jsonl",
        "releases_metadata.jsonl",
        "releases_manifest_50.jsonl",
    ]
    for n in names:
        p = os.path.join(data_dir, n)
        if os.path.exists(p):
            return p
    raise FileNotFoundError(f"No manifest found in {data_dir}. Tried: {names}")


def _find_images_dir(data_dir: str, images_dir: str) -> str:
    """Resolve images directory."""
    if images_dir:
        return images_dir
    candidates = [
        os.path.join(data_dir, "images"),
        os.path.join(os.path.dirname(data_dir), "data", "images"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return candidates[0]


def train(args):
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    manifest_path = _find_manifest(args.data_dir)
    images_dir = _find_images_dir(args.data_dir, args.images_dir)

    releases = load_releases_data(manifest_path)
    print(f"Loaded {len(releases)} releases from {manifest_path}")

    train_ds, val_ds = create_datasets(images_dir, releases, test_size=args.test_size)
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, shuffle=False, num_workers=args.num_workers)

    num_classes = len(releases)
    model = create_model(num_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.learning_rate, weight_decay=args.weight_decay)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    best_acc = 0.0
    best_path = os.path.join(args.model_dir, "model.pth")
    os.makedirs(args.model_dir, exist_ok=True)

    for epoch in range(args.epochs):
        model.train()
        train_loss, train_correct, train_total = 0.0, 0, 0
        for images, labels in train_loader:
            images, labels = images.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(images), labels)
            loss.backward()
            optimizer.step()
            train_loss += loss.item()
            _, pred = model(images).max(1)
            train_correct += (pred == labels).sum().item()
            train_total += labels.size(0)

        model.eval()
        val_correct, val_total = 0, 0
        with torch.no_grad():
            for images, labels in val_loader:
                images, labels = images.to(device), labels.to(device)
                _, pred = model(images).max(1)
                val_correct += (pred == labels).sum().item()
                val_total += labels.size(0)

        train_acc = 100 * train_correct / train_total
        val_acc = 100 * val_correct / val_total
        print(f"Epoch {epoch+1}/{args.epochs} - Train: {train_loss/len(train_loader):.4f} / {train_acc:.2f}% - Val: {val_acc:.2f}%")

        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), best_path)

        scheduler.step()

    metadata = {
        "num_classes": num_classes,
        "best_val_accuracy": best_acc,
        "epochs": args.epochs,
        "releases": releases,
    }
    with open(os.path.join(args.model_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, indent=2)

    print(f"✓ Training complete. Best val acc: {best_acc:.2f}%")
    return best_acc


def parse_args():
    p = argparse.ArgumentParser(description="Train album classifier")
    p.add_argument("--data-dir", type=str, default=os.environ.get("SM_CHANNEL_TRAINING", "data"))
    p.add_argument("--images-dir", type=str, default=None)
    p.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "models"))
    p.add_argument("--epochs", type=int, default=25)
    p.add_argument("--batch-size", type=int, default=16)
    p.add_argument("--learning-rate", type=float, default=0.001)
    p.add_argument("--weight-decay", type=float, default=1e-4)
    p.add_argument("--test-size", type=float, default=0.2)
    p.add_argument("--num-workers", type=int, default=0)
    return p.parse_args()


if __name__ == "__main__":
    args = parse_args()
    train(args)
