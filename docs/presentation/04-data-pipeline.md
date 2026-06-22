# Slide 4: Data Pipeline — From Discogs to Training Images

## Pipeline Stages

```mermaid
flowchart TD
    A[Discogs XML Dump<br/>discogs_releases.xml.gz] --> B[parser.py<br/>Extract N releases]
    B --> C[releases_manifest.jsonl<br/>title, artist, release_id]
    C --> D[enrich.py<br/>Discogs API]
    D --> E[releases_manifest_enriched.jsonl<br/>+ image URLs]
    E --> F[downloader.py<br/>Fetch cover art]
    F --> G[data/images/<br/>0.jpg, 1.jpg, ...]

    style A fill:#e8f4fd
    style G fill:#d4edda
```

## Manifest Format (JSONL)

One JSON object per line — each line is one **class** the model learns:

```json
{
  "release_id": "12345",
  "title": "Kind of Blue",
  "artists": ["Miles Davis"],
  "labels": ["Columbia"],
  "released": "1959",
  "image_url": "https://..."
}
```

## Entry Point: `build_data.py`

Single CLI that chains all steps:

| Flag | Purpose |
|------|---------|
| `--count 500` | How many releases to include |
| `--skip-download-dump` | Reuse existing XML file |
| `--skip-enrich` | Skip API step (no image URLs) |
| `--skip-download-images` | Parse only, no images |

## Why Enrichment Matters

The XML dump has metadata but **not always direct image URLs**. The enrich step calls the Discogs API to attach cover art links before download.

**Credential:** `DISCOGS_USER_TOKEN` in `backend/.env.local`
