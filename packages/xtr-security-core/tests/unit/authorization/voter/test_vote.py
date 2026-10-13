"""A vote records an answer and the reasons behind it."""

from __future__ import annotations

from xtr_security_core.authorization.voter import Access, Vote


def test_defaults() -> None:
    vote = Vote()

    assert vote.voter is None
    assert vote.result is Access.ABSTAIN
    assert vote.reasons == []
    assert vote.extra_data == {}
    assert vote.re_authentication_attribute is None


def test_add_reason_accumulates() -> None:
    vote = Vote()

    vote.add_reason("first")
    vote.add_reason("second")

    assert vote.reasons == ["first", "second"]


def test_request_re_authentication_records_the_attribute() -> None:
    vote = Vote()

    vote.request_re_authentication("IS_AUTHENTICATED_RECENTLY")

    assert vote.re_authentication_attribute == "IS_AUTHENTICATED_RECENTLY"
