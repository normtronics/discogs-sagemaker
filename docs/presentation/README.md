# Presentation: Creating & Training the Album Classifier

Markdown slides for presenting the Discogs Sage ML pipeline — terminal workflow, SageMaker, and the Studio notebook.

## Slide Order

| # | File | Topic |
|---|------|-------|
| 1 | [01-title.md](./01-title.md) | Title & agenda |
| 2 | [02-project-overview.md](./02-project-overview.md) | What we're building |
| 3 | [03-terminal-explained.md](./03-terminal-explained.md) | Terminal / CLI role |
| 4 | [04-data-pipeline.md](./04-data-pipeline.md) | Discogs → images |
| 5 | [05-model-architecture.md](./05-model-architecture.md) | ResNet50 + transfer learning |
| 6 | [06-training-process.md](./06-training-process.md) | Training loop & hyperparameters |
| 7 | [07-what-is-sagemaker.md](./07-what-is-sagemaker.md) | SageMaker concepts |
| 8 | [08-sagemaker-training-flow.md](./08-sagemaker-training-flow.md) | Cloud training step-by-step |
| 9 | [09-inference-and-deployment.md](./09-inference-and-deployment.md) | Endpoints & inference handlers |
| 10 | [10-studio-notebook-walkthrough.md](./10-studio-notebook-walkthrough.md) | `studio_notebook.ipynb` |
| 11 | [11-end-to-end-diagram.md](./11-end-to-end-diagram.md) | Full system diagram |
| 12 | [12-glossary-and-summary.md](./12-glossary-and-summary.md) | Glossary & takeaways |

## How to Present

- Each `.md` file is one slide (or slide group). Use **Marp**, **Slidev**, **reveal.js**, or paste into Google Slides / Keynote.
- Mermaid diagrams render in GitHub, VS Code (with extension), and many slide tools.
- For a live demo, follow the checklist in slide 12.

## Quick Reference: Three Ways to Train

```
Local:     python backend/scripts/train.py --data-dir data --model-dir backend/models
Terminal:  python backend/scripts/run_sagemaker_training.py --bucket YOUR_BUCKET
Notebook:  notebooks/studio_notebook.ipynb (cells 4–6)
```
