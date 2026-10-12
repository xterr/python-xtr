"""A token response is built, and may still be replaced."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface

__all__ = ["TokenRequestResolveEvent"]


class TokenRequestResolveEvent(Event):
    """Carries the answer to a token request, before it is sent.

    The seam for a deployment that has to add a field of its own to the token
    response, or record that one went out. It carries the whole answer rather
    than the fields of it, because the response at this point is already
    built — the grant decided what was issued, and what is left is the
    document.

    Announced for a refusal as well as for a success: an error answer is still
    the answer to the request.
    """

    def __init__(self, response: ResponseInterface) -> None:
        """Announce ``response`` as the answer to a token request."""
        self._response: ResponseInterface = response

    def get_response(self) -> ResponseInterface:
        """Return the answer as it stands."""
        return self._response

    def set_response(self, response: ResponseInterface) -> Self:
        """Send ``response`` instead of the one announced."""
        self._response = response

        return self

    @override
    def __repr__(self) -> str:
        """Name the event and the status of the answer, never the document.

        The answer to a token request carries the token itself, and whether its
        reading shows it is the response implementation's choice rather than
        this event's, so only the status is named.
        """
        return f"{type(self).__name__}(status={self._response.get_status_code()!r})"
