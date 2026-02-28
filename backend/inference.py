#!/usr/bin/env python3
"""SageMaker inference entry point. Re-exports ml.inference handlers."""
from ml.inference import model_fn, input_fn, predict_fn, output_fn
