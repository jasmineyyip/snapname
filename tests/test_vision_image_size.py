"""Tests for shrinking oversized screenshots before calling Anthropic."""

import base64
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from PIL import Image

from snapname.config import Settings
from snapname import naming
from snapname.naming import NamingError, describe_image_slug


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        anthropic_api_key="k",
        vision_model="claude-test",
        screenshots_dir=tmp_path,
        filename_prefix="",
        filename_suffix="",
        only_screenshot_prefix=True,
    )


def test_oversize_png_is_reencoded_as_jpeg_under_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(naming, "ANTHROPIC_IMAGE_MAX_RAW_BYTES", 25_000)

    pixels = bytes((i * 17 + j * 31) % 256 for i in range(280) for j in range(280) for _ in range(3))
    img = Image.frombytes("RGB", (280, 280), pixels)
    buf = Path(tmp_path / "big.png")
    img.save(buf, format="PNG", compress_level=0)
    assert buf.stat().st_size > 25_000

    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="slug-from-model")]
    )
    with patch("snapname.naming.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = fake_message
        slug = describe_image_slug(_settings(tmp_path), buf)

    assert slug == "slug-from-model"
    call_kw = instance.messages.create.call_args.kwargs
    block = call_kw["messages"][0]["content"][0]
    assert block["type"] == "image"
    assert block["source"]["media_type"] == "image/jpeg"
    decoded = base64.standard_b64decode(block["source"]["data"])
    assert len(decoded) <= naming.ANTHROPIC_IMAGE_MAX_RAW_BYTES


def test_oversize_non_image_bytes_raises(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(naming, "ANTHROPIC_IMAGE_MAX_RAW_BYTES", 100)
    p = tmp_path / "x.png"
    p.write_bytes(b"not-a-real-png-" + b"z" * 500)
    with pytest.raises(NamingError, match="could not be read"):
        describe_image_slug(_settings(tmp_path), p)
