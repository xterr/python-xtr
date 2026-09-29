"""Who may reach a stored file."""

from __future__ import annotations

from enum import StrEnum

from xtr_storage.exception import InvalidVisibilityError

__all__ = ["Visibility"]


class Visibility(StrEnum):
    """Whether a stored file is readable by anyone, or by its owner alone.

    Two values rather than a backend's permission model: a mode bit on a local
    file and an access list on an object store have nothing in common, and code
    that stores files only ever cares which of the two it asked for. Each
    adapter translates them, and one that cannot say raises rather than guess.

    The members *are* their strings, so an option mapping, a configuration file
    or an environment variable carries ``"public"`` and is understood without a
    conversion step — while code that reads them still gets a closed set.
    """

    PUBLIC = "public"
    PRIVATE = "private"

    @classmethod
    def parse(cls, value: Visibility | str) -> Visibility:
        """Return the member ``value`` stands for.

        The single door for anything arriving from outside — a config option, a
        bundle definition, a caller's keyword — so a typo is refused once, here,
        instead of reaching an adapter as an unknown permission.

        Args:
            value: A member, or the string one carries.

        Returns:
            The member named by ``value``.

        Raises:
            InvalidVisibilityError: When no member carries that string.
        """
        try:
            return cls(value)
        except ValueError as error:
            raise InvalidVisibilityError(value) from error
