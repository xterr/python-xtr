"""A scope reads as the identifier it is named by."""

from __future__ import annotations

from tests.support.entities import make_scope


def test_a_scope_reads_as_its_identifier() -> None:
    assert str(make_scope("read")) == "read"
