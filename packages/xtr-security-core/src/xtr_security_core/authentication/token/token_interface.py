"""What a token — the outcome of authentication — answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["TokenInterface"]


@runtime_checkable
class TokenInterface(Protocol):
    """The result of authentication: who is calling, and what was decided about them.

    A token names a user and the roles that authentication settled on. Those
    roles are fixed when the token is created, decoupled from whatever the
    live user object may report later, so a decision reads a stable snapshot.
    Attributes carry extra data an authenticator or a listener attached — the
    scopes of a bearer token, the client it was issued to.
    """

    def get_user(self) -> UserInterface | None:
        """Return the authenticated user, or ``None`` for nobody."""
        ...

    def get_user_identifier(self) -> str:
        """Return the identifier of the user, or the empty string for nobody."""
        ...

    def get_role_names(self) -> Sequence[str]:
        """Return the roles fixed on this token at creation."""
        ...

    def get_attributes(self) -> Mapping[str, object]:
        """Return every attribute attached to this token, read-only."""
        ...

    def get_attribute(self, name: str) -> object:
        """Return the attribute ``name``.

        Raises:
            InvalidArgumentError: When no attribute is attached under ``name``.
        """
        ...

    def has_attribute(self, name: str) -> bool:
        """Tell whether an attribute is attached under ``name``."""
        ...

    def set_attribute(self, name: str, value: object) -> None:
        """Attach ``value`` under ``name``, replacing any attribute there."""
        ...
