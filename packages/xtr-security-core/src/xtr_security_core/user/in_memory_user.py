"""A user held entirely in memory."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_password_hasher import PasswordAuthenticatedUserInterface

from xtr_security_core.exception import InvalidArgumentError

from .equatable_interface import EquatableInterface
from .user_interface import UserInterface

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["InMemoryUser"]


@final
@dataclass(frozen=True, slots=True)
class InMemoryUser(UserInterface, PasswordAuthenticatedUserInterface, EquatableInterface):
    """A user defined by its own fields rather than loaded from a store.

    Enough of a user for tests, small fixed sets of accounts, and the anonymous
    edges of a system. It carries a password so it can stand in for a stored
    user where one is verified, and an ``enabled`` flag a checker reads.

    Implements the password-carrying user contract: its
    :meth:`get_password` is what a hasher verifies against.
    """

    identifier: str
    password: str | None = None
    roles: Sequence[str] = field(default=())
    enabled: bool = True

    def __post_init__(self) -> None:
        """Reject an empty identifier and normalise the roles to a tuple."""
        if not self.identifier:
            raise InvalidArgumentError("A user identifier cannot be empty.")
        object.__setattr__(self, "roles", tuple(self.roles))

    @override
    def __str__(self) -> str:
        """Return the identifier, so a user reads as who it is."""
        return self.identifier

    @override
    def get_user_identifier(self) -> str:
        """Return the string that names this user."""
        return self.identifier

    @override
    def get_roles(self) -> Sequence[str]:
        """Return the roles granted to this user."""
        return self.roles

    @override
    def get_password(self) -> str | None:
        """Return the hashed password, or ``None`` when the user has none."""
        return self.password

    def is_enabled(self) -> bool:
        """Tell whether this account may authenticate."""
        return self.enabled

    @override
    def is_equal_to(self, user: UserInterface) -> bool:
        """Tell whether ``user`` is the same in-memory user, field for field."""
        return (
            isinstance(user, InMemoryUser)
            and user.identifier == self.identifier
            and _passwords_equal(user.password, self.password)
            and user.enabled == self.enabled
            and set(user.get_roles()) == set(self.get_roles())
        )


def _passwords_equal(left: str | None, right: str | None) -> bool:
    """Compare two optional passwords in constant time, ``None``-safe."""
    if left is None or right is None:
        return left is right
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
