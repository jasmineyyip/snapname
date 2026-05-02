from pathlib import Path

import pytest

from snapname.config import Settings
from snapname.naming import (
    NamingError,
    build_basename,
    extract_slug_raw,
    media_type_for_path,
    sanitize_slug,
    unique_destination,
)


def test_extract_slug_raw_plain() -> None:
    assert extract_slug_raw("  hello-world  ") == "hello-world"


def test_extract_slug_raw_fenced_block() -> None:
    raw = "```\nmy-slug-here\n```"
    assert extract_slug_raw(raw) == "my-slug-here"


def test_extract_slug_raw_first_line_only() -> None:
    assert extract_slug_raw("first-line\nignored") == "first-line"


def test_sanitize_slug_normalizes_and_truncates() -> None:
    assert sanitize_slug("Foo  BAR!!!") == "foo-bar"
    assert sanitize_slug("") == "screenshot"
    assert sanitize_slug("a" * 100, max_len=10) == "aaaaaaaaaa"


def test_media_type_for_path_png() -> None:
    assert media_type_for_path(Path("x.png")) == "image/png"


def test_media_type_for_path_unsupported() -> None:
    with pytest.raises(NamingError, match="Unsupported"):
        media_type_for_path(Path("x.bmp"))


def test_build_basename_prefix_suffix() -> None:
    settings = Settings(
        anthropic_api_key="x",
        vision_model="m",
        screenshots_dir=Path("/tmp"),
        filename_prefix="pre-",
        filename_suffix="-suf",
        only_screenshot_prefix=True,
    )
    assert build_basename(settings, "slug") == "pre-slug-suf"


def test_build_basename_rejects_path_separators_in_affixes() -> None:
    settings = Settings(
        anthropic_api_key="x",
        vision_model="m",
        screenshots_dir=Path("/tmp"),
        filename_prefix="bad/name",
        filename_suffix="",
        only_screenshot_prefix=True,
    )
    with pytest.raises(NamingError, match="prefix/suffix"):
        build_basename(settings, "slug")


def test_unique_destination_no_collision(tmp_path: Path) -> None:
    dest = unique_destination(tmp_path, "foo", ".png")
    assert dest == tmp_path / "foo.png"


def test_unique_destination_skips_existing_source(tmp_path: Path) -> None:
    existing = tmp_path / "foo.png"
    existing.write_bytes(b"\x89PNG\r\n\x1a\n")
    dest = unique_destination(tmp_path, "foo", ".png", skip=existing)
    assert dest == existing.resolve()


def test_unique_destination_collision_adds_suffix(tmp_path: Path) -> None:
    (tmp_path / "foo.png").write_bytes(b"a")
    dest = unique_destination(tmp_path, "foo", ".png")
    assert dest.name == "foo-2.png"
