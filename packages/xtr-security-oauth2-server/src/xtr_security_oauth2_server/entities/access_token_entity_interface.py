"""What an access token answers to, beyond being a token."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .token_interface import TokenInterface

if TYPE_CHECKING:
    from .access_token_signer import AccessTokenSigner

__all__ = ["AccessTokenEntityInterface"]


@runtime_checkable
class AccessTokenEntityInterface(TokenInterface, Protocol):
    """A token that can sign itself into the string a client is handed.

    An access token is the one token here that leaves the server as a
    self-describing document rather than as an opaque reference: a resource
    server reads the claims and decides, without asking this server anything.
    So the entity is handed what it takes to sign — through
    :meth:`set_private_key` — and asked for the result.
    """

    def set_private_key(self, signer: AccessTokenSigner) -> None:
        """Hand this token the key, the names and the clock it signs itself with."""
        ...

    def to_string(self) -> str:
        """Return this token as the signed string a client is handed."""
        ...
