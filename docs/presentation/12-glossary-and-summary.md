# Slide 12: Glossary & Summary

## Key Terms

| Term | Definition |
|------|------------|
| **Terminal / CLI** | Command-line interface on your machine; runs Python scripts and shell commands |
| **JSONL** | JSON Lines — one JSON record per line; our album catalog format |
| **Manifest** | List of releases (metadata + image paths) used for training labels |
| **Transfer learning** | Reuse a pre-trained model; fine-tune only the top layers |
| **ResNet50** | 50-layer residual network; our image classifier backbone |
| **SageMaker** | AWS managed ML platform for training and hosting models |
| **SageMaker Studio** | Web-based IDE with Jupyter notebooks |
| **Training Job** | One cloud run of `train.py` on a chosen instance type |
| **Estimator** | SDK class (`PyTorch`) that configures and launches training jobs |
| **Model artifact** | `model.tar.gz` containing weights + metadata |
| **Endpoint** | Live HTTPS service that runs inference on new images |
| **Execution role** | IAM role granting SageMaker access to S3 and other AWS services |
| **S3** | Amazon object storage; holds data, code, and trained models |
| **Hyperparameters** | Training settings: epochs, batch size, learning rate |

---

## Demo Checklist (Live Presentation)

```bash
# 1. Local data build (show terminal)
python backend/scripts/build_data.py --count 50

# 2. Show generated files
ls data/images/ | head
head -1 data/releases_manifest_enriched.jsonl

# 3. Upload to S3
./prepare_for_studio.sh your-bucket us-east-1

# 4. Open studio_notebook.ipynb in SageMaker Studio
#    → Run train cell → Run deploy cell → Test with image
```

---

## Takeaways

1. **One codebase** powers local dev and SageMaker — `ml/` is the core.
2. **Terminal** is for scripting and automation; **notebook** is for interactive cloud workflows.
3. **SageMaker** handles compute, containers, and deployment so you focus on `train.py` and `inference.py`.
4. **Data quality** (manifest + images) matters more than model tweaks for small catalogs.
5. **Always delete endpoints** when done to avoid ongoing AWS charges.

---

## Further Reading (in this repo)

| Doc | Topic |
|-----|-------|
| `docs/STUDIO_WALKTHROUGH.md` | Detailed Studio steps |
| `docs/SAGEMAKER_INTEGRATION.md` | Architecture + Lambda option |
| `docs/DATA_PREPARATION_WORKFLOW.md` | Processing jobs for data prep |
| `docs/backend.md` | Backend structure reference |
| `notebooks/studio_notebook.ipynb` | Runnable full pipeline |

---

## Questions?

**Project:** Album cover recognition from Discogs catalog  
**Model:** ResNet50 fine-tuned classifier  
**Cloud:** Amazon SageMaker (train + deploy)  
**Orchestration:** Terminal scripts + `studio_notebook.ipynb`
