"""The stateless user built from a token's claims."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast, final

from typing_extensions import override

from .jwt_user_interface import JwtUserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["JwtUser"]


@final
class JwtUser(JwtUserInterface):
    """A user carrying only an identifier and roles, built from a token's claims.

    The user a stateless deployment authenticates with: it holds no password and
    reads its roles straight from the ``roles`` claim, so a request is proven by
    the token alone with no store to consult.
    """

    __slots__ = ("_identifier", "_roles")

    def __init__(self, identifier: str, roles: Sequence[str] = ()) -> None:
        """Record the user's ``identifier`` and its ``roles``."""
        self._identifier = identifier
        self._roles = tuple(roles)

    @classmethod
    @override
    def create_from_payload(cls, username: str, payload: Mapping[str, object]) -> Self:
        """Build a user named ``username`` from the token's ``roles`` claim."""
        roles = payload.get("roles", ())
        if isinstance(roles, (list, tuple)):
            items = cast("Sequence[object]", roles)
            names: tuple[str, ...] = tuple(str(role) for role in items)
        else:
            names = ()
        return cls(username, names)

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier the token named."""
        return self._identifier

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles read from the token."""
        return self._roles

    @override
    def __str__(self) -> str:
        """Name the user by its identifier."""
        return self._identifier
