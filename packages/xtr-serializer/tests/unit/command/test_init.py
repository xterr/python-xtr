"""The command module exports the console commands."""

from __future__ import annotations

from xtr_serializer import command


def test_every_exported_name_resolves() -> None:
    assert [name for name in command.__all__ if not hasattr(command, name)] == []
