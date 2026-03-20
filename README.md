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

Run stays in the foreground: it prints `ready`, the resolved folder, then `watching…`. When a new image file appears there (create or move-in), it waits until the file size stops changing, then prints `detected: /full/path`. Stop with **Ctrl+C**.

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

## macOS screenshots

By default, macOS often saves captures to **Desktop** (`~/Desktop`). Snapname uses that path unless you set `SNAPNAME_SCREENSHOTS_DIR`.

## API key

Naming from image content uses the **Anthropic Messages API** (the image bytes are sent to the model). Set `ANTHROPIC_API_KEY` in `.env` for that path. Do not commit `.env`.

### Naming API (for scripts / next steps)

The package exposes helpers in `snapname.naming`:

- `describe_image_slug(settings, path)` — vision call → sanitized slug (no extension).
- `propose_new_path(settings, path)` — slug + prefix/suffix + collision handling → a **new** `Path` in the same folder with the same extension as `path` (the file is not renamed until you `path.rename(target)` yourself; wiring that into the watcher is the next step).

Both raise `NamingError` if the key is missing, the path is not a supported image, or the API errors.
