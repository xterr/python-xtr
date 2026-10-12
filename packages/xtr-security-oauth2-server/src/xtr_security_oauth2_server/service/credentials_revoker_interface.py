"""Withdrawing everything a user or a client holds, in one call."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

    from xtr_security_oauth2_server.model.client_interface import ClientInterface

__all__ = ["CredentialsRevokerInterface"]


@runtime_checkable
class CredentialsRevokerInterface(Protocol):
    """Withdraws every credential issued for a user, or to a client.

    An administrative operation, and the one thing the protocol itself never
    asks for: a password change, an account closure or a client being
    withdrawn all have to take back what was already handed out, and none of
    them arrives as an OAuth request.

    "Credential" means everything this server issued and still remembers —
    access tokens, refresh tokens, authorization codes, device codes. What a
    deployment does not store, it cannot withdraw: with no access-token
    records, an access token stays good until it expires, however thoroughly
    its refresh token was revoked.

    Both methods are awaitable and neither reports anything. There is nothing
    useful to count: the honest answer is "everything that could be withdrawn
    has been", and a number would invite a caller to treat zero as a failure.
    """

    async def revoke_credentials_for_user(self, user: UserInterface) -> None:
        """Withdraw every credential issued on behalf of ``user``."""
        ...

    async def revoke_credentials_for_client(self, client: ClientInterface) -> None:
        """Withdraw every credential issued to ``client``."""
        ...
