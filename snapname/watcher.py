from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.observers.polling import PollingObserver

from snapname.config import Settings
from snapname.images import is_image_path
from snapname.naming import NamingError, propose_new_path


def wait_until_stable(
    path: Path,
    *,
    stable_for: float = 0.25,
    poll_interval: float = 0.05,
    timeout: float = 60.0,
) -> bool:
    """Wait until ``path`` exists, is a file, and its size is unchanged for ``stable_for`` seconds."""
    deadline = time.monotonic() + timeout
    prev_size: int | None = None
    stable_start: float | None = None

    while time.monotonic() < deadline:
        try:
            if not path.is_file():
                prev_size = None
                stable_start = None
                time.sleep(poll_interval)
                continue
            size = path.stat().st_size
        except OSError:
            prev_size = None
            stable_start = None
            time.sleep(poll_interval)
            continue

        if size != prev_size:
            prev_size = size
            stable_start = None
        elif size == 0:
            stable_start = None
        else:
            now = time.monotonic()
            if stable_start is None:
                stable_start = now
            elif now - stable_start >= stable_for:
                return True

        time.sleep(poll_interval)

    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


class _ScreenshotFolderHandler(FileSystemEventHandler):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._watch_root = settings.screenshots_dir.resolve()
        self._lock = threading.Lock()
        self._in_flight: set[Path] = set()

    def on_created(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        self._enqueue(Path(event.src_path))

    def on_moved(self, event: object) -> None:
        if getattr(event, "is_directory", False):
            return
        dest = getattr(event, "dest_path", None)
        if dest:
            self._enqueue(Path(dest))

    def _enqueue(self, path: Path) -> None:
        try:
            path = path.resolve()
            path.relative_to(self._watch_root)
        except (OSError, ValueError):
            return
        if not is_image_path(path):
            return
        if self._settings.only_screenshot_prefix and not path.name.startswith("Screenshot"):
            return

        with self._lock:
            if path in self._in_flight:
                return
            self._in_flight.add(path)

        thread = threading.Thread(
            target=self._process,
            args=(path,),
            name=f"snapname-stable:{path.name}",
            daemon=True,
        )
        thread.start()

    def _process(self, path: Path) -> None:
        try:
            if not wait_until_stable(path):
                return
            if not path.is_file():
                return
            if self._settings.only_screenshot_prefix and not path.name.startswith("Screenshot"):
                return
            src = path
            target = propose_new_path(self._settings, src)
            if target.resolve() == src.resolve():
                return
            src.rename(target)
            print(f"renamed: {src} -> {target}", flush=True)
        except NamingError as exc:
            print(f"snapname: {path}: {exc}", file=sys.stderr, flush=True)
        except OSError as exc:
            print(f"snapname: {path}: {exc}", file=sys.stderr, flush=True)
        finally:
            with self._lock:
                self._in_flight.discard(path)


def _observer() -> BaseObserver:
    flag = os.environ.get("SNAPNAME_POLLING", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return PollingObserver(timeout=1.0)
    return Observer()


def run_observer(settings: Settings) -> None:
    watch_dir = settings.screenshots_dir.resolve()
    handler = _ScreenshotFolderHandler(settings)
    observer = _observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    try:
        while observer.is_alive():
            time.sleep(0.5)
    finally:
        observer.stop()
        observer.join(timeout=5)
