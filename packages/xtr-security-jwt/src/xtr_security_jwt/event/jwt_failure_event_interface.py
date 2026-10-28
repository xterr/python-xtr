"""What a failed-authentication event exposes to a listener."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts import ResponseInterface
    from xtr_security_core.exception import AuthenticationError

__all__ = ["JwtFailureEventInterface"]


@runtime_checkable
class JwtFailureEventInterface(Protocol):
    """A failure event a listener can read and answer.

    The common shape of the not-found, expired and invalid events: the error that
    caused the failure, and the response that will answer it — which a listener
    may replace with one of its own.
    """

    def get_response(self) -> ResponseInterface:
        """Return the response that will answer the failed request."""
        ...

    def get_exception(self) -> AuthenticationError:
        """Return the error that caused the failure."""
        ...

    def set_response(self, response: ResponseInterface) -> None:
        """Replace the response that will answer the failed request."""
        ...
