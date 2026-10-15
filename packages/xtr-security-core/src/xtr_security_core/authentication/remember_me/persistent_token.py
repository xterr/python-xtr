"""One remember-me series entry, as it lives in a store."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_security_core.exception import InvalidArgumentError

if TYPE_CHECKING:
    from datetime import datetime

__all__ = ["PersistentToken"]


@final
class PersistentToken:
    """Who a remember-me series remembers, and the value it expects next.

    A remember-me login is a series of one-time values: each presentation
    of a value rotates it, and only the current one is kept. This is that
    entry — the identifier of the user it remembers, the series it belongs
    to, the value expected next, and when the value was last used.
    """

    __slots__: tuple[str, ...] = ("_last_used", "_series", "_token_value", "_user_identifier")

    _user_identifier: str
    _series: str
    _token_value: str
    _last_used: datetime

    def __init__(
        self,
        user_identifier: str,
        series: str,
        token_value: str,
        last_used: datetime,
    ) -> None:
        """Record who the token remembers, its series, its value and its last use.

        Raises:
            InvalidArgumentError: When the identifier, the series or the
                value is empty.
        """
        if user_identifier == "":
            raise InvalidArgumentError('The "user_identifier" must not be empty.')
        if series == "":
            raise InvalidArgumentError('The "series" must not be empty.')
        if token_value == "":
            raise InvalidArgumentError('The "token_value" must not be empty.')
        self._user_identifier = user_identifier
        self._series = series
        self._token_value = token_value
        self._last_used = last_used

    def get_user_identifier(self) -> str:
        """Return the identifier of the user this token remembers."""
        return self._user_identifier

    def get_series(self) -> str:
        """Return the series this token belongs to."""
        return self._series

    def get_token_value(self) -> str:
        """Return the value this token currently expects."""
        return self._token_value

    def get_last_used(self) -> datetime:
        """Return when this token's value was last used."""
        return self._last_used
