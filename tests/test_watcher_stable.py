import time
from pathlib import Path

from snapname.watcher import wait_until_stable


def test_wait_until_stable_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "s.png"
    path.write_bytes(b"12345")
    assert wait_until_stable(path, stable_for=0.05, poll_interval=0.01, timeout=2.0) is True


def test_wait_until_stable_missing_file_times_out(tmp_path: Path) -> None:
    path = tmp_path / "missing.png"
    start = time.monotonic()
    ok = wait_until_stable(path, stable_for=0.05, poll_interval=0.02, timeout=0.15)
    elapsed = time.monotonic() - start
    assert ok is False
    assert elapsed >= 0.12
