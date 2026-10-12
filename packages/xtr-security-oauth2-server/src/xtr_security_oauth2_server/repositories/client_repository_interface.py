"""Where registered clients are read from."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from xtr_security_oauth2_server.entities.client_entity_interface import ClientEntityInterface

__all__ = ["ClientRepositoryInterface"]


@runtime_checkable
class ClientRepositoryInterface(RepositoryInterface, Protocol):
    """Finds a registered client, and says whether it proved who it is.

    Both methods may reach a database, so both are awaitable.

    Authenticating a client is kept apart from finding one because the grants
    need them apart: every grant has to find the client that a request names
    in order to read its redirect URIs, while only a request that carried
    credentials — or that must have — goes on to check them.
    """

    async def get_client_entity(self, client_identifier: str) -> ClientEntityInterface | None:
        """Return the client registered as ``client_identifier``, or ``None``."""
        ...

    async def validate_client(
        self,
        client_identifier: str,
        client_secret: str | None,
        grant_type: str | None,
    ) -> bool:
        """Tell whether ``client_identifier`` proved itself for ``grant_type``.

        A confidential client is expected to present ``client_secret`` and the
        answer is whether it matched; a public client presents none, and the
        answer is whether this deployment lets it use the grant without one.

        Args:
            client_identifier: The client the request named.
            client_secret: The secret the request carried, or ``None`` for none.
            grant_type: The grant being used, or ``None`` when the caller is
                not acting for a particular grant.
        """
        ...
