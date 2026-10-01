"""The base failure event: an error, the response, and the request."""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from typing_extensions import override
from xtr_event_dispatcher_contracts import Event

from .jwt_failure_event_interface import JwtFailureEventInterface

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response
    from xtr_security_core.exception import AuthenticationError

__all__ = ["AuthenticationFailureEvent"]


class AuthenticationFailureEvent(Event, JwtFailureEventInterface):
    """Carries a failed token authentication, its response, and the request.

    The base the not-found, expired and invalid events derive from, so a listener
    reading :class:`~xtr_security_jwt.event.jwt_failure_event_interface.JwtFailureEventInterface`
    handles any of them. A listener may replace the response before it is sent.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_exception", "_request", "_response")

    def __init__(
        self,
        exception: AuthenticationError,
        response: Response,
        request: Request | None = None,
    ) -> None:
        """Record the ``exception``, the ``response`` and the ``request``."""
        self._exception: AuthenticationError = exception
        self._response: Response = response
        self._request: Request | None = request

    @override
    def get_exception(self) -> AuthenticationError:
        """Return the error that caused the failure."""
        return self._exception

    @override
    def get_response(self) -> Response:
        """Return the response that will answer the failed request."""
        return self._response

    @override
    def set_response(self, response: Response) -> None:
        """Replace the response that will answer the failed request."""
        self._response = response

    def get_request(self) -> Request | None:
        """Return the request that failed, when one is known."""
        return self._request

    def set_request(self, request: Request) -> None:
        """Record the request that failed."""
        self._request = request
