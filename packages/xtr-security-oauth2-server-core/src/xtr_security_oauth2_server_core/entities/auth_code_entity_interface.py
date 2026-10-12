"""What an authorization code answers to, beyond being a token."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .token_interface import TokenInterface

__all__ = ["AuthCodeEntityInterface"]


@runtime_checkable
class AuthCodeEntityInterface(TokenInterface, Protocol):
    """A token that remembers the redirect URI it was asked for.

    The redirect URI is kept because the token endpoint has to check that the
    one sent with the code matches the one the code was issued for: without
    that check, a code intercepted on one registered URI could be redeemed
    naming another.

    A code issued for a client with a single registered URI, where the
    authorization request named none, carries ``None`` — there was no URI to
    compare, and the token request may not supply one either.
    """

    def get_redirect_uri(self) -> str | None:
        """Return the redirect URI this code was issued for, or ``None``."""
        ...

    def set_redirect_uri(self, uri: str) -> None:
        """Record that this code was issued for ``uri``."""
        ...
