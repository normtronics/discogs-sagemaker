# Slide 11: End-to-End — How Everything Works Together

## The Complete System

```mermaid
flowchart TB
    subgraph Sources["Data Sources"]
        XML[Discogs XML Dump]
        API[Discogs API<br/>cover image URLs]
    end

    subgraph Local["Local Machine — Terminal"]
        BD[build_data.py]
        PT[prepare_for_studio.sh]
        LT[train.py local<br/>optional]
        RS[run_sagemaker_training.py<br/>optional]
    end

    subgraph Studio["SageMaker Studio"]
        NB[studio_notebook.ipynb]
    end

    subgraph AWS["AWS Cloud"]
        S3[(S3 Bucket<br/>data + code + models)]
        TJ[SageMaker<br/>Training Job]
        EP[SageMaker<br/>Endpoint]
        LAM[Lambda + API Gateway<br/>optional]
    end

    subgraph Code["Shared Python Code"]
        ML[backend/ml/<br/>dataset · model · train · inference]
        DATA[backend/data/<br/>parser · enrich · downloader]
    end

    XML --> BD
    API --> BD
    BD --> S3
    PT --> S3
    RS --> S3
    RS --> TJ
    NB --> BD
    NB --> PT
    NB --> TJ
    NB --> EP

    S3 --> TJ
    TJ --> S3
    S3 --> EP

    ML --> BD
    ML --> LT
    ML --> TJ
    ML --> EP
    DATA --> BD

    EP --> LAM
    LAM --> FE[Frontend / Hugging Face Space]

    LT -.->|dev only| LT
```

---

## Three Entry Paths, One Codebase

```mermaid
flowchart LR
    subgraph Path1["Path A: Fully Local"]
        A1[Terminal: build_data] --> A2[Terminal: train.py]
        A2 --> A3[Terminal: main.py FastAPI]
    end

    subgraph Path2["Path B: Terminal → Cloud"]
        B1[Terminal: build_data] --> B2[Terminal: prepare_for_studio]
        B2 --> B3[Terminal: run_sagemaker_training]
        B3 --> B4[Notebook or Console: deploy]
    end

    subgraph Path3["Path C: All in Studio"]
        C1[Notebook: build_data cell] --> C2[Notebook: upload cell]
        C2 --> C3[Notebook: train cell]
        C3 --> C4[Notebook: deploy + test]
    end
```

---

## File → Responsibility Map

| File / Folder | Responsibility |
|---------------|----------------|
| `backend/scripts/build_data.py` | CLI: full data pipeline |
| `backend/ml/model.py` | ResNet50 architecture |
| `backend/ml/dataset.py` | Load manifest, augment images |
| `backend/ml/train.py` | Training loop (local + SageMaker) |
| `backend/ml/inference.py` | SageMaker inference handlers |
| `backend/train.py` | Thin SageMaker entry → `ml.train` |
| `backend/inference.py` | Thin SageMaker entry → `ml.inference` |
| `prepare_for_studio.sh` | Package + upload to S3 |
| `run_sagemaker_training.py` | Upload + launch training job |
| `notebooks/studio_notebook.ipynb` | Interactive full pipeline |
| `infrastructure/` | CDK: Lambda, API Gateway, stacks |

---

## Data Flow Summary

1. **Discogs** → manifest JSONL + JPEG images
2. **S3** → durable storage for cloud training
3. **Training Job** → reads S3, writes `model.tar.gz`
4. **Endpoint** → loads model, serves predictions
5. **Frontend** → sends album photo, displays top matches
