"""The token that stands for nobody."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, NoReturn, final

from typing_extensions import override

from xtr_security_core.exception import BadMethodCallError

from .token_interface import TokenInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["NullToken"]


@final
class NullToken(TokenInterface):
    """A token carrying no user, no roles, no attributes: the anonymous caller.

    An access decision is always made against a token; when authentication
    settled on nobody, it is made against this one. It answers every question
    about itself with nothing, and refuses anything that would make it someone:
    setting a user, an attribute or an authentication proof raises.
    """

    __slots__ = ()

    @override
    def __str__(self) -> str:
        """Return the empty string: there is nobody to describe."""
        return ""

    @override
    def get_role_names(self) -> Sequence[str]:
        """Return no roles."""
        return ()

    @override
    def get_user(self) -> UserInterface | None:
        """Return ``None``: nobody is authenticated."""
        return None

    @override
    def set_user(self, user: UserInterface) -> NoReturn:
        """Refuse a user.

        Raises:
            BadMethodCallError: Always.
        """
        del user
        raise BadMethodCallError("Cannot set user on a NullToken.")

    @override
    def get_user_identifier(self) -> str:
        """Return the empty string."""
        return ""

    @override
    def get_attributes(self) -> Mapping[str, object]:
        """Return no attributes."""
        return MappingProxyType({})

    @override
    def set_attributes(self, attributes: Mapping[str, object]) -> NoReturn:
        """Refuse attributes.

        Raises:
            BadMethodCallError: Always.
        """
        del attributes
        raise BadMethodCallError("Cannot set attributes of NullToken.")

    @override
    def has_attribute(self, name: str) -> bool:
        """Return ``False``: no attribute is ever attached."""
        del name
        return False

    @override
    def get_attribute(self, name: str) -> object:
        """Return ``None``: no attribute is ever attached."""
        del name
        return None

    @override
    def set_attribute(self, name: str, value: object) -> NoReturn:
        """Refuse an attribute.

        Raises:
            BadMethodCallError: Always.
        """
        del name, value
        raise BadMethodCallError("Cannot add attribute to NullToken.")

    @override
    def get_authentication_proofs(self) -> Mapping[str, int]:
        """Return no authentication proofs."""
        return MappingProxyType({})

    @override
    def set_authentication_proofs(self, proofs: Mapping[str, int]) -> NoReturn:
        """Refuse authentication proofs.

        Raises:
            BadMethodCallError: Always.
        """
        del proofs
        raise BadMethodCallError("Cannot record authentication proofs on a NullToken.")
