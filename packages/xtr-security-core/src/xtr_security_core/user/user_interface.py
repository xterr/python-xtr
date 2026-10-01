"""What every user in this library answers to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Sequence

__all__ = ["UserInterface"]


@runtime_checkable
class UserInterface(Protocol):
    """The user a token carries: an identity and the roles it was granted.

    A user is not a set of credentials. It is what authentication resolves to
    — an identifier that names it and the roles it holds — and what
    authorization reasons about. How it is stored, and whether it carries a
    password, is the concern of the provider that loads it, not of this
    contract.
    """

    def get_roles(self) -> Sequence[str]:
        """Return the roles granted to this user.

        Roles are opaque strings. Their meaning is decided by the voters that
        read them and by any role hierarchy configured over them.
        """
        ...

    def get_user_identifier(self) -> str:
        """Return the non-empty string that names this user.

        The value a provider loads a user by, and the ``sub`` a self-issued
        token carries — a username, an email, a client id.
        """
        ...
