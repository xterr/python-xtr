"""The event carrying a token's claims and headers before it is signed."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["JwtCreatedEvent"]


@final
class JwtCreatedEvent(Event):
    """Announces a token about to be signed, so a listener may shape it.

    Dispatched by the token manager with the claims and headers it assembled,
    before either is handed to the encoder. Both mappings are mutable — a listener
    adds a claim an application needs, or an extra header, and the manager signs
    what they hold afterwards — while the user the token is for is read-only.
    """

    __slots__ = ("_data", "_header", "_user")

    def __init__(
        self,
        data: dict[str, object],
        user: UserInterface,
        header: dict[str, object] | None = None,
    ) -> None:
        """Record the token's ``data`` and ``header`` and the ``user`` it is for."""
        self._data = data
        self._header = header if header is not None else {}
        self._user = user

    def get_data(self) -> dict[str, object]:
        """Return the claims the token will carry, open to change."""
        return self._data

    def set_data(self, data: dict[str, object]) -> None:
        """Replace the claims the token will carry."""
        self._data = data

    def get_header(self) -> dict[str, object]:
        """Return the header parameters the token will carry, open to change."""
        return self._header

    def set_header(self, header: dict[str, object]) -> None:
        """Replace the header parameters the token will carry."""
        self._header = header

    def get_user(self) -> UserInterface:
        """Return the user the token is being issued for."""
        return self._user
