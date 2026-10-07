"""The shared base of every token: a user, fixed roles, and attributes."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from typing_extensions import override

from xtr_security_core.exception import InvalidArgumentError

from .token_interface import TokenInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["AbstractToken"]


class AbstractToken(TokenInterface):
    """A user, the roles fixed at creation, and a bag of attributes.

    Implements :class:`~xtr_security_core.authentication.token.token_interface.TokenInterface`.
    The roles are copied at construction and never re-read from the user, so a
    decision made against this token reflects what authentication settled on,
    not what the user object may report afterwards. Concrete tokens derive from
    this and add whatever their own kind needs.
    """

    __slots__: tuple[str, ...] = ("_attributes", "_role_names", "_user")

    _user: UserInterface | None
    _role_names: tuple[str, ...]
    _attributes: dict[str, object]

    def __init__(self, user: UserInterface | None = None, roles: Sequence[str] = ()) -> None:
        """Record the user and copy the roles fixed on this token."""
        self._user = user
        self._role_names = tuple(roles)
        self._attributes = {}

    @override
    def get_user(self) -> UserInterface | None:
        """Return the authenticated user, or ``None`` for nobody."""
        return self._user

    @override
    def get_user_identifier(self) -> str:
        """Return the identifier of the user, or the empty string for nobody."""
        return self._user.get_user_identifier() if self._user is not None else ""

    @override
    def get_role_names(self) -> Sequence[str]:
        """Return the roles fixed on this token at creation."""
        return self._role_names

    @override
    def get_attributes(self) -> Mapping[str, object]:
        """Return a read-only snapshot of the attributes attached to this token.

        The mapping is a copy taken now, so a later
        :meth:`set_attribute` does not change a mapping already returned.
        """
        return MappingProxyType(dict(self._attributes))

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
    def has_attribute(self, name: str) -> bool:
        """Tell whether an attribute is attached under ``name``."""
        return name in self._attributes

    @override
    def set_attribute(self, name: str, value: object) -> None:
        """Attach ``value`` under ``name``, replacing any attribute there."""
        self._attributes[name] = value
