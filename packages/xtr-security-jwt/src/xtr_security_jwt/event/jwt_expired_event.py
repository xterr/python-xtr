"""The failure event for a token that was refused as expired."""

from __future__ import annotations

from typing import final

from .authentication_failure_event import AuthenticationFailureEvent

__all__ = ["JwtExpiredEvent"]


@final
class JwtExpiredEvent(AuthenticationFailureEvent):
    """Announces that a presented token was refused because it had expired.

    Dispatched by the authenticator, apart from the invalid event, so a listener
    can tell an expired token from a bad one — to prompt a refresh rather than a
    re-login.
    """
