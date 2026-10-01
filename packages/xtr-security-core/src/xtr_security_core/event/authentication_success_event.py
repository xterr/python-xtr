"""The event announcing that authentication settled on a token."""

from __future__ import annotations

from dataclasses import dataclass

from .authentication_event import AuthenticationEvent

__all__ = ["AuthenticationSuccessEvent"]


@dataclass(frozen=True)
class AuthenticationSuccessEvent(AuthenticationEvent):
    """Announces that authentication succeeded and settled on a token.

    Dispatched once a token has been created for an authenticated user, before
    it is put to use. A listener reads the token — through the inherited
    :meth:`~xtr_security_core.event.authentication_event.AuthenticationEvent.get_authentication_token`
    — to react to a successful authentication (a post-authentication account
    check, an audit line), and may stop the event to keep the listeners after
    it from running.
    """
