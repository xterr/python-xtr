"""A cross-site request forgery token, as a caller holds one."""

from __future__ import annotations

from typing import final

from typing_extensions import override

__all__ = ["CsrfToken"]


@final
class CsrfToken:
    """The id a token is known under, and the value that answers for it.

    A token id names what the token guards — a form, an action, a listener —
    and the value is what a request carries to prove that the page which
    rendered it asked for it. The pair travels together: the id says which
    stored value the carried one is checked against.
    """

    __slots__ = ("_id", "_value")

    def __init__(self, token_id: str, value: str = "") -> None:
        """Record the id and the value that answers for it.

        Args:
            token_id: What the token guards, chosen by whoever mints it.
            value: The value that answers for the id; the empty value is
                the token a caller holds before one has been minted.
        """
        self._id = token_id
        self._value = value

    def get_id(self) -> str:
        """Return the id this token is known under."""
        return self._id

    def get_value(self) -> str:
        """Return the value that answers for the id."""
        return self._value

    @override
    def __str__(self) -> str:
        """Return the value, so a token renders straight into a form or a header."""
        return self._value
