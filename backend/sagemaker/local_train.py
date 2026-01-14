#!/usr/bin/env python3
"""
Local SageMaker Training Script
Simulates SageMaker training environment locally
"""
import os
import sys
import argparse
from pathlib import Path

# Add parent directory to path to import train module
sys.path.insert(0, os.path.dirname(__file__))

from train import train, parse_args


def setup_local_environment():
    """Setup local environment to simulate SageMaker"""
    # __file__ is backend/sagemaker/local_train.py
    # parent is backend/sagemaker/, parent.parent is backend/, parent.parent.parent is project root
    backend_root = Path(__file__).parent.parent
    project_root = backend_root.parent
    
    # Set SageMaker environment variables
    # Manifest is in project_root/data/, images are in backend/data/images/
    env_vars = {
        'SM_CHANNEL_TRAINING': str(project_root / 'data'),  # Where manifest is
        'SM_MODEL_DIR': str(backend_root / 'sagemaker' / 'models'),
        'SM_OUTPUT_DATA_DIR': str(backend_root / 'sagemaker' / 'output'),
        'SM_NUM_GPUS': '1' if os.system('which nvidia-smi > /dev/null 2>&1') == 0 else '0',
    }
    
    for key, value in env_vars.items():
        os.environ[key] = value
    
    # Create directories
    Path(env_vars['SM_MODEL_DIR']).mkdir(parents=True, exist_ok=True)
    Path(env_vars['SM_OUTPUT_DATA_DIR']).mkdir(parents=True, exist_ok=True)
    
    return env_vars


def main():
    """Run training locally"""
    print("=" * 60)
    print("Local SageMaker Training")
    print("=" * 60)
    
    # Setup environment
    env_vars = setup_local_environment()
    
    print("\nEnvironment Configuration:")
    for key, value in env_vars.items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 60)
    print("Starting Training...")
    print("=" * 60 + "\n")
    
    # Parse arguments and train
    args = parse_args()
    
    # Override with local paths if not specified
    if args.data_dir == os.environ.get('SM_CHANNEL_TRAINING'):
        print(f"Using data directory: {args.data_dir}")
    
    # Train model
    accuracy = train(args)
    
    print("\n" + "=" * 60)
    print("Training Complete!")
    print("=" * 60)
    print(f"Final Accuracy: {accuracy:.2f}%")
    print(f"Model saved to: {args.model_dir}")
    print("\nTo test inference locally, run:")
    print("  python sagemaker/local_predict.py --image data/images/0.jpg")
    

if __name__ == '__main__':
    main()

