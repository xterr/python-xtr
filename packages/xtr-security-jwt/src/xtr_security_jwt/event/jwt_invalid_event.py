"""The failure event for a token that was refused as invalid."""

from __future__ import annotations

from typing import final

from .authentication_failure_event import AuthenticationFailureEvent

__all__ = ["JwtInvalidEvent"]


@final
class JwtInvalidEvent(AuthenticationFailureEvent):
    """Announces that a presented token was refused as invalid.

    Dispatched by the authenticator when a token could not be trusted for any
    reason other than expiry — malformed, unsigned, tampered with, or missing the
    claim naming its user.
    """
