# Snapname

Snapname watches a folder (by default **your Desktop**). When a new screenshot appears, it sends the image to an Anthropic vision model, gets back a short descriptive slug, and **renames the file in place**.

---

## Prerequisites

- **Python 3.11 or newer** (`python3 --version`)
- An **[Anthropic API key](https://console.anthropic.com/)** — stored locally in `.env`, never committed
- **macOS** is the typical setup (screenshots land on Desktop by default). Other platforms work if you point `SNAPNAME_SCREENSHOTS_DIR` at an existing folder.

---

## How to start

Work from the **repository root** — the directory that contains `snapname/` and `pyproject.toml`.

```bash
git clone https://github.com/jasmineyyip/snapname.git
cd snapname

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Make sure in .env, set ANTHROPIC_API_KEY=...

python -m snapname
```

Run `source .venv/bin/activate` and `python` should work inside that shell.

You should see **`ready`**, the resolved watch folder, then **`watching…`**. Leave this terminal open while you use Snapname. You can terminate it with **Ctrl+C**.

---

## What happens while it runs

1. Snapname watches **only the top level** of the configured folder.
2. By default it only reacts to files whose name starts with **`Screenshot`** (macOS naming). To rename **every** new image in that folder, set `SNAPNAME_ONLY_SCREENSHOT_PREFIX=0` (see the table below).
3. When a matching image appears, Snapname waits until the file size stabilizes, calls the model, then renames it.
4. If it succeed, it prints: `renamed: /old/path -> /new/path`. Problems such as missing key, API errors, and rename failures will go to **stderr**.

**Supported extensions:** `.png`, `.jpg`, `.jpeg`, `.webp`, `.gif`, `.heic`, `.tiff`, `.tif`.

---

## Run in the background (macOS Launch Agent)

Use a **Launch Agent** so Snapname starts at login without keeping a terminal open.

1. From the repo root: venv created, `pip install -e .` (or at least `pip install -r requirements.txt`), and **`.env`** with your key. Snapname loads `.env` from the repo root (next to `pyproject.toml`).
2. Copy `launchd/com.snapname.watcher.example.plist` to `~/Library/LaunchAgents/com.snapname.watcher.plist`.
3. Edit the plist: replace **every** `/ABSOLUTE/PATH/TO/snapname-repo` with your **real** absolute path to the clone (folder that contains `.venv` and `snapname/`).
4. Load the agent (after edits, **bootout** first if you loaded an older version):

   ```bash
   launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.snapname.watcher.plist
   ```

5. Logs: `.snapname-launchd.out.log` and `.snapname-launchd.err.log` in the repo root (gitignored).

**Stop / uninstall:** `launchctl bootout "gui/$(id -u)" ~/Library/LaunchAgents/com.snapname.watcher.plist`, then delete the plist from `LaunchAgents` if you want it gone.

---

## Configuration

Copy `.env.example` to `.env` in the repo root. Do **not** commit `.env`.

Naming uses the **Anthropic Messages API** (image bytes are sent to the model).

| Variable | Purpose |
|----------|---------|
| `SNAPNAME_SCREENSHOTS_DIR` | Folder to watch. Default: `~/Desktop`. Must exist. |
| `ANTHROPIC_API_KEY` | Required for renaming from image content. |
| `SNAPNAME_MODEL` | Vision model id. Default: `claude-sonnet-4-20250514`. |
| `SNAPNAME_FILENAME_PREFIX` | Optional string before the slug (sanitized). |
| `SNAPNAME_FILENAME_SUFFIX` | Optional string after the slug, before the extension (sanitized). |
| `SNAPNAME_POLLING` | `1` / `true` / `yes` / `on` → polling watcher (more CPU; useful if native events misbehave). |
| `SNAPNAME_ONLY_SCREENSHOT_PREFIX` | Default on: only files whose name starts with `Screenshot`. Set `0` / `false` / `off` for all new images in the folder. |