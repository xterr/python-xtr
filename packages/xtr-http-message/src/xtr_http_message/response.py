"""A response on its way out, as a server sends it."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Final, Self, final

from typing_extensions import override
from xtr_http_message_contracts import ResponseInterface

from ._message_trait import MessageTrait
from .exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import BinaryIO

    from xtr_http_message_contracts import StreamInterface

__all__ = ["Response"]

_LOWEST_STATUS = 100
_HIGHEST_STATUS = 599

# The reason phrase recommended for each status code that has one. A code
# absent from here is still a status code; it simply has no phrase to offer.
_PHRASES: Final[Mapping[int, str]] = MappingProxyType(
    {
        100: "Continue",
        101: "Switching Protocols",
        102: "Processing",
        200: "OK",
        201: "Created",
        202: "Accepted",
        203: "Non-Authoritative Information",
        204: "No Content",
        205: "Reset Content",
        206: "Partial Content",
        207: "Multi-status",
        208: "Already Reported",
        300: "Multiple Choices",
        301: "Moved Permanently",
        302: "Found",
        303: "See Other",
        304: "Not Modified",
        305: "Use Proxy",
        306: "Switch Proxy",
        307: "Temporary Redirect",
        400: "Bad Request",
        401: "Unauthorized",
        402: "Payment Required",
        403: "Forbidden",
        404: "Not Found",
        405: "Method Not Allowed",
        406: "Not Acceptable",
        407: "Proxy Authentication Required",
        408: "Request Time-out",
        409: "Conflict",
        410: "Gone",
        411: "Length Required",
        412: "Precondition Failed",
        413: "Request Entity Too Large",
        414: "Request-URI Too Large",
        415: "Unsupported Media Type",
        416: "Requested range not satisfiable",
        417: "Expectation Failed",
        418: "I'm a teapot",
        422: "Unprocessable Entity",
        423: "Locked",
        424: "Failed Dependency",
        425: "Unordered Collection",
        426: "Upgrade Required",
        428: "Precondition Required",
        429: "Too Many Requests",
        431: "Request Header Fields Too Large",
        451: "Unavailable For Legal Reasons",
        500: "Internal Server Error",
        501: "Not Implemented",
        502: "Bad Gateway",
        503: "Service Unavailable",
        504: "Gateway Time-out",
        505: "HTTP Version not supported",
        506: "Variant Also Negotiates",
        507: "Insufficient Storage",
        508: "Loop Detected",
        511: "Network Authentication Required",
    }
)


@final
class Response(MessageTrait, ResponseInterface):
    """A response: a status code, the phrase that goes with it, headers and a body.

    ```python
    from xtr_http_message import Response

    response = Response(201, {"content-type": "application/json"}, b'{"id": 7}')
    assert response.get_reason_phrase() == "Created"
    ```

    Given no reason phrase, the one recommended for the status code is filled
    in; given an empty one, the response carries none, since a status line
    need not have a phrase at all.
    """

    __slots__ = ("_reason_phrase", "_status_code")

    def __init__(
        self,
        status: int = 200,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        body: bytes | BinaryIO | StreamInterface | None = None,
        version: str = "1.1",
        reason: str | None = None,
    ) -> None:
        """Build a response.

        Args:
            status: The status code.
            headers: Each header name mapped to one value or to several.
            body: The payload, in any of the shapes a stream is built from.
                Left out, nothing is opened until the body is asked for.
            version: The HTTP version number alone.
            reason: The reason phrase. ``None`` — the default — takes the one
                recommended for ``status``; an empty string leaves the
                response with none.

        Raises:
            InvalidArgumentError: When a header name or value is not one.
        """
        super().__init__()

        self._set_body(body)

        self._status_code: int = status
        self._set_headers(headers or {})

        if reason is None:
            self._reason_phrase: str = _PHRASES.get(status, "")
        else:
            self._reason_phrase = reason

        self._protocol = version

    @override
    def get_status_code(self) -> int:
        """Return the status code of the response.

        Returns:
            The three-digit code saying how the server got on with the
            request.
        """
        return self._status_code

    @override
    def get_reason_phrase(self) -> str:
        """Return the reason phrase that goes with the status code.

        Returns:
            The reason phrase, or an empty string when the response carries
            none.
        """
        return self._reason_phrase

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        """Return an instance carrying ``code`` and, optionally, ``reason_phrase``.

        Args:
            code: The status code to set.
            reason_phrase: The phrase to go with ``code``. Left out or empty,
                the one recommended for ``code`` is filled in where there is
                one.

        Returns:
            A new instance; this one is left as it was.

        Raises:
            InvalidArgumentError: When the code is not a status code.
        """
        if code < _LOWEST_STATUS or code > _HIGHEST_STATUS:
            message = (
                "Status code has to be an integer between 100 and 599. "
                f"A status code of {code} was given"
            )
            raise InvalidArgumentError(message)

        if reason_phrase == "":
            reason_phrase = _PHRASES.get(code, "")

        new = self._copy()
        new._status_code = code  # noqa: SLF001 — a copy of this very class.
        new._reason_phrase = reason_phrase  # noqa: SLF001 — a copy of this very class.

        return new
