"""A response written out in advance, for a client that answers from a script."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self

from typing_extensions import override
from xtr_http_client_contracts import HttpResponseInterface

from xtr_http_client.exception import InvalidArgumentError, TransportError
from xtr_http_client.internal.mock_head import scripted_message
from xtr_http_client.internal.mock_info import issued_info
from xtr_http_client.internal.response_body import ResponseBody

from .http_response import HttpResponse

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable, Mapping, Sequence
    from types import TracebackType

    from xtr_http_message import Response
    from xtr_http_message_contracts import StreamInterface

__all__ = ["MockResponse"]

_NOT_ISSUED = "MockResponse instances must be issued by MockHttpClient before processing."


class MockResponse(HttpResponseInterface):
    """An answer written before the question, which a client hands back as its own.

    A test says what it wants to come back — a body, a status, headers, or an
    error instead of an answer — and :class:`MockHttpClient
    <xtr_http_client.mock_http_client.MockHttpClient>` answers with it. Nothing
    is sent and nothing is opened.

    ```python
    client = MockHttpClient(MockResponse(b'{"id": 7}', {"http_code": 201}))
    async with await client.request("GET", "/orders") as response:
        assert await response.to_array() == {"id": 7}
    ```

    A written response is only half a response: the other half — the method,
    the URL and the options it answers — is the client's, and is filled in when
    the client *issues* it. Until then there is nothing to read, because what
    came back is not yet an answer to anything; reading one raises
    :class:`InvalidArgumentError
    <xtr_http_client_contracts.exception.invalid_argument_error.InvalidArgumentError>`.

    Once issued, it is an ordinary response of this package: the status,
    headers, body, copies and errors are :class:`HttpResponse
    <xtr_http_client.response.http_response.HttpResponse>`'s, over a body made
    of the scripted pieces, so a test reads a scripted answer exactly as it
    reads a real one.
    """

    __slots__: tuple[str, ...] = (
        "_info",
        "_issued",
        "_message",
        "_pieces",
        "_request_method",
        "_request_options",
        "_request_url",
    )

    _info: dict[str, object]
    _issued: HttpResponse | None
    _message: Response
    _pieces: Iterable[bytes]
    _request_method: str
    _request_options: Mapping[str, object]
    _request_url: str

    def __init__(
        self,
        body: bytes | str | Iterable[bytes] = b"",
        info: Mapping[str, object] | None = None,
    ) -> None:
        """Write out an answer.

        Args:
            body: What the body is to be. Bytes or text are the whole of it;
                an iterable of bytes is handed over a piece at a time, which
                is how a test reads a body that arrives in pieces.
            info: What the transfer is to claim about itself — ``http_code``
                (``200`` when left out), ``response_headers``, and ``error``
                for a transfer that is to fail rather than answer. Any other
                entry is carried through to ``get_info()`` untouched.
        """
        script = dict(info or {})
        self._pieces, length = _scripted(body)
        self._message = scripted_message(script, length)
        script["http_code"] = self._message.get_status_code()

        self._info = script
        self._issued = None
        self._request_method = ""
        self._request_url = ""
        self._request_options = {}

    def issue(self, method: str, url: str, options: Mapping[str, object]) -> Self:
        """Make this written answer the answer to a request that was just made.

        What a client does to a response before handing it over: the request
        side is filled in, and the body and the record of the transfer come
        into being. Called by :class:`MockHttpClient
        <xtr_http_client.mock_http_client.MockHttpClient>`.

        Args:
            method: The method the request was made with.
            url: The URL it was made to, resolved.
            options: The options it was made with, merged.

        Returns:
            This response, now readable.

        Raises:
            TransportError: When the script says the transfer fails rather
                than answers. Nothing is opened in that case, so there is
                nothing left to let go of.
        """
        self._request_method = method
        self._request_url = url
        self._request_options = dict(options)

        error = self._info.get("error")
        if isinstance(error, str) and error:
            raise TransportError(error)

        self._issued = HttpResponse(
            self._message,
            ResponseBody(_arriving(self._pieces)),
            issued_info(self._info, self._message, method, url, options),
        )

        return self

    def get_request_method(self) -> str:
        """The method of the request this answered, empty until it answered one."""
        return self._request_method

    def get_request_url(self) -> str:
        """The URL of the request this answered, empty until it answered one."""
        return self._request_url

    def get_request_options(self) -> Mapping[str, object]:
        """The options the request was made with, merged as the client sent them."""
        return self._request_options

    @override
    def get_status_code(self) -> int:
        """Return the status the script says the answer came back with."""
        return self._delegate.get_status_code()

    @override
    def get_reason_phrase(self) -> str:
        """Return the reason phrase that goes with the status."""
        return self._delegate.get_reason_phrase()

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> Self:
        """Return a copy carrying ``code`` and, optionally, ``reason_phrase``."""
        return self._around(self._delegate.with_status(code, reason_phrase))

    @override
    def get_protocol_version(self) -> str:
        """Return the HTTP version the script says the answer came back on."""
        return self._delegate.get_protocol_version()

    @override
    def with_protocol_version(self, version: str) -> Self:
        """Return a copy carrying ``version``."""
        return self._around(self._delegate.with_protocol_version(version))

    @override
    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values."""
        return self._delegate.get_headers()

    @override
    def has_header(self, name: str) -> bool:
        """Tell whether a header is there, matching ``name`` without case."""
        return self._delegate.has_header(name)

    @override
    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case."""
        return self._delegate.get_header(name)

    @override
    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas."""
        return self._delegate.get_header_line(name)

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a copy whose ``name`` header holds ``value`` and nothing else."""
        return self._around(self._delegate.with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> Self:
        """Return a copy with ``value`` appended to the ``name`` header."""
        return self._around(self._delegate.with_added_header(name, value))

    @override
    def without_header(self, name: str) -> Self:
        """Return a copy with the ``name`` header gone."""
        return self._around(self._delegate.without_header(name))

    @override
    def get_body(self) -> StreamInterface:
        """Return the body, over the pieces the script was written with."""
        return self._delegate.get_body()

    @override
    def with_body(self, body: StreamInterface) -> Self:
        """Return a copy reading its body from ``body`` instead."""
        return self._around(self._delegate.with_body(body))

    @override
    def get_info(self, key: str | None = None) -> object:
        """Return what the transfer knows about itself, as it stands.

        Readable before the response is issued, where it is the script as it
        was written — which is what lets a cancelled response say so even
        though it never answered anything.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            Every entry when ``key`` is ``None``; otherwise the value under
            ``key``, or ``None`` when there is no such entry.
        """
        if self._issued is not None:
            return self._issued.get_info(key)
        if key is None:
            return dict(self._info)

        return self._info.get(key)

    @override
    async def cancel(self) -> None:
        """Abandon the transfer and let go of what it was holding."""
        self._info["canceled"] = True
        self._info["error"] = "Response has been canceled."

        if self._issued is not None:
            await self._issued.cancel()

    @override
    async def get_content(self, throw: bool = True) -> bytes:
        """Read the whole body, as the script hands it over.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                answered with the body that came with it.

        Returns:
            Every byte of the body, empty when the script wrote none.

        Raises:
            InvalidArgumentError: When the response has not been issued.
            TransportError: When the body cannot be read.
            RedirectionError: On a 3xx, when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        return await self._delegate.get_content(throw)

    @override
    async def to_array(self, throw: bool = True) -> dict[str, object]:
        """Read the whole body and decode it as a JSON object.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                answered with the body that came with it.

        Returns:
            What the body decoded to.

        Raises:
            InvalidArgumentError: When the response has not been issued.
            JsonError: When the body is empty, is not JSON, or is JSON that is
                not an object.
            TransportError: When the body cannot be read.
            RedirectionError: On a 3xx, when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        return await self._delegate.to_array(throw)

    @override
    async def __aenter__(self) -> Self:
        """Enter a block that owns the scripted body.

        Returns:
            This response.
        """
        return self

    @override
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the body however the block ends, and nothing else.

        A response no client issued has no body to let go of, so leaving its
        block does nothing rather than complaining about what was never read.

        Args:
            exc_type: The class of the exception the block is leaving with.
            exc: That exception.
            traceback: Its traceback.
        """
        if self._issued is not None:
            await self._issued.__aexit__(exc_type, exc, traceback)

    @property
    def _delegate(self) -> HttpResponse:
        """The response this one answers from, once a client has issued it.

        Raises:
            InvalidArgumentError: When no client has, since a written answer
                is not an answer to anything until one does.
        """
        if self._issued is None:
            raise InvalidArgumentError(_NOT_ISSUED)

        return self._issued

    def _around(self, issued: HttpResponse) -> Self:
        """Return a response of this kind around a copy of the issued response.

        Built field by field rather than through the constructor, because a
        copy answers from a message that has already been made, where a new
        response makes one out of the script it is written with.
        """
        copy = type(self).__new__(type(self))
        copy._message = self._message  # noqa: SLF001 — a copy of this very class.
        copy._pieces = self._pieces  # noqa: SLF001 — likewise.
        copy._info = self._info  # noqa: SLF001 — likewise.
        copy._issued = issued  # noqa: SLF001 — likewise.
        copy._request_method = self._request_method  # noqa: SLF001 — likewise.
        copy._request_url = self._request_url  # noqa: SLF001 — likewise.
        copy._request_options = self._request_options  # noqa: SLF001 — likewise.

        return copy


def _scripted(body: bytes | str | Iterable[bytes]) -> tuple[Iterable[bytes], int | None]:
    """The pieces a body is handed over as, and its length when it has one.

    Bytes and text are the whole body, so their length is known and is what
    ``Content-Length`` is made to say. An iterable is as long as it turns out
    to be, which nobody knows until it ends.
    """
    if isinstance(body, str):
        whole = body.encode()
    elif isinstance(body, bytes):
        whole = body
    else:
        return body, None

    return ([whole] if whole else []), len(whole)


async def _arriving(pieces: Iterable[bytes]) -> AsyncIterator[bytes]:
    """The scripted pieces, handed over as a transfer would produce them."""
    for piece in pieces:
        yield piece
