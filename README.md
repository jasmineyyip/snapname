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

Run stays in the foreground: it prints `ready`, the resolved folder, then `watching…`. When a **new macOS-style screenshot** appears (filename starts with `Screenshot` by default), it waits until the file size stops changing, asks the model for a short slug, then **renames** the file in place. It logs `renamed: /old/path -> /new/path` on success, or a message on **stderr** if the API key is missing, the API errors, or the rename fails. Stop with **Ctrl+C**.

Set `SNAPNAME_ONLY_SCREENSHOT_PREFIX=0` to rename **every** new image in the watched folder (not only `Screenshot*`), e.g. if your system uses a different naming pattern.

Supported extensions: `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.heic`, `.tiff`, `.tif`. Only the top level of the folder is watched (not subfolders).

## Configuration

Environment variables (optional unless noted). You can put them in a `.env` file in the repo root; copy `.env.example` to `.env`.

| Variable | Purpose |
|----------|---------|
| `SNAPNAME_SCREENSHOTS_DIR` | Folder to watch. Default: `~/Desktop`. Must exist. |
| `ANTHROPIC_API_KEY` | Anthropic API key. Required to compute a name from image content (e.g. once renaming is enabled). |
| `SNAPNAME_MODEL` | Vision model id. Default: `claude-sonnet-4-20250514`. |
| `SNAPNAME_FILENAME_PREFIX` | Optional string prepended to the generated slug (sanitized with the slug). |
| `SNAPNAME_FILENAME_SUFFIX` | Optional string appended before the file extension (sanitized with the slug). |
| `SNAPNAME_POLLING` | If `1` / `true` / `yes` / `on`, use a polling watcher instead of native FSEvents (higher CPU; useful if FSEvents fails). |
| `SNAPNAME_ONLY_SCREENSHOT_PREFIX` | Default `1`: only process files whose name starts with `Screenshot`. Set to `0` / `false` / `off` to process all new images in the folder. |

## macOS screenshots

By default, macOS often saves captures to **Desktop** (`~/Desktop`). Snapname uses that path unless you set `SNAPNAME_SCREENSHOTS_DIR`.

## API key

Naming from image content uses the **Anthropic Messages API** (the image bytes are sent to the model). Set `ANTHROPIC_API_KEY` in `.env` for that path. Do not commit `.env`.

### Naming API (for scripts)

The package exposes helpers in `snapname.naming`:

- `describe_image_slug(settings, path)` — vision call → sanitized slug (no extension).
- `propose_new_path(settings, path)` — slug + prefix/suffix + collision handling → target `Path` (same folder, same extension). The watcher calls this then `Path.rename`.

Both raise `NamingError` if the key is missing, the path is not a supported image, or the API errors.
