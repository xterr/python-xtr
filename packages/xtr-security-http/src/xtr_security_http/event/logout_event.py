"""The event announcing a logout, for the listeners that carry it out."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface, ServerRequestInterface
    from xtr_security_core.authentication.token.token_interface import TokenInterface

__all__ = ["LogoutEvent"]


@final
class LogoutEvent(Event):
    """Announces that a request asked to log out, and carries its outcome.

    Dispatched by the logout listener once the request proved it is asking
    for a logout — the configured path matched, the cross-site request
    forgery token checked out — and before the token is cleared, so the
    listeners of this event still see the token being logged out. Each
    listener does its own part of the logout — invalidating the session,
    clearing cookies and tokens, answering the request — and the first
    response set on the event is the one the request is answered with.

    Not a frozen dataclass: a listener answering the logout replaces the
    response, and the event is the one place that answer gathers.
    """

    def __init__(
        self,
        request: ServerRequestInterface,
        token: TokenInterface | None,
    ) -> None:
        """Record the request asking to log out and the token it logs out.

        Args:
            request: The request that asked for the logout, as a message.
            token: The token the request's storage held, or ``None`` when
                it held none — a logout is asked for as readily by a
                request that never authenticated.
        """
        self._request = request
        self._token = token
        self._response: ResponseInterface | None = None

    def get_request(self) -> ServerRequestInterface:
        """Return the request that asked for the logout, as a message."""
        return self._request

    def get_token(self) -> TokenInterface | None:
        """Return the token being logged out, or ``None`` when there is none."""
        return self._token

    def set_response(self, response: ResponseInterface) -> None:
        """Answer the logout with ``response``.

        The first listener to answer decides the request: the listeners
        that run after one that set a response see it here and leave it
        alone.
        """
        self._response = response

    def get_response(self) -> ResponseInterface | None:
        """Return the response a listener answered the logout with, if any."""
        return self._response
