"""A vote records an answer and the reasons behind it."""

from __future__ import annotations

from xtr_security_core.authorization.voter import Access, Vote


def test_defaults() -> None:
    vote = Vote()

    assert vote.voter is None
    assert vote.result is Access.ABSTAIN
    assert vote.reasons == []
    assert vote.extra_data == {}


def test_add_reason_accumulates() -> None:
    vote = Vote()

    vote.add_reason("first")
    vote.add_reason("second")

    assert vote.reasons == ["first", "second"]
