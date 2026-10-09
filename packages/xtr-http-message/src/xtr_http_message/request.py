"""A request on its way out, as a client sends it."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_message_contracts import RequestInterface

from ._request_trait import RequestTrait
from .uri import Uri

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface, UriInterface

__all__ = ["Request"]

_HOST = "Host"


@final
class Request(RequestTrait, RequestInterface):
    """An outgoing, client-side request: a method, a URI, headers and a body.

    ```python
    from xtr_http_message import Request

    request = Request("GET", "https://example.com/orders?page=2")
    assert request.get_header_line("host") == "example.com"
    assert request.get_request_target() == "/orders?page=2"
    ```

    The ``Host`` header is taken from the URI unless one was given with the
    request, and is sent in front of every other header.
    """

    __slots__ = ()

    def __init__(
        self,
        method: str,
        uri: UriInterface | str,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        body: bytes | BinaryIO | StreamInterface | None = None,
        version: str = "1.1",
    ) -> None:
        """Build a request.

        Args:
            method: The HTTP method, kept exactly as given.
            uri: The URI of the request. Given as text, it is read into a
                :class:`~xtr_http_message.uri.Uri`.
            headers: Each header name mapped to one value or to several.
            body: The payload, in any of the shapes a stream is built from.
                Left out, nothing is opened until the body is asked for.
            version: The HTTP version number alone.

        Raises:
            InvalidArgumentError: When the URI cannot be read, or a header
                name or value is not one.
        """
        super().__init__()

        self._method = method
        self._uri = Uri(uri) if isinstance(uri, str) else uri
        self._set_headers(headers or {})
        self._protocol = version

        if not self.has_header(_HOST):
            self._update_host_from_uri()

        self._set_body(body)
