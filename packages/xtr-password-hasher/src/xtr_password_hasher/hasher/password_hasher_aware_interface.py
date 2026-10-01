"""A user that names the hasher it wants."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

__all__ = ["PasswordHasherAwareInterface"]


@runtime_checkable
class PasswordHasherAwareInterface(Protocol):
    """A user that chooses its hasher by name rather than by its class.

    The factory asks this first: a user that answers with a name is hashed by
    the entry mapped to that name, whatever its class. A ``None`` answer means
    "decide by my class instead", the usual case.
    """

    def get_password_hasher_name(self) -> str | None:
        """Return the name of the hasher to use, or ``None`` to decide by class."""
        ...
