# SageMaker Instance Types Guide

Guide to choosing the right instance type for training and inference.

## Training Instance Types

### CPU Instances (Cheaper, Slower)

| Instance Type | vCPUs | Memory | Cost/Hour | Best For |
|--------------|-------|--------|-----------|----------|
| `ml.m5.large` | 2 | 8 GB | ~$0.115 | Testing, small datasets |
| `ml.m5.xlarge` | 4 | 16 GB | ~$0.23 | **Recommended for CPU** |
| `ml.m5.2xlarge` | 8 | 32 GB | ~$0.46 | Larger datasets |
| `ml.m5.4xlarge` | 16 | 64 GB | ~$0.92 | Very large datasets |

### GPU Instances (Faster, More Expensive)

| Instance Type | GPUs | vCPUs | Memory | Cost/Hour | Best For |
|--------------|------|-------|--------|-----------|----------|
| `ml.p3.2xlarge` | 1x V100 | 8 | 61 GB | ~$3.06 | **Recommended for GPU** |
| `ml.p3.8xlarge` | 4x V100 | 32 | 244 GB | ~$12.24 | Large-scale training |
| `ml.g4dn.xlarge` | 1x T4 | 4 | 16 GB | ~$0.736 | Budget GPU option |
| `ml.g4dn.2xlarge` | 1x T4 | 8 | 32 GB | ~$0.94 | Better GPU performance |

### Spot Instances (Up to 90% cheaper)

You can use Spot instances for training to save money:

```python
estimator = PyTorch(
    # ... other config ...
    use_spot_instances=True,  # Enable Spot
    max_wait=86400,  # Max wait time: 24 hours
    max_run=86400,  # Max run time: 24 hours
)
```

**Warning**: Spot instances can be interrupted. Use checkpoints!

## Inference Instance Types

### Real-time Endpoints

| Instance Type | vCPUs | Memory | Cost/Hour | Best For |
|--------------|-------|--------|-----------|----------|
| `ml.t2.medium` | 2 | 4 GB | ~$0.047 | **Cheapest**, low traffic |
| `ml.t3.medium` | 2 | 4 GB | ~$0.052 | Burstable, low traffic |
| `ml.m5.large` | 2 | 8 GB | ~$0.115 | **Recommended**, steady traffic |
| `ml.m5.xlarge` | 4 | 16 GB | ~$0.23 | Higher traffic |
| `ml.m5.2xlarge` | 8 | 32 GB | ~$0.46 | Very high traffic |

### Serverless Inference (Scales to Zero)

```python
from sagemaker.serverless import ServerlessInferenceConfig

predictor = model.deploy(
    serverless_inference_config=ServerlessInferenceConfig(
        memory_size_in_mb=2048,  # 1024-10240 MB
        max_concurrency=10,  # Max concurrent requests
    ),
    endpoint_name='album-classifier-serverless'
)
```

**Cost**: Pay per invocation + compute time (scales to zero when idle)

## How to Change Instance Type

### In the Notebook

Simply change the `instance_type` parameter:

```python
# For training - CPU option (cheaper)
estimator = PyTorch(
    # ... other config ...
    instance_type='ml.m5.xlarge',  # ← Change this
)

# For training - GPU option (faster)
estimator = PyTorch(
    # ... other config ...
    instance_type='ml.p3.2xlarge',  # ← Change this
)

# For inference
predictor = model.deploy(
    # ... other config ...
    instance_type='ml.m5.large',  # ← Change this
)
```

## Recommendations

### For Training

**Start with CPU** (if budget-conscious):
```python
instance_type='ml.m5.xlarge'  # ~$0.23/hour, takes 20-30 min
```

**Use GPU** (if you want faster training):
```python
instance_type='ml.p3.2xlarge'  # ~$3.06/hour, takes 5-10 min
```

**Use Spot** (to save money):
```python
instance_type='ml.p3.2xlarge'
use_spot_instances=True  # Can save 50-90%
max_wait=86400
```

### For Inference

**Development/Testing**:
```python
instance_type='ml.t2.medium'  # Cheapest, ~$0.047/hour
```

**Production (Recommended)**:
```python
instance_type='ml.m5.large'  # Good balance, ~$0.115/hour
```

**High Traffic**:
```python
instance_type='ml.m5.xlarge'  # More capacity, ~$0.23/hour
```

## Cost Comparison Example

Training 10 epochs on your dataset:

| Instance | Cost/Hour | Est. Time | Total Cost |
|----------|-----------|-----------|------------|
| `ml.m5.xlarge` (CPU) | $0.23 | 25 min | ~$0.10 |
| `ml.p3.2xlarge` (GPU) | $3.06 | 8 min | ~$0.41 |
| `ml.p3.2xlarge` (Spot) | ~$0.30 | 8 min | ~$0.04 |

**Recommendation**: Start with `ml.m5.xlarge` for training. If it's too slow, switch to GPU.

## Instance Availability

Some instance types may not be available in all regions or may have capacity limits.

**Check availability**:
```python
import boto3
ec2_client = boto3.client('ec2', region_name='us-east-1')

# Check available instance types
response = ec2_client.describe_instance_type_offerings(
    LocationType='region',
    Filters=[
        {'Name': 'instance-type', 'Values': ['ml.p3.2xlarge']}
    ]
)
```

## Common Errors

### "Insufficient capacity"

**Solution**: Try a different instance type or region:
- Switch from `ml.p3.2xlarge` to `ml.p3.8xlarge` (sometimes more available)
- Or use `ml.m5.xlarge` (CPU, usually always available)

### "Instance type not supported"

**Solution**: Make sure you're using SageMaker instance types (start with `ml.`):
- ✅ `ml.m5.xlarge` (correct)
- ❌ `m5.xlarge` (missing `ml.` prefix)

## Quick Reference

**Training**:
- **Budget**: `ml.m5.xlarge` (CPU)
- **Speed**: `ml.p3.2xlarge` (GPU)
- **Best Value**: `ml.p3.2xlarge` with Spot

**Inference**:
- **Development**: `ml.t2.medium`
- **Production**: `ml.m5.large`
- **Serverless**: Scales to zero (good for spiky traffic)

---

**Bottom Line**: You can use any instance type that fits your needs and budget. Start with `ml.m5.xlarge` for training and `ml.m5.large` for inference, then adjust based on your requirements!
