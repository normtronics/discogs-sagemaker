#!/usr/bin/env python3
"""Download ResNet50 pretrained weights to torch hub cache. Run on a machine with internet."""
import os
import torch

# Same path the model expects
cache_dir = torch.hub.get_dir()
os.makedirs(os.path.join(cache_dir, "checkpoints"), exist_ok=True)
path = os.path.join(cache_dir, "checkpoints", "resnet50-0676ba61.pth")

if os.path.exists(path):
    print(f"Already exists: {path}")
else:
    print(f"Downloading to {path}...")
    torch.hub.download_url_to_file(
        "https://download.pytorch.org/models/resnet50-0676ba61.pth",
        path,
    )
    print("Done. Copy this file to your offline machine at:")
    print(f"  {path}")
