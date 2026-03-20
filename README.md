# Snapname

This application watches your screenshots folder, sends each new capture to a vision model, and renames the file to a short slug based on what’s in the image.

## Requirements

- Python 3.11

## Setup

```bash
cd snapname
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m snapname
```

You should see `ready` and a line showing the resolved screenshots folder (default: `~/Desktop`).

## Configuration

Environment variables (optional unless noted). You can put them in a `.env` file in the repo root; copy `.env.example` to `.env`.

| Variable | Purpose |
|----------|---------|
| `SNAPNAME_SCREENSHOTS_DIR` | Folder to watch. Default: `~/Desktop`. Must exist. |
| `ANTHROPIC_API_KEY` | Anthropic API key (required once vision naming exists). |
| `SNAPNAME_MODEL` | Vision model id. Default: `claude-sonnet-4-20250514`. |
| `SNAPNAME_FILENAME_PREFIX` | Optional prefix for generated filenames (later). |
| `SNAPNAME_FILENAME_SUFFIX` | Optional suffix before the extension (later). |

## macOS screenshots

By default, macOS often saves captures to **Desktop** (`~/Desktop`). Snapname uses that path unless you set `SNAPNAME_SCREENSHOTS_DIR`.

## API key

Vision-based naming will call the Anthropic API. Set `ANTHROPIC_API_KEY` in `.env` before using that feature. Do not commit `.env`.
