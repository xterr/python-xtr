"""The import package is importable and ships the marker that publishes its types."""

from __future__ import annotations

from importlib.resources import files


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_notifier").joinpath("py.typed").is_file()
