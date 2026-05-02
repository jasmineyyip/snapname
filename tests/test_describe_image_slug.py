from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from snapname.config import Settings
from snapname.naming import NamingError, describe_image_slug, propose_new_path


def _settings(
    tmp_path: Path,
    *,
    anthropic_api_key: str | None = "test-key",
    vision_model: str = "claude-test",
    filename_prefix: str = "",
    filename_suffix: str = "",
    only_screenshot_prefix: bool = True,
) -> Settings:
    return Settings(
        anthropic_api_key=anthropic_api_key,
        vision_model=vision_model,
        screenshots_dir=tmp_path,
        filename_prefix=filename_prefix,
        filename_suffix=filename_suffix,
        only_screenshot_prefix=only_screenshot_prefix,
    )


def test_describe_image_slug_requires_api_key(tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"x")
    settings = _settings(tmp_path, anthropic_api_key=None)
    with pytest.raises(NamingError, match="ANTHROPIC_API_KEY"):
        describe_image_slug(settings, image)


def test_describe_image_slug_requires_file(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    missing = tmp_path / "nope.png"
    with pytest.raises(NamingError, match="Not a file"):
        describe_image_slug(settings, missing)


def test_describe_image_slug_requires_supported_image(tmp_path: Path) -> None:
    settings = _settings(tmp_path)
    bad = tmp_path / "x.txt"
    bad.write_text("hi")
    with pytest.raises(NamingError, match="supported image"):
        describe_image_slug(settings, bad)


def test_describe_image_slug_calls_api_and_sanitizes(tmp_path: Path) -> None:
    image = tmp_path / "a.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    settings = _settings(tmp_path)
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="  Hello World!!!  ")]
    )
    with patch("snapname.naming.anthropic.Anthropic") as MockAnthropic:
        instance = MockAnthropic.return_value
        instance.messages.create.return_value = fake_message
        slug = describe_image_slug(settings, image)
    assert slug == "hello-world"
    instance.messages.create.assert_called_once()
    call_kw = instance.messages.create.call_args.kwargs
    assert call_kw["model"] == "claude-test"


def test_propose_new_path_uses_slug_and_extension(tmp_path: Path) -> None:
    image = tmp_path / "Screenshot 2025.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    settings = _settings(tmp_path)
    fake_message = SimpleNamespace(
        content=[SimpleNamespace(type="text", text="my-test-slug")]
    )
    with patch("snapname.naming.anthropic.Anthropic") as MockAnthropic:
        MockAnthropic.return_value.messages.create.return_value = fake_message
        target = propose_new_path(settings, image)
    assert target.parent == tmp_path.resolve()
    assert target.suffix.lower() == ".png"
    assert target.name.startswith("my-test-slug")
    assert target != image.resolve()
