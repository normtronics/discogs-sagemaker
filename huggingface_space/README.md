---
title: Album Cover Recognition
emoji: 🎵
colorFrom: blue
colorTo: green
sdk: gradio
sdk_version: "4.0.0"
app_file: app.py
pinned: false
---

# Album Cover Recognition

Upload an album cover image to identify the release. Uses a ResNet50 model trained on Discogs data.

Set the `REPO_ID` secret to your Hugging Face model repo (e.g. `username/dsicogs-album-classifier`) in Space settings.
