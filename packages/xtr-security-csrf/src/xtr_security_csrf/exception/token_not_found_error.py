"""A token was asked for under an id nothing is stored under."""

from __future__ import annotations

from .csrf_error import CsrfError

__all__ = ["TokenNotFoundError"]


class TokenNotFoundError(CsrfError):
    """No token is stored under the id a caller asked to read.

    The manager never raises it — where nothing is stored it mints — it is
    the error a storage raises when its ``get_token`` is called directly for
    an id that holds nothing.
    """

    __slots__: tuple[str, ...] = ("_token_id",)

    _token_id: str

    def __init__(self, token_id: str) -> None:
        """Record which id was asked about and found empty.

        Args:
            token_id: The id whose stored value was asked for.
        """
        super().__init__(f"The CSRF token with ID {token_id} does not exist.")
        self._token_id = token_id

    def get_token_id(self) -> str:
        """Return the id no token is stored under."""
        return self._token_id
