from __future__ import annotations

import base64
import re
from pathlib import Path

import anthropic

from snapname.config import Settings
from snapname.images import is_image_path

MAX_SLUG_LENGTH = 80
MAX_BASENAME_LENGTH = 120

MEDIA_TYPE_BY_SUFFIX: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".heic": "image/heic",
    ".tiff": "image/tiff",
    ".tif": "image/tiff",
}

VISION_PROMPT = """You name screenshot files for a local folder.

Reply with ONE LINE only: a short slug in English — lowercase words separated by single ASCII hyphens.
- Describe the main subject only (e.g. ide-code-editor, safari-wikipedia-article, slack-channel-list).
- Use letters a–z and digits 0–9 only between hyphens (no spaces, dots, slashes, quotes, or emoji).
- No paths, file extensions, personal names, email addresses, phone numbers, or other sensitive details.
- At most 6 hyphen-separated words; keep it under 50 characters if you can.
"""


class NamingError(Exception):
    pass


def media_type_for_path(path: Path) -> str:
    mt = MEDIA_TYPE_BY_SUFFIX.get(path.suffix.lower())
    if not mt:
        raise NamingError(f"Unsupported image type: {path.suffix}")
    return mt


def extract_slug_raw(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    line = text.splitlines()[0].strip() if text else ""
    return line.strip("\"'").strip()


def sanitize_slug(s: str, max_len: int = MAX_SLUG_LENGTH) -> str:
    s = s.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-")
    if not s:
        s = "screenshot"
    if len(s) > max_len:
        s = s[:max_len].rstrip("-")
    return s


def _response_text(message: object) -> str:
    parts: list[str] = []
    for block in message.content:
        if block.type == "text":
            parts.append(block.text)
    return "\n".join(parts).strip()


def describe_image_slug(settings: Settings, path: Path) -> str:
    if not settings.anthropic_api_key:
        raise NamingError("ANTHROPIC_API_KEY is not set.")
    if not path.is_file():
        raise NamingError(f"Not a file: {path}")
    if not is_image_path(path):
        raise NamingError(f"Not a supported image path: {path}")

    media_type = media_type_for_path(path)
    raw_bytes = path.read_bytes()
    b64 = base64.standard_b64encode(raw_bytes).decode("ascii")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    try:
        message = client.messages.create(
            model=settings.vision_model,
            max_tokens=150,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIError as exc:
        raise NamingError(f"Anthropic API error: {exc}") from exc

    raw = _response_text(message)
    if not raw:
        return "screenshot"
    return sanitize_slug(extract_slug_raw(raw))


def build_basename(settings: Settings, slug: str) -> str:
    prefix = (settings.filename_prefix or "").strip()
    suffix = (settings.filename_suffix or "").strip()
    for part in (prefix, suffix):
        if not part:
            continue
        if "/" in part or "\\" in part or part in {".", ".."}:
            raise NamingError("filename prefix/suffix must not contain path separators.")
    combined = f"{prefix}{slug}{suffix}"
    return sanitize_slug(combined, max_len=MAX_BASENAME_LENGTH)


def _path_occupied(path: Path, skip: Path | None) -> bool:
    try:
        if not path.exists():
            return False
        if skip is not None and path.resolve() == skip.resolve():
            return False
        return True
    except OSError:
        return True


def unique_destination(
    directory: Path,
    basename_without_ext: str,
    extension: str,
    *,
    skip: Path | None = None,
) -> Path:
    ext = extension if extension.startswith(".") else f".{extension}"
    candidate = (directory / f"{basename_without_ext}{ext}").resolve()
    if not _path_occupied(candidate, skip):
        return candidate
    n = 2
    while n < 10_000:
        stem = f"{basename_without_ext}-{n}"
        candidate = (directory / f"{stem}{ext}").resolve()
        if not _path_occupied(candidate, skip):
            return candidate
        n += 1
    raise NamingError("Could not find a free filename (too many collisions).")


def propose_new_path(settings: Settings, source: Path) -> Path:
    """Return a non-existing path in ``source``'s directory with the same extension."""
    source = source.resolve()
    slug = describe_image_slug(settings, source)
    basename = build_basename(settings, slug)
    return unique_destination(
        source.parent,
        basename,
        source.suffix,
        skip=source,
    )
