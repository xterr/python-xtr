"""The shared base of every token: a user, fixed roles, and attributes."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, cast

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .token_interface import TokenInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["AbstractToken"]

#: The attribute the authentication proofs are kept under.
_AUTH_PROOFS_ATTRIBUTE: Final = "auth_proofs"


class AbstractToken(TokenInterface):
    """A user, the roles fixed at creation, and a bag of attributes.

    Implements :class:`~xtr_security_core.authentication.token.token_interface.TokenInterface`.
    The token's role names are decoupled from the user's roles on purpose:
    they describe the authentication context, not the user's permanent role
    assignment. That is why :meth:`set_user` only updates the user reference
    and leaves the role names untouched. Concrete tokens derive from this and
    add whatever their own kind needs.
    """

    __slots__: tuple[str, ...] = ("_attributes", "_role_names", "_user")

    _user: UserInterface | None
    _role_names: tuple[str, ...]
    _attributes: dict[str, object]

    def __init__(self, roles: Sequence[str] = ()) -> None:
        """Copy the roles fixed on this token; the user is set through :meth:`set_user`."""
        self._user = None
        self._role_names = tuple(roles)
        self._attributes = {}

    @override
    def get_role_names(self) -> Sequence[str]:
        """Return the roles fixed on this token at creation."""
        return self._role_names

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier of the user, or the empty string for nobody."""
        return self._user.get_user_identifier() if self._user is not None else ""

    @override
    def get_user(self) -> UserInterface | None:
        """Return the authenticated user, or ``None`` for nobody."""
        return self._user

    @override
    def set_user(self, user: UserInterface) -> None:
        """Set the authenticated user; the role names are left untouched."""
        self._user = user

    @override
    def get_attributes(self) -> Mapping[str, object]:
        """Return a read-only snapshot of the attributes attached to this token.

        The mapping is a copy taken now, so a later
        :meth:`set_attribute` does not change a mapping already returned.
        """
        return MappingProxyType(dict(self._attributes))

    @override
    def set_attributes(self, attributes: Mapping[str, object]) -> None:
        """Replace every attribute attached to this token with ``attributes``."""
        self._attributes = dict(attributes)

    @override
    def has_attribute(self, name: str) -> bool:
        """Tell whether an attribute is attached under ``name``."""
        return name in self._attributes

    @override
    def get_attribute(self, name: str) -> object:
        """Return the attribute ``name``.

        Raises:
            InvalidArgumentError: When no attribute is attached under ``name``.
        """
        if name not in self._attributes:
            raise InvalidArgumentError(f'This token has no "{name}" attribute.')
        return self._attributes[name]

    @override
    def set_attribute(self, name: str, value: object) -> None:
        """Attach ``value`` under ``name``, replacing any attribute there."""
        self._attributes[name] = value

    @override
    def get_authentication_proofs(self) -> Mapping[str, int]:
        """Return the authentication methods the user proved, each mapped to its last proof."""
        proofs = self._attributes.get(_AUTH_PROOFS_ATTRIBUTE)
        if proofs is None:
            return MappingProxyType({})
        return MappingProxyType(dict(cast("Mapping[str, int]", proofs)))

    @override
    def set_authentication_proofs(self, proofs: Mapping[str, int]) -> None:
        """Record the authentication methods the user proved, each mapped to its last proof."""
        self._attributes[_AUTH_PROOFS_ATTRIBUTE] = dict(proofs)

    @override
    def __str__(self) -> str:
        """Return ``Class(user="…", roles="…")``, for debugging only."""
        roles = ", ".join(self.get_role_names())
        return f'{type(self).__name__}(user="{self.get_user_identifier()}", roles="{roles}")'
