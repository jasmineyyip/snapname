import sys

from snapname.config import ConfigError, load_settings


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    print("ready")
    print(f"screenshots: {settings.screenshots_dir}")


if __name__ == "__main__":
    main()
