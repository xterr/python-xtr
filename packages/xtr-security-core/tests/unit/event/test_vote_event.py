"""A vote event carries a voter's answer for tracing."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_security_core.authorization.voter import Access, RoleVoter
from xtr_security_core.event import VoteEvent


def test_carries_its_fields() -> None:
    voter = RoleVoter()
    event = VoteEvent(
        voter=voter,
        subject="book",
        attributes=("ROLE_ADMIN",),
        vote=Access.DENIED,
        reasons=("no role",),
    )

    assert event.voter is voter
    assert event.subject == "book"
    assert event.attributes == ("ROLE_ADMIN",)
    assert event.vote is Access.DENIED
    assert event.reasons == ("no role",)


def test_reasons_default_to_empty() -> None:
    event = VoteEvent(voter=RoleVoter(), subject=None, attributes=(), vote=Access.ABSTAIN)

    assert event.reasons == ()


def test_is_an_event() -> None:
    assert issubclass(VoteEvent, Event)
