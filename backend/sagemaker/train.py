#!/usr/bin/env python3
"""
SageMaker Training Script for Album Classification Model
Compatible with SageMaker PyTorch containers
"""
import os
import json
import argparse
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
from pathlib import Path
from sklearn.model_selection import train_test_split


class AlbumDataset(Dataset):
    """Dataset for album cover images"""
    
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        image_path = self.image_paths[idx]
        label = self.labels[idx]
        
        # Load image
        image = Image.open(image_path).convert("RGB")
        
        if self.transform:
            image = self.transform(image)
        
        return image, label


def load_releases_data(manifest_path):
    """Load releases metadata from JSONL file"""
    releases = []
    with open(manifest_path, 'r') as f:
        for line in f:
            if line.strip():
                releases.append(json.loads(line))
    return releases


def create_datasets(images_dir, releases, test_size=0.2):
    """Create train and validation datasets"""
    image_paths = []
    labels = []
    
    # Collect all valid image paths and labels
    for idx, release in enumerate(releases):
        image_path = os.path.join(images_dir, f"{idx}.jpg")
        if os.path.exists(image_path):
            image_paths.append(image_path)
            labels.append(idx)
    
    if len(image_paths) == 0:
        raise ValueError(f"No images found in {images_dir}")
    
    print(f"Found {len(image_paths)} images")
    
    # Check if we can use stratified split (need at least 2 samples per class)
    from collections import Counter
    label_counts = Counter(labels)
    min_samples = min(label_counts.values())
    can_stratify = min_samples >= 2
    
    if not can_stratify:
        print(f"Warning: Some classes have only 1 sample, using non-stratified split")
    
    # Split into train and validation
    train_paths, val_paths, train_labels, val_labels = train_test_split(
        image_paths, labels, test_size=test_size, random_state=42, 
        stratify=labels if can_stratify else None
    )
    
    # Data augmentation for training
    train_transform = transforms.Compose([
        transforms.Resize((256, 256)),
        transforms.RandomCrop((224, 224)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.2, contrast=0.2, saturation=0.2),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225])
    ])
    
    train_dataset = AlbumDataset(train_paths, train_labels, train_transform)
    val_dataset = AlbumDataset(val_paths, val_labels, val_transform)
    
    return train_dataset, val_dataset


def create_model(num_classes):
    """Create ResNet50 model for album classification"""
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    
    # Freeze early layers
    for param in list(model.parameters())[:-30]:
        param.requires_grad = False
    
    # Replace final layer
    num_features = model.fc.in_features
    model.fc = nn.Linear(num_features, num_classes)
    
    return model


def train_epoch(model, train_loader, criterion, optimizer, device):
    """Train for one epoch"""
    model.train()
    train_loss = 0.0
    train_correct = 0
    train_total = 0
    
    for images, labels in train_loader:
        images = images.to(device)
        labels = labels.to(device)
        
        optimizer.zero_grad()
        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()
        
        train_loss += loss.item()
        _, predicted = torch.max(outputs.data, 1)
        train_total += labels.size(0)
        train_correct += (predicted == labels).sum().item()
    
    avg_loss = train_loss / len(train_loader)
    accuracy = 100 * train_correct / train_total
    
    return avg_loss, accuracy


def validate(model, val_loader, criterion, device):
    """Validate the model"""
    model.eval()
    val_loss = 0.0
    val_correct = 0
    val_total = 0
    
    with torch.no_grad():
        for images, labels in val_loader:
            images = images.to(device)
            labels = labels.to(device)
            
            outputs = model(images)
            loss = criterion(outputs, labels)
            
            val_loss += loss.item()
            _, predicted = torch.max(outputs.data, 1)
            val_total += labels.size(0)
            val_correct += (predicted == labels).sum().item()
    
    avg_loss = val_loss / len(val_loader)
    accuracy = 100 * val_correct / val_total
    
    return avg_loss, accuracy


