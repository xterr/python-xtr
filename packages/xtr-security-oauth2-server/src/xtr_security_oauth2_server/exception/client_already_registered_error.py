"""An identifier a client was to be registered under is one already in use."""

from __future__ import annotations

from typing import final

from xtr_security_oauth2_server_core.exception import OAuth2Error

__all__ = ["ClientAlreadyRegisteredError"]


@final
class ClientAlreadyRegisteredError(OAuth2Error):
    """A client could not be registered because its identifier is taken.

    An identifier is what a client is known by at every endpoint, so two
    registrations cannot share one. Raised by whoever is registering — a
    command that looked first, a store that lost the race between the look and
    the write — and it carries the identifier and nothing else: what a store
    would say of a refused write names the row it refused, and a stored
    client's row carries the hash of its secret.
    """

    __slots__ = ("identifier",)

    def __init__(self, identifier: str) -> None:
        """Report that ``identifier`` is already registered to a client."""
        super().__init__(f'OAuth2 client identified as "{identifier}" already exists.')
        self.identifier = identifier
