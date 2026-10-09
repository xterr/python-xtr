"""Build a request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_message_contracts.request_interface import RequestInterface
    from xtr_http_message_contracts.uri_interface import UriInterface

__all__ = ["RequestFactoryInterface"]


@runtime_checkable
class RequestFactoryInterface(Protocol):
    """Makes a request, so that a caller need not name the class that is one."""

    def create_request(self, method: str, uri: UriInterface | str) -> RequestInterface:
        """Return a new request for ``method`` and ``uri``.

        Args:
            method: The HTTP method of the request.
            uri: The URI of the request. Given as text, the factory builds the
                URI from it.

        Returns:
            The request.
        """
        ...
