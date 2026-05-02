from __future__ import annotations

import base64
import math
import re
import sys
from io import BytesIO
from pathlib import Path

import anthropic
from PIL import Image, ImageOps

from snapname.config import Settings
from snapname.images import is_image_path

MAX_SLUG_LENGTH = 80
MAX_BASENAME_LENGTH = 120

# Anthropic caps base64 image payloads at 5 MiB decoded size.
ANTHROPIC_IMAGE_MAX_RAW_BYTES = 5 * 1024 * 1024

# The API also rejects large decoded rasters (errors match width×height×4-byte buffers).
ANTHROPIC_MAX_PIXELS_RGBA = max(1, ANTHROPIC_IMAGE_MAX_RAW_BYTES // 4 - 512)


def _anthropic_target_raw_bytes() -> int:
    cap = ANTHROPIC_IMAGE_MAX_RAW_BYTES
    headroom = min(256 * 1024, max(cap // 8, 4096))
    return max(4096, cap - headroom)

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


def _image_to_rgb_for_jpeg(img: Image.Image) -> Image.Image:
    if img.mode == "P":
        img = img.convert("RGBA")
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        return bg
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _encode_jpeg(img: Image.Image, *, quality: int) -> bytes:
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def _limit_raster_for_api(rgb: Image.Image) -> Image.Image:
    """Scale down so width×height×4 fits Anthropic's ~5 MiB raster limit."""
    w, h = rgb.size
    if w * h <= ANTHROPIC_MAX_PIXELS_RGBA:
        return rgb
    scale = math.sqrt(ANTHROPIC_MAX_PIXELS_RGBA / (w * h)) * 0.995
    nw = max(1, int(w * scale))
    nh = max(1, int(h * scale))
    while nw * nh > ANTHROPIC_MAX_PIXELS_RGBA and (nw > 1 or nh > 1):
        if nw >= nh and nw > 1:
            nw -= 1
        elif nh > 1:
            nh -= 1
        else:
            break
    return rgb.resize((nw, nh), Image.Resampling.LANCZOS)


def _image_exceeds_api_raster_cap(raw: bytes) -> bool:
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except OSError:
        return False
    img = ImageOps.exif_transpose(img)
    return img.width * img.height > ANTHROPIC_MAX_PIXELS_RGBA


def _shrink_for_anthropic_vision(raw: bytes) -> tuple[bytes, str]:
    """Return JPEG bytes under Anthropic's decoded 5 MiB cap (may downscale aggressively)."""
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except OSError as exc:
        raise NamingError(
            "Screenshot is larger than 5 MB (Anthropic limit) and could not be read as an image. "
            f"Details: {exc}"
        ) from exc

    img = ImageOps.exif_transpose(img)
    rgb = _limit_raster_for_api(_image_to_rgb_for_jpeg(img))

    quality = 88
    scale = 1.0
    target = _anthropic_target_raw_bytes()

    for _ in range(96):
        w = max(1, int(rgb.width * scale))
        h = max(1, int(rgb.height * scale))
        work = rgb if (w, h) == (rgb.width, rgb.height) else rgb.resize(
            (w, h), Image.Resampling.LANCZOS
        )
        q = max(28, min(quality, 95))
        data = _encode_jpeg(work, quality=q)
        if len(data) <= target:
            return data, "image/jpeg"
        if len(data) <= ANTHROPIC_IMAGE_MAX_RAW_BYTES:
            return data, "image/jpeg"

        if quality > 42:
            quality -= 5
        else:
            scale *= 0.72
            quality = min(quality + 10, 88)

        if w <= 64 and h <= 64 and quality <= 30:
            break

    raise NamingError(
        "Could not shrink screenshot enough to stay under Anthropic's 5 MB image limit."
    )


def _bytes_for_vision_api(raw: bytes, media_type: str) -> tuple[bytes, str]:
    if len(raw) <= ANTHROPIC_IMAGE_MAX_RAW_BYTES and not _image_exceeds_api_raster_cap(
        raw
    ):
        return raw, media_type
    return _shrink_for_anthropic_vision(raw)


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
    if len(raw_bytes) > ANTHROPIC_IMAGE_MAX_RAW_BYTES:
        print(
            f"snapname: compressing {len(raw_bytes)}-byte image for API (5 MiB limit)…",
            file=sys.stderr,
            flush=True,
        )
    payload_bytes, payload_media_type = _bytes_for_vision_api(raw_bytes, media_type)
    if len(payload_bytes) > ANTHROPIC_IMAGE_MAX_RAW_BYTES:
        payload_bytes, payload_media_type = _shrink_for_anthropic_vision(raw_bytes)
    if len(payload_bytes) > ANTHROPIC_IMAGE_MAX_RAW_BYTES:
        raise NamingError(
            f"Refusing API call: image payload is still {len(payload_bytes)} bytes (> 5 MiB). "
            f"This build should shrink large screenshots; loaded naming.py from {__file__}. "
            "Re-run from the repo you edited with `pip install -e .` and use this venv's python."
        )
    b64 = base64.standard_b64encode(payload_bytes).decode("ascii")

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
                                "media_type": payload_media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": VISION_PROMPT},
                    ],
                }
            ],
        )
    except anthropic.APIError as exc:
        err_text = str(exc)
        if "exceeds 5 MB" in err_text or "5242880" in err_text:
            raise NamingError(
                f"Anthropic API error: {exc}\n"
                "If this persists after upgrading snapname, report it with screenshot dimensions "
                f"and snapname version; naming.py: {__file__}"
            ) from exc
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
