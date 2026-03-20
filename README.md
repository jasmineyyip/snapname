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

You should see: `ready`

## macOS screenshots

By default, macOS often saves captures to **Desktop** (`~/Desktop`). This project will use that path unless you override it in configuration (added later).

## API key

Vision-based naming will call the Anthropic API. When that lands, copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. Do not commit `.env`.
