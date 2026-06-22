# Slide 2: What Are We Building?

## The Problem

Given a photo of an album cover, identify which release in our catalog it belongs to — with confidence scores for the top matches.

## The Solution

A **multi-class image classifier** trained on Discogs album cover images.

| Component | Technology |
|-----------|------------|
| Data source | Discogs XML dump + API |
| Model | ResNet50 (transfer learning) |
| Framework | PyTorch |
| Local dev | Terminal scripts + FastAPI |
| Cloud training | Amazon SageMaker |
| Orchestration | Jupyter notebook in SageMaker Studio |

## One Codebase, Two Environments

The same Python modules run **locally on your laptop** and **remotely on SageMaker** — no duplicate training logic.

```
backend/
├── ml/          ← shared: dataset, model, train, inference
├── data/        ← shared: parser, enrich, downloader
├── train.py     ← SageMaker entry point → ml.train
└── inference.py ← SageMaker entry point → ml.inference
```
