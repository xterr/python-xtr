"""A user built from the claims of a verified token."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["OidcUser"]


@final
class OidcUser(UserInterface):
    """A user whose identity is the claims a verified token carried.

    When no provider is configured, a verified bearer token is itself the
    source of truth: its ``sub`` names the user, and the rest of the claims
    travel with it for anything downstream that wants them. The identifier is
    read from a chosen claim, and the roles default to a single ordinary role
    unless the caller decides otherwise.

    Attributes:
        claims: The claims the token carried, read-only.
    """

    __slots__ = ("_claims", "_identifier", "_roles")

    def __init__(
        self,
        claims: Mapping[str, object],
        *,
        identifier_claim: str = "sub",
        roles: Sequence[str] = ("ROLE_USER",),
    ) -> None:
        """Read the identifier from ``identifier_claim`` and keep the claims."""
        value = claims.get(identifier_claim)
        if not isinstance(value, str) or not value:
            raise InvalidArgumentError(
                f'The claims carry no usable "{identifier_claim}" to identify the user by.',
            )
        self._claims: dict[str, object] = dict(claims)
        self._identifier = value
        self._roles: tuple[str, ...] = tuple(roles)

    @property
    def claims(self) -> Mapping[str, object]:
        """Return the claims the token carried, read-only."""
        return MappingProxyType(self._claims)

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier read from the chosen claim."""
        return self._identifier

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles granted to this user."""
        return self._roles
