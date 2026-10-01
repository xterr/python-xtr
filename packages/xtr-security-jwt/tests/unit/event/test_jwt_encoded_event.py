"""The encoded event reports the signed token string."""

from __future__ import annotations

from xtr_event_dispatcher_contracts import Event

from xtr_security_jwt.event.jwt_encoded_event import JwtEncodedEvent


def test_it_is_a_dispatcher_event() -> None:
    assert Event in JwtEncodedEvent.__mro__


def test_it_reports_the_token() -> None:
    assert JwtEncodedEvent("a.b.c").get_jwt_string() == "a.b.c"
