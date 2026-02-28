"""Dataset and data loading. Shared by train and inference."""
import json
import os
from typing import List, Dict

from torch.utils.data import Dataset
from torchvision import transforms
from PIL import Image
from sklearn.model_selection import train_test_split


def load_releases_data(path: str) -> List[Dict]:
    """Load releases from JSONL manifest."""
    releases = []
    with open(path) as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))
    return releases


class AlbumDataset(Dataset):
    """Dataset for album cover images."""

    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        image = Image.open(self.image_paths[idx]).convert("RGB")
        if self.transform:
            image = self.transform(image)
        return image, self.labels[idx]


def _get_image_paths_for_release(images_dir: str, release_idx: int) -> List[str]:
    """Get all image paths for a release (multi {idx}_0.jpg, {idx}_1.jpg, ... or single {idx}.jpg)."""
    # Prefer multi format when present (allows using all images after re-download)
    paths = []
    img_idx = 0
    while True:
        p = os.path.join(images_dir, f"{release_idx}_{img_idx}.jpg")
        if os.path.exists(p):
            paths.append(p)
            img_idx += 1
        else:
            break
    if paths:
        return paths
    single = os.path.join(images_dir, f"{release_idx}.jpg")
    if os.path.exists(single):
        return [single]
    return []


def create_datasets(images_dir: str, releases: List[Dict], test_size: float = 0.2):
    """Create train and validation datasets. Uses all images per release (same label)."""
    image_paths = []
    labels = []
    for idx, _ in enumerate(releases):
        for path in _get_image_paths_for_release(images_dir, idx):
            image_paths.append(path)
            labels.append(idx)

    if not image_paths:
        raise ValueError(f"No images found in {images_dir}")

    # Split by image (same album can be in train and val) - tests "recognize different photo of same album"
    from collections import Counter
    can_stratify = min(Counter(labels).values()) >= 2
    train_paths, val_paths, train_labels, val_labels = train_test_split(
        image_paths, labels, test_size=test_size, random_state=42,
        stratify=labels if can_stratify else None,
    )

    train_tf = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])
    val_tf = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    ])

    return (
        AlbumDataset(train_paths, train_labels, train_tf),
        AlbumDataset(val_paths, val_labels, val_tf),
    )
