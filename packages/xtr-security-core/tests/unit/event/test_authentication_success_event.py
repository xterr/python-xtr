"""The success event announces the token authentication settled on."""

from __future__ import annotations

from xtr_security_core.authentication.token import NullToken
from xtr_security_core.event import AuthenticationEvent, AuthenticationSuccessEvent


def test_it_extends_the_authentication_event() -> None:
    assert issubclass(AuthenticationSuccessEvent, AuthenticationEvent)


def test_it_reads_the_inherited_token() -> None:
    token = NullToken()
    event = AuthenticationSuccessEvent(token)

    assert event.get_authentication_token() is token
    assert event.is_propagation_stopped() is False
