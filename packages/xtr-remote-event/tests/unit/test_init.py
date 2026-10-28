"""The import package is importable, ships the marker that publishes its types, and exports them."""

from __future__ import annotations

from importlib.resources import files

import xtr_remote_event
from xtr_remote_event.event import mailer


def test_the_package_ships_its_typing_marker() -> None:
    assert files("xtr_remote_event").joinpath("py.typed").is_file()


def test_every_exported_name_resolves() -> None:
    assert [name for name in xtr_remote_event.__all__ if not hasattr(xtr_remote_event, name)] == []


def test_the_mailer_events_are_exported_from_the_package() -> None:
    assert [name for name in mailer.__all__ if name not in xtr_remote_event.__all__] == []
