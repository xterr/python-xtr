"""The event carrying a token's response data, for a listener to enrich."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["AuthenticationSuccessEvent"]


@final
class AuthenticationSuccessEvent(Event):
    """Announces a successful token issuance, so a listener may shape the response body.

    Dispatched when an application hands a freshly minted token back to a client,
    with the data the response will carry and the user it was minted for. A
    listener adds to the data — a refresh token, a profile — and the application
    sends what it holds afterwards.
    """

    __slots__ = ("_data", "_user")

    def __init__(self, data: dict[str, object], user: UserInterface) -> None:
        """Record the response ``data`` and the ``user`` the token was minted for."""
        self._data = data
        self._user = user

    def get_data(self) -> dict[str, object]:
        """Return the data the response will carry, open to change."""
        return self._data

    def set_data(self, data: dict[str, object]) -> None:
        """Replace the data the response will carry."""
        self._data = data

    def get_user(self) -> UserInterface:
        """Return the user the token was minted for."""
        return self._user
