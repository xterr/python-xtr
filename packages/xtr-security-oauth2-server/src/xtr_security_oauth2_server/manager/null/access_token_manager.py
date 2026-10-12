"""The access-token manager for a deployment that stores no access token."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_oauth2_server.manager.access_token_manager_interface import (
    AccessTokenManagerInterface,
)

if TYPE_CHECKING:
    from xtr_security_oauth2_server.model.access_token_interface import AccessTokenInterface

__all__ = ["AccessTokenManager"]


@final
class AccessTokenManager(AccessTokenManagerInterface):
    """Stores nothing, finds nothing, sweeps nothing.

    An access token here is a signed document a resource server reads on its
    own, so a deployment may decide never to write one down: no row per token
    issued, and no lookup on the way in. What it gives up is revocation — a
    token stays good until it expires, because there is nothing to mark.

    Wired in place of a real manager when access tokens are not persisted, so
    the repository bridge above it is unchanged and nothing else in the server
    knows the difference.
    """

    @override
    def __repr__(self) -> str:
        """Name the type, which is the whole of what there is to say."""
        return f"{type(self).__name__}()"

    @override
    async def find(self, identifier: str) -> AccessTokenInterface | None:
        """Return ``None``: nothing was ever stored to find."""
        del identifier

        return None

    @override
    async def save(self, access_token: AccessTokenInterface) -> None:
        """Do nothing: this deployment keeps no record of its access tokens."""
        del access_token

    @override
    async def clear_expired(self) -> int:
        """Return zero: there is nothing stored to sweep."""
        return 0
