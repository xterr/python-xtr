"""No hasher was configured for a user, a class or a name."""

from __future__ import annotations

from .password_hasher_error import PasswordHasherError

__all__ = ["UnknownPasswordHasherError"]


class UnknownPasswordHasherError(PasswordHasherError, LookupError):
    """The factory holds no hasher for the user, class or name asked for.

    Raised by
    :meth:`~xtr_password_hasher.PasswordHasherFactoryInterface.get_password_hasher`
    when nothing in its mapping matches — no entry for the class or any of its
    bases, no entry for the name the user declares, and no entry for the string
    key given. The message names what was looked up so the fix is to add that
    key to the factory's mapping.

    Also a :class:`LookupError`, so a caller may catch either this type or the
    built-in.

    Attributes:
        looked_up: What was searched for — a class's qualified name, or the
            string key given.
    """

    looked_up: str

    def __init__(self, looked_up: str) -> None:
        """Record what had no hasher, and how to fix it."""
        self.looked_up = looked_up
        super().__init__(
            f'No password hasher is configured for "{looked_up}". '
            f"Add it to the factory's mapping, keyed by the class, a "
            f'"module:Class" string, or the name the user declares.',
        )
