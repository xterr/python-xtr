"""The data collector module exports the collector, the traced serializer and the call."""

from __future__ import annotations

from xtr_serializer import data_collector


def test_every_exported_name_resolves() -> None:
    assert [name for name in data_collector.__all__ if not hasattr(data_collector, name)] == []
