"""A user held entirely in memory."""

from __future__ import annotations

import hmac
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final, Self, final

from typing_extensions import override
from xtr_password_hasher import PasswordAuthenticatedUserInterface

from xtr_security_core._session_state import (
    boolean_field,
    optional_string_field,
    string_field,
    strings_field,
)
from xtr_security_core.exception import InvalidArgumentError

from .equatable_interface import EquatableInterface
from .password_digest import password_digest
from .session_serializable_user_interface import SessionSerializableUserInterface

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from .user_interface import UserInterface

__all__ = ["InMemoryUser"]

# The length of a password a session kept as its digest, eight hex characters.
_DIGEST_LENGTH: Final = 8


@final
@dataclass(frozen=True, slots=True)
class InMemoryUser(
    SessionSerializableUserInterface,
    PasswordAuthenticatedUserInterface,
    EquatableInterface,
):
    """A user defined by its own fields rather than loaded from a store.

    Enough of a user for tests, small fixed sets of accounts, and the anonymous
    edges of a system. It carries a password so it can stand in for a stored
    user where one is verified, and an ``enabled`` flag a checker reads.

    Implements the password-carrying user contract: its
    :meth:`get_password` is what a hasher verifies against.

    A session keeps it whole — its identifier, roles and ``enabled`` flag —
    with the digest of its password in place of the password, and rebuilds it
    as an in-memory user carrying that digest, which :meth:`is_equal_to`
    recognises as the password it stands for.
    """

    identifier: str
    password: str | None = field(default=None, repr=False)
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
    def to_session(self) -> Mapping[str, object]:
        """Return the fields a session keeps, the password as its digest.

        The hash itself never reaches the session store: the digest says
        whether the password changed, and nothing a stolen store could crack.
        """
        return {
            "identifier": self.identifier,
            "password": None if self.password is None else password_digest(self.password),
            "roles": list(self.roles),
            "enabled": self.enabled,
        }

    @classmethod
    @override
    def from_session(cls, state: Mapping[str, object]) -> Self:
        """Rebuild the user a session kept, the digest standing as its password.

        Raises:
            InvalidArgumentError: When a field of ``state`` is missing or of the
                wrong type.
        """
        return cls(
            identifier=string_field(state, "identifier"),
            password=optional_string_field(state, "password"),
            roles=strings_field(state, "roles"),
            enabled=boolean_field(state, "enabled"),
        )

    @override
    def is_equal_to(self, user: UserInterface) -> bool:
        """Tell whether ``user`` is the same in-memory user, field for field.

        The password carries the carve-out a session needs: a password of
        exactly eight characters that is the digest of ``user``'s is the same
        password — the spelling this user is rebuilt with from a session, so a
        reload of the account it stands for compares equal while the password
        has not changed.
        """
        return (
            isinstance(user, InMemoryUser)
            and user.identifier == self.identifier
            and _passwords_match(self.password, user.password)
            and user.enabled == self.enabled
            and set(user.get_roles()) == set(self.get_roles())
        )


def _passwords_match(kept: str | None, reloaded: str | None) -> bool:
    """Tell whether ``reloaded`` is the password ``kept`` is, or the digest stands for."""
    if _passwords_equal(reloaded, kept):
        return True
    return (
        kept is not None
        and reloaded is not None
        and len(kept) == _DIGEST_LENGTH
        and _passwords_equal(password_digest(reloaded), kept)
    )


def _passwords_equal(left: str | None, right: str | None) -> bool:
    """Compare two optional passwords in constant time, ``None``-safe."""
    if left is None or right is None:
        return left is right
    return hmac.compare_digest(left.encode("utf-8"), right.encode("utf-8"))
