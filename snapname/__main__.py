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
    print("watching (Ctrl+C to stop)…", flush=True)
    try:
        run_observer(settings.screenshots_dir)
    except KeyboardInterrupt:
        print("\nstopped", flush=True)


if __name__ == "__main__":
    main()
