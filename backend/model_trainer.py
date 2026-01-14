import os
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
from torchvision import models, transforms
from PIL import Image
from pathlib import Path
from typing import List, Dict
from sklearn.model_selection import train_test_split


class AlbumDataset(Dataset):
    """Dataset for album cover images"""
    
    def __init__(self, image_paths: List[str], labels: List[int], transform=None):
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


def create_datasets(images_dir: str, releases: List[Dict]):
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
        raise ValueError("No images found. Please download images first.")
    
    print(f"Found {len(image_paths)} images")
    
    # Check if we can use stratified split (need at least 2 samples per class)
    from collections import Counter
    label_counts = Counter(labels)
    min_samples = min(label_counts.values())
    can_stratify = min_samples >= 2
    
    if not can_stratify:
        print(f"Warning: Some classes have only 1 sample, using non-stratified split")
    
    # Split into train and validation (use smaller test size for small datasets)
    test_size = min(0.2, max(0.1, len(image_paths) * 0.15 / len(image_paths)))
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
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    val_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(
            mean=[0.485, 0.456, 0.406],
            std=[0.229, 0.224, 0.225]
        )
    ])
    
    train_dataset = AlbumDataset(train_paths, train_labels, train_transform)
    val_dataset = AlbumDataset(val_paths, val_labels, val_transform)
    
    return train_dataset, val_dataset


def train_model(images_dir: str, releases: List[Dict], model_path: str, epochs: int = 10) -> Dict:
    """
    Train album classification model using transfer learning
    
    Args:
        images_dir: Directory containing album images
        releases: List of release metadata
        model_path: Path to save trained model
        epochs: Number of training epochs
    
    Returns:
        Training results dictionary
    """
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")
    
    # Create datasets
    train_dataset, val_dataset = create_datasets(images_dir, releases)
    
    # Create data loaders (adjust batch size for small datasets)
    batch_size = min(8, max(4, len(train_dataset) // 5))
    train_loader = DataLoader(train_dataset, batch_size=batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_dataset, batch_size=batch_size, shuffle=False, num_workers=0)
    
    # Create model
    num_classes = len(releases)
    model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
    
    # Freeze early layers (keep more layers trainable for small datasets)
    for param in list(model.parameters())[:-30]:
        param.requires_grad = False
    
    # Replace final layer
    num_features = model.fc.in_features
    model.fc = nn.Linear(num_features, num_classes)
    model = model.to(device)
    
    # Loss and optimizer
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    scheduler = optim.lr_scheduler.StepLR(optimizer, step_size=5, gamma=0.1)
    
    # Training loop
    best_acc = 0.0
    
    for epoch in range(epochs):
        print(f"\nEpoch {epoch + 1}/{epochs}")
        print("-" * 30)
        
        # Training phase
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
        
        train_acc = 100 * train_correct / train_total
        print(f"Train Loss: {train_loss/len(train_loader):.4f}, Train Acc: {train_acc:.2f}%")
        
        # Validation phase
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
        
        val_acc = 100 * val_correct / val_total
        print(f"Val Loss: {val_loss/len(val_loader):.4f}, Val Acc: {val_acc:.2f}%")
        
        # Save best model
        if val_acc > best_acc:
            best_acc = val_acc
            torch.save(model.state_dict(), model_path)
            print(f"Model saved with accuracy: {best_acc:.2f}%")
        
        scheduler.step()
    
    # Always save the final model even if validation accuracy was poor
    torch.save(model.state_dict(), model_path)
    print(f"\nTraining completed. Best validation accuracy: {best_acc:.2f}%")
    print(f"Final model saved to {model_path}")
    
    return {
        "accuracy": best_acc,
        "epochs": epochs,
        "num_classes": num_classes,
        "train_size": len(train_dataset),
        "val_size": len(val_dataset)
    }


if __name__ == "__main__":
    # For standalone testing
    from data_loader import load_releases_data
    import os
    
    # Try multiple manifest paths
    possible_manifests = [
        "../data/releases_manifest_enriched.jsonl",
    
    ]
    
    releases = None
    for manifest_path in possible_manifests:
        if os.path.exists(manifest_path):
            releases = load_releases_data(manifest_path)
            print(f"Loaded {len(releases)} releases from {manifest_path}")
            break
    
    if not releases:
        print("Error: No manifest file found")
        sys.exit(1)
    
    results = train_model("./data/images", releases, "./models/album_classifier.pth", epochs=5)
    print(f"\nTraining results: {results}")

