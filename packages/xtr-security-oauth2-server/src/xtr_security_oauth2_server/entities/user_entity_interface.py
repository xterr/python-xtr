"""What a resource owner answers to."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["UserEntityInterface"]


@runtime_checkable
class UserEntityInterface(Protocol):
    """The resource owner a token was issued on behalf of.

    Only the identifier is asked for, because that is all the protocol writes
    into a token and all a resource server is handed back. Whatever else an
    application knows about its users — a name, an e-mail address, the roles a
    firewall reads — stays on its own class and never travels through here.
    """

    def get_identifier(self) -> str:
        """Return the identifier this resource owner is named by."""
        ...
