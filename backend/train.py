#!/usr/bin/env python3
"""SageMaker entry point. Calls ml.train."""
from ml.train import train, parse_args

if __name__ == "__main__":
    train(parse_args())
