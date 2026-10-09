"""Build a server request."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_message_contracts.server_request_interface import ServerRequestInterface
    from xtr_http_message_contracts.uri_interface import UriInterface

__all__ = ["ServerRequestFactoryInterface"]


@runtime_checkable
class ServerRequestFactoryInterface(Protocol):
    """Makes a server request, so that a caller need not name the class that is one."""

    def create_server_request(
        self,
        method: str,
        uri: UriInterface | str,
        server_params: Mapping[str, object] | None = None,
    ) -> ServerRequestInterface:
        """Return a new server request for ``method`` and ``uri``.

        The environment parameters are taken exactly as given: nothing in them
        is parsed or processed, and in particular neither the method nor the
        URI is read out of them, which is why both have to be passed.

        Args:
            method: The HTTP method of the request.
            uri: The URI of the request. Given as text, the factory builds the
                URI from it.
            server_params: The environment parameters to seed the request
                with. ``None`` seeds it with none.

        Returns:
            The server request.
        """
        ...
