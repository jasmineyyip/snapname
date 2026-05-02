from pathlib import Path

from snapname.images import is_image_path


def test_is_image_path_recognizes_extensions() -> None:
    assert is_image_path(Path("x.PNG")) is True
    assert is_image_path(Path("shot.jpeg")) is True
    assert is_image_path(Path("a.webp")) is True


def test_is_image_path_rejects_non_images() -> None:
    assert is_image_path(Path("readme.txt")) is False
    assert is_image_path(Path("noext")) is False
