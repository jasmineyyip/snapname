from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    anthropic_api_key: str | None
    vision_model: str
    screenshots_dir: Path
    filename_prefix: str
    filename_suffix: str


class ConfigError(Exception):
    pass


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _load_dotenv_files() -> None:
    load_dotenv(_repo_root() / ".env")
    load_dotenv(Path.cwd() / ".env", override=True)


def load_settings() -> Settings:
    _load_dotenv_files()

    key_raw = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    model = os.environ.get("SNAPNAME_MODEL", "claude-sonnet-4-20250514").strip()
    raw_dir = os.environ.get("SNAPNAME_SCREENSHOTS_DIR", "").strip()
    prefix = os.environ.get("SNAPNAME_FILENAME_PREFIX", "").strip()
    suffix = os.environ.get("SNAPNAME_FILENAME_SUFFIX", "").strip()

    if raw_dir:
        screenshots = Path(raw_dir).expanduser().resolve()
    else:
        screenshots = (Path.home() / "Desktop").resolve()

    if not screenshots.is_dir():
        raise ConfigError(
            "Screenshots folder does not exist or is not a directory:\n"
            f"  {screenshots}\n"
            "Set SNAPNAME_SCREENSHOTS_DIR to an existing folder, or create Desktop."
        )

    return Settings(
        anthropic_api_key=key_raw or None,
        vision_model=model,
        screenshots_dir=screenshots,
        filename_prefix=prefix,
        filename_suffix=suffix,
    )
