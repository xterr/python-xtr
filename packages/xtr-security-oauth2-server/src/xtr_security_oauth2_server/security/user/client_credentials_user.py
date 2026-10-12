"""The caller a token issued to a client itself, rather than to a person, names."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_security_core.user.user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["ClientCredentialsUser"]


@final
class ClientCredentialsUser(UserInterface):
    """A client acting for itself, standing where a resource owner would.

    A token from the client-credentials flow belongs to no person: the client
    authenticated as itself and is calling on its own behalf. The firewall
    still needs *somebody* to put on the token, and there is no user provider
    to ask — the identifier names a client, not a person, so asking a provider
    for it would either fail or, worse, find a user who happens to share the
    name.

    So this stands in. It carries the client's identifier and no roles at all:
    whatever such a caller may do comes from the token's scopes, which the
    token turns into roles itself. Giving this any role of its own would grant
    every client-credentials caller the same thing regardless of what it was
    allowed to ask for.
    """

    __slots__ = ("_client_id",)

    def __init__(self, client_id: str) -> None:
        """Stand for the client registered as ``client_id``."""
        self._client_id = client_id

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier of the client this caller is."""
        return self._client_id

    @override
    def get_roles(self) -> Sequence[str]:
        """Return no roles: what this caller may do is in the token's scopes."""
        return ()

    @override
    def __repr__(self) -> str:
        """Name the client this stands for, which is not a secret."""
        return f"{type(self).__name__}(client_id={self._client_id!r})"
