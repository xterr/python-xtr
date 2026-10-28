from __future__ import annotations

from typing import TYPE_CHECKING

from tests.support import build_settings

if TYPE_CHECKING:
    from pathlib import Path


def test_the_values_fill_every_placeholder(tmp_path: Path) -> None:
    settings = build_settings(tmp_path / "web-shop")

    assert settings.values() == {
        "name": "web-shop",
        "app": "web_shop",
        "python": "3.13",
        "minor": "13",
    }
