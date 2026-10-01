"""The failure event for a request that carried no token."""

from __future__ import annotations

from typing import final

from .authentication_failure_event import AuthenticationFailureEvent

__all__ = ["JwtNotFoundEvent"]


@final
class JwtNotFoundEvent(AuthenticationFailureEvent):
    """Announces that a request reached a protected resource with no token.

    Dispatched by the authenticator's entry point, so a listener can answer a
    missing token differently from a wrong one — pointing at where to obtain one.
    """
