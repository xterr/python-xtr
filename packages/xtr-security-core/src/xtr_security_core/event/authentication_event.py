"""The base of every event about an authentication."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["AuthenticationEvent"]


@dataclass(frozen=True)
class AuthenticationEvent(Event):
    """Carries the token an authentication settled on.

    The shared base of the events raised around a successful authentication.
    Derive from it and add what a particular moment needs; every one of them
    answers :meth:`get_authentication_token`.

    Attributes:
        token: The token the authentication settled on.
    """

    token: TokenInterface

    def get_authentication_token(self) -> TokenInterface:
        """Return the token this event is about."""
        return self.token
