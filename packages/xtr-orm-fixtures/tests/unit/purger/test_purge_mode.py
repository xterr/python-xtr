"""Unit tests for :class:`xtr_orm_fixtures.purger.PurgeMode`."""

from __future__ import annotations

from xtr_orm_fixtures.purger import PurgeMode


def test_modes_keep_their_numbers() -> None:
    assert [(mode.name, mode.value) for mode in PurgeMode] == [("DELETE", 1), ("TRUNCATE", 2)]
