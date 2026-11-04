"""Fixtures shared by the transport tests."""

from __future__ import annotations

import pytest


def _first(upper: int) -> int:
    del upper
    return 0


@pytest.fixture
def first_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Give a round-robin transport's first turn to its first transport, not a random one."""
    monkeypatch.setattr("xtr_mailer.transport.round_robin_transport.randbelow", _first)
