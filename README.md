# Wan2GP Pinokio Launcher

Pinokio launcher scripts for [deepbeepmeep/Wan2GP](https://github.com/deepbeepmeep/Wan2GP), focused on running optimized AI video generation workflows on NVIDIA GPUs with lower VRAM.

## What this repository contains

- Pinokio app metadata (`pinokio.js`, `pinokio_meta.json`).
- Install/start/update/reset scripts for the bundled app (`install.js`, `start.js`, `update.js`, `reset.js`).
- Optional helper flows (`deepy.js`, `torch.js`).
- A simple static profile page (`index.html`).

## Requirements

- Pinokio runtime
- NVIDIA GPU (AMD + macOS are explicitly blocked by installer logic)
- Python environment managed by Pinokio (`venv: env`)

## Quick start

1. Open this repository in Pinokio.
2. Run **Install**.
3. After installation, run **Start**.
4. Open the generated local web UI URL.

## Script overview

- `install.js`: clones Wan2GP and installs dependencies (including Torch-related wheels via `torch.js`).
- `start.js`: starts `wgp.py` and exposes the local URL in Pinokio.
- `update.js`: pulls both launcher and upstream app updates, then refreshes dependencies.
- `reset.js`: removes the local `app` folder to restore pre-install state.
- `deepy.js`: enables and launches Deepy assistant mode.

## GitHub readiness checklist

Current state:

- ✅ Has a concise README and clear project purpose.
- ✅ Contains focused launcher scripts with separated responsibilities.
- ✅ MIT `LICENSE` included.
- ✅ GitHub Actions CI syntax check included.
- ✅ Issue templates and PR template included.
- ✅ `CODEOWNERS` file included for default review ownership.
- ✅ `SECURITY.md` added for responsible vulnerability reporting.

If you plan to publish broadly, the next optional step is release notes automation.
