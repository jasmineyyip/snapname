import sys

from snapname.config import ConfigError, load_settings
from snapname.watcher import run_observer


def main() -> None:
    try:
        settings = load_settings()
    except ConfigError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc

    print("ready", flush=True)
    print(f"screenshots: {settings.screenshots_dir}", flush=True)
    if not settings.anthropic_api_key:
        print(
            "warning: ANTHROPIC_API_KEY is not set; renames will fail until you add it to .env.",
            file=sys.stderr,
            flush=True,
        )
    try:
        print("watching (Ctrl+C to stop)…", flush=True)
        run_observer(settings)
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