def train(args):
    """Main training function"""
    # Set device
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Load releases data
    # Manifest is in project_root/data/, images are in backend/data/images/
    # When running locally: args.data_dir is '../data' (project root data)
    # When in SageMaker: args.data_dir is '/opt/ml/input/data/training'
    
    # Try manifest in data_dir first (for SageMaker)
    possible_manifests = [
        os.path.join(args.data_dir, 'releases_manifest_enriched.jsonl'),
        os.path.join(args.data_dir, 'releases_manifest.jsonl'),
        os.path.join(args.data_dir, 'releases_metadata.jsonl'),
        os.path.join(args.data_dir, 'releases_manifest_50.jsonl'),
    ]
    
    # Also try project_root/data/ (for local runs from backend/)
    if not any(os.path.exists(p) for p in possible_manifests):
        # If running from backend/sagemaker/, go to project_root/data/
        script_dir = os.path.dirname(os.path.abspath(__file__))  # backend/sagemaker/
        backend_root = os.path.dirname(script_dir)  # backend/
        project_root = os.path.dirname(backend_root)  # project root
        data_dir = os.path.join(project_root, 'data')
        
        possible_manifests.extend([
            os.path.join(data_dir, 'releases_manifest_enriched.jsonl'),
            os.path.join(data_dir, 'releases_manifest.jsonl'),
            os.path.join(data_dir, 'releases_metadata.jsonl'),
            os.path.join(data_dir, 'releases_manifest_50.jsonl'),
        ])
    
    manifest_path = None
    for path in possible_manifests:
        if os.path.exists(path):
            manifest_path = path
            break
    
    if not manifest_path:
        raise ValueError(f"No manifest file found. Tried: {possible_manifests}")
    
    print(f"Loading releases from {manifest_path}")
    releases = load_releases_data(manifest_path)
    print(f"Loaded {len(releases)} releases")
    
    # Determine images directory
    if args.images_dir:
        images_dir = args.images_dir
    else:
        # In SageMaker: images are in data_dir/images/
        # Locally: images are in backend/data/images/
        images_dir = os.path.join(args.data_dir, 'images')
        if not os.path.exists(images_dir):
            # Try backend/data/images/ for local runs
            script_dir = os.path.dirname(os.path.abspath(__file__))  # backend/sagemaker/
            backend_root = os.path.dirname(script_dir)  # backend/
            images_dir = os.path.join(backend_root, 'data', 'images')
    
    print(f"Images directory: {images_dir}")
    train_dataset, val_dataset = create_datasets(images_dir, releases, test_size=args.test_size)
    
    # Create data loaders
    batch_size = args.batch_size
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=args.num_workers)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=args.num_workers)
    
    print(f"Training samples: {len(train_dataset)}, Validation samples: {len(val_dataset)}")
    
    # Create model
    num_classes = len(releases)
    model = create_model(num_classes)
    model = model.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=args.learning_rate)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=args.lr_step_size, gamma=args.lr_gamma)
    
    # Training loop
    best_acc = 0.0
    best_model_path = os.path.join(args.model_dir, 'model.pth')
    
    for epoch in range(args.epochs):
        print(f"\nEpoch {epoch + 1}/{args.epochs}")
        print("-" * 50)
        
        # Train
        train_loss, train_acc = train_epoch(model, train_loader, criterion, optimizer, device)
        print(f"Train Loss: {train_loss:.4f}, Train Acc: {train_acc:.2f}%")
        
        # Validate
        val_loss, val_acc = validate(model, val_loader, criterion, device)
        print(f"Val Loss: {val_loss:.4f}, Val Acc: {val_acc:.2f}%")
        
        # Save best model
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), best_model_path)
            print(f"✓ Model saved with accuracy: {best_acc:.2f}%")
        
        scheduler.step()
    
    # Save final model
    torch.save(model.state_dict(), best_model_path)
    
    # Save model metadata
    metadata = {
        "num_classes": num_classes,
        "best_val_accuracy": best_acc,
        "epochs": args.epochs,
        "train_size": len(train_dataset),
        "val_size": len(val_dataset),
        "releases": releases
    }
    
    metadata_path = os.path.join(args.model_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\nTraining completed!")
    print(f"Best validation accuracy: {best_acc:.2f}%")
    print(f"Model saved to: {best_model_path}")
    print(f"Metadata saved to: {metadata_path}")
    
    return best_acc


def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='Train album classification model')
    
    # SageMaker specific arguments
    # When running locally: '../data' points to project_root/data (for manifest)
    # When in SageMaker: SM_CHANNEL_TRAINING points to /opt/ml/input/data/training
    parser.add_argument('--data-dir', type=str, default=os.environ.get('SM_CHANNEL_TRAINING', '../data'))
    
    # Images are in backend/data/images/
    parser.add_argument('--images-dir', type=str, default=None,
                        help='Directory containing images (default: backend/data/images)')
    parser.add_argument('--model-dir', type=str, default=os.environ.get('SM_MODEL_DIR', './models'))
    parser.add_argument('--output-data-dir', type=str, default=os.environ.get('SM_OUTPUT_DATA_DIR', './output'))
    
    # Training arguments
    parser.add_argument('--epochs', type=int, default=10)
    parser.add_argument('--batch-size', type=int, default=8)
    parser.add_argument('--learning-rate', type=float, default=0.001)
    parser.add_argument('--lr-step-size', type=int, default=5)
    parser.add_argument('--lr-gamma', type=float, default=0.1)
    parser.add_argument('--test-size', type=float, default=0.2)
    parser.add_argument('--num-workers', type=int, default=0)
    
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    
    # Create output directories
    os.makedirs(args.model_dir, exist_ok=True)
    os.makedirs(args.output_data_dir, exist_ok=True)
    
    # Train model
    train(args)

