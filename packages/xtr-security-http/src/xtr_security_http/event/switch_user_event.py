"""The event announcing a user switch, into an impersonation or out of one."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface
    from xtr_security_core.user.user_interface import UserInterface

__all__ = ["SwitchUserEvent"]


@final
class SwitchUserEvent(Event):
    """Announces a user switching to another, or an impersonation being left.

    Dispatched under
    :attr:`~xtr_security_http.security_events.SecurityEvents.SWITCH_USER`
    — the second event that carries a name of its own, because an
    application listens for a user switch across the whole flow rather
    than at one step — once per switch: before the switched-to token is
    stored, and once per exit, before the original token is restored. A
    listener reads the request the switch was asked through and the user
    being switched to, and may replace the token the switch settles on —
    the dispatcher's answer is the token the flow stores.

    Not a frozen dataclass: a listener replaces the token.

    Attributes:
        request: The request the switch was asked through.
        target_user: The user being switched to — on an exit, the user
            returned to.
    """

    def __init__(
        self,
        request: ServerRequestInterface,
        target_user: UserInterface,
        token: TokenInterface | None = None,
    ) -> None:
        """Record the request, the user being switched to, and the token.

        Args:
            request: The request the switch was asked through.
            target_user: The user being switched to — on an exit, the user
                returned to.
            token: The token the switch settles on, when the announcer
                already built it.
        """
        self._request = request
        self._target_user = target_user
        self._token = token

    def get_request(self) -> ServerRequestInterface:
        """Return the request the switch was asked through."""
        return self._request

    def get_target_user(self) -> UserInterface:
        """Return the user being switched to — on an exit, the user returned to."""
        return self._target_user

    def get_token(self) -> TokenInterface | None:
        """Return the token the switch settles on, or ``None`` before one is set."""
        return self._token

    def set_token(self, token: TokenInterface) -> None:
        """Replace the token the switch settles on.

        A listener may hand the flow a token of its own — one carrying
        extra roles, say — and the switch stores what the event now
        carries instead of what it was announced with.
        """
        self._token = token
