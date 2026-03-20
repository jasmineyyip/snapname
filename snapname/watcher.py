from __future__ import annotations

import os
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import BaseObserver
from watchdog.observers.polling import PollingObserver

IMAGE_SUFFIXES = frozenset(
    {".png", ".jpg", ".jpeg", ".webp", ".gif", ".heic", ".tiff", ".tif"}
)


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in IMAGE_SUFFIXES


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
    def __init__(self, watch_root: Path) -> None:
        self._watch_root = watch_root.resolve()
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
            if wait_until_stable(path):
                print(f"detected: {path}", flush=True)
        finally:
            with self._lock:
                self._in_flight.discard(path)


def _observer() -> BaseObserver:
    flag = os.environ.get("SNAPNAME_POLLING", "").strip().lower()
    if flag in ("1", "true", "yes", "on"):
        return PollingObserver(timeout=1.0)
    return Observer()


def run_observer(watch_dir: Path) -> None:
    watch_dir = watch_dir.resolve()
    handler = _ScreenshotFolderHandler(watch_dir)
    observer = _observer()
    observer.schedule(handler, str(watch_dir), recursive=False)
    observer.start()
    try:
        while observer.is_alive():
            time.sleep(0.5)
    finally:
        observer.stop()
        observer.join(timeout=5)
