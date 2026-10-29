"""The import package ships the marker that publishes its types, and exports what it lists."""

from __future__ import annotations

from importlib.resources import files

import xtr_serializer


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_serializer").joinpath("py.typed").is_file()


def test_every_name_it_lists_is_exported() -> None:
    missing = [name for name in xtr_serializer.__all__ if not hasattr(xtr_serializer, name)]

    assert missing == []
