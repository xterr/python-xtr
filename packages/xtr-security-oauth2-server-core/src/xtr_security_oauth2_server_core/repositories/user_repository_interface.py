"""Where a resource owner's credentials are checked."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from .repository_interface import RepositoryInterface

if TYPE_CHECKING:
    from xtr_security_oauth2_server_core.entities.client_entity_interface import (
        ClientEntityInterface,
    )
    from xtr_security_oauth2_server_core.entities.user_entity_interface import UserEntityInterface

__all__ = ["UserRepositoryInterface"]


@runtime_checkable
class UserRepositoryInterface(RepositoryInterface, Protocol):
    """Checks a resource owner's own credentials, for the one grant that sees them.

    Only the grant that takes a username and a password reaches here: every
    other flow sends the resource owner to this server's own pages and never
    learns their credentials, which is the point of the protocol. A deployment
    that keeps that grant off can leave this answering ``None``.

    The client is passed in as well, so a deployment can let one client check
    credentials and refuse another.
    """

    async def get_user_entity_by_user_credentials(
        self,
        username: str,
        password: str,
        grant_type: str,
        client_entity: ClientEntityInterface,
    ) -> UserEntityInterface | None:
        """Return the resource owner the credentials belong to, or ``None``.

        Answering ``None`` covers every reason to refuse — no such user, a
        wrong password, an account this client may not act for — because the
        request is answered the same way whichever it was: telling a caller
        which of the two it got wrong is a way to enumerate accounts.

        Args:
            username: The name the request carried.
            password: The password the request carried.
            grant_type: The grant asking.
            client_entity: The client asking.
        """
        ...
