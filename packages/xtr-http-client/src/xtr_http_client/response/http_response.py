"""The response a client hands back once the head of it has arrived."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Self, cast, final

from typing_extensions import override
from xtr_http_client_contracts import HttpResponseInterface

from xtr_http_client.exception import (
    ClientError,
    JsonError,
    RedirectionError,
    ServerError,
    TransportError,
)
from xtr_http_client.exception._http_error_message import build_message
from xtr_http_client.internal.debug_type import debug_type

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence
    from types import TracebackType

    from xtr_http_message import Response
    from xtr_http_message_contracts import StreamInterface

    from xtr_http_client.internal.response_body import ResponseBody

__all__ = ["HttpResponse"]

_REDIRECTION = 300
_CLIENT_ERROR = 400
_SERVER_ERROR = 500


@final
class HttpResponse(HttpResponseInterface):
    """A response whose head has arrived and whose body is read when it is asked for.

    Three parts are held apart because they arrive apart: the message — the
    status line and the headers, which came in whole — the body, which is
    still coming off the transfer, and the info, which the transfer goes on
    writing to as it does.

    A ``with_*`` copy therefore copies the message alone. The body is the one
    transfer's and cannot be had twice, and the info is that transfer's own
    record, so every copy reads the one mapping and sees whatever has been
    written to it since.
    """

    __slots__ = ("_body", "_info", "_message", "_on_cancel")

    def __init__(
        self,
        message: Response,
        body: ResponseBody,
        info: dict[str, object],
        on_cancel: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Hold the parts of a response that arrived apart.

        Args:
            message: The status line and the headers, as they came in.
            body: The body, taken off the transfer as it is asked for.
            info: What the transfer knows about itself. Kept rather than
                copied, because the transfer is still writing to it.
            on_cancel: What abandoning the transfer takes, when there is
                anything: the client that opened it knows, a response does
                not.
        """
        self._message: Response = message
        self._body: StreamInterface = body
        self._info: dict[str, object] = info
        self._on_cancel: Callable[[], Awaitable[None]] | None = on_cancel

    @override
    def get_status_code(self) -> int:
        """Return the status code the server answered with.

        Returns:
            The three-digit code off the status line.
        """
        return self._message.get_status_code()

    @override
    def get_reason_phrase(self) -> str:
        """Return the reason phrase that goes with the status code.

        Returns:
            The phrase, or an empty string when the status line carried none.
        """
        return self._message.get_reason_phrase()

    @override
    def with_status(self, code: int, reason_phrase: str = "") -> HttpResponse:
        """Return a copy carrying ``code`` and, optionally, ``reason_phrase``.

        Args:
            code: The status code to set.
            reason_phrase: The phrase to go with ``code``.

        Returns:
            A new response; this one is left as it was.
        """
        return self._around(self._message.with_status(code, reason_phrase))

    @override
    def get_protocol_version(self) -> str:
        """Return the HTTP version the answer came back on.

        Returns:
            The version number alone, such as ``"1.1"``.
        """
        return self._message.get_protocol_version()

    @override
    def with_protocol_version(self, version: str) -> HttpResponse:
        """Return a copy carrying ``version``.

        Args:
            version: The HTTP version number alone.

        Returns:
            A new response; this one is left as it was.
        """
        return self._around(self._message.with_protocol_version(version))

    @override
    def get_headers(self) -> Mapping[str, Sequence[str]]:
        """Return every header, each name mapped to all of its values.

        Returns:
            The names in the case they arrived in, mapped to their values.
        """
        return self._message.get_headers()

    @override
    def has_header(self, name: str) -> bool:
        """Tell whether a header arrived, matching ``name`` without case.

        Args:
            name: The header name, in any case.

        Returns:
            ``True`` when some header name matches it.
        """
        return self._message.has_header(name)

    @override
    def get_header(self, name: str) -> Sequence[str]:
        """Return every value recorded under a header, matched without case.

        Args:
            name: The header name, in any case.

        Returns:
            Its values in order, or an empty sequence when it did not arrive.
        """
        return self._message.get_header(name)

    @override
    def get_header_line(self, name: str) -> str:
        """Return the values of a header joined with commas.

        Args:
            name: The header name, in any case.

        Returns:
            The values joined with commas, or an empty string.
        """
        return self._message.get_header_line(name)

    @override
    def with_header(self, name: str, value: str | Sequence[str]) -> HttpResponse:
        """Return a copy whose ``name`` header holds ``value`` and nothing else.

        Args:
            name: The header name, in any case.
            value: One value, or every value the header is to hold.

        Returns:
            A new response; this one is left as it was.
        """
        return self._around(self._message.with_header(name, value))

    @override
    def with_added_header(self, name: str, value: str | Sequence[str]) -> HttpResponse:
        """Return a copy with ``value`` appended to the ``name`` header.

        Args:
            name: The header name, in any case.
            value: One value, or every value to append.

        Returns:
            A new response; this one is left as it was.
        """
        return self._around(self._message.with_added_header(name, value))

    @override
    def without_header(self, name: str) -> HttpResponse:
        """Return a copy with the ``name`` header gone.

        Args:
            name: The header name, in any case.

        Returns:
            A new response; this one is left as it was.
        """
        return self._around(self._message.without_header(name))

    @override
    def get_body(self) -> StreamInterface:
        """Return the body, which reads off the transfer as it is read.

        Returns:
            The one body of this transfer, shared by every copy of the
            response.
        """
        return self._body

    @override
    def with_body(self, body: StreamInterface) -> HttpResponse:
        """Return a copy reading its body from ``body`` instead.

        Args:
            body: The stream the copy is to read its body from, in place of
                the one coming off the transfer.

        Returns:
            A new response; this one is left as it was, still over the
            transfer's own body.
        """
        return self._around(self._message, body)

    @override
    def get_info(self, key: str | None = None) -> object:
        """Return what the transfer knows about itself, as it stands.

        The mapping handed back is a copy, so reading the info of a transfer
        still running cannot be disturbed by the transfer writing to it, and
        nothing a caller does to it reaches the transfer.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            Every entry when ``key`` is ``None``; otherwise the value under
            ``key``, or ``None`` when there is no such entry.
        """
        if key is None:
            return dict(self._info)
        return self._info.get(key)

    @override
    async def cancel(self) -> None:
        """Abandon the transfer and let go of what it was holding.

        The record is written before anything is let go of, so a reader that
        finds the body closed can be told why it is closed rather than only
        that it is.
        """
        self._info["canceled"] = True
        self._info["error"] = "Response has been canceled."

        if self._on_cancel is not None:
            await self._on_cancel()

        await self._body.close()

    @override
    async def get_content(self, throw: bool = True) -> bytes:
        """Read the whole body, waiting for the rest of it to arrive.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                answered with the body that came with it.

        Returns:
            Every byte of the body, empty when there was none.

        Raises:
            TransportError: When the body cannot be read — the transfer broke,
                or it was cancelled.
            RedirectionError: On a 3xx, when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        if throw:
            await self._check_status()

        try:
            return await self._body.get_contents()
        except RuntimeError as error:
            # A body that will not read only knows it is shut; the transfer
            # knows what shut it, and that is the half worth reporting.
            raise TransportError(self._recorded_error() or str(error)) from error

    @override
    async def to_array(self, throw: bool = True) -> dict[str, object]:
        """Read the whole body and decode it as a JSON object.

        Args:
            throw: Whether an unsuccessful status is to be raised rather than
                answered with the body that came with it.

        Returns:
            What the body decoded to.

        Raises:
            JsonError: When the body is empty, is not JSON, or is JSON that is
                not an object.
            TransportError: When the body cannot be read.
            RedirectionError: On a 3xx, when ``throw``.
            ClientError: On a 4xx, when ``throw``.
            ServerError: On a 5xx, when ``throw``.
        """
        content = await self.get_content(throw)
        url = self._info.get("url")

        if not content:
            raise JsonError("Response body is empty.")

        try:
            decoded = cast("object", json.loads(content))
        except ValueError as error:
            raise JsonError(f'{error} for "{url}".') from error

        if not isinstance(decoded, dict):
            raise JsonError(
                "JSON content was expected to decode to an array, "
                f'"{debug_type(decoded)}" returned for "{url}".'
            )

        # A decoded JSON object is keyed by strings; the cast says so once
        # rather than at every lookup the caller makes.
        return cast("dict[str, object]", decoded)

    @override
    async def __aenter__(self) -> Self:
        """Enter a block that owns the transfer.

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

        Leaving the block is not cancelling: the body is let go of, which
        frees the connection, but the transfer is not recorded as abandoned.

        Args:
            exc_type: The class of the exception the block is leaving with.
            exc: That exception.
            traceback: Its traceback.
        """
        del exc_type, exc, traceback
        await self._body.close()

    async def _check_status(self) -> None:
        """Raise the error the status code stands for, when it stands for one.

        Raises:
            RedirectionError: On a 3xx.
            ClientError: On a 4xx.
            ServerError: On a 5xx.
        """
        code = self._message.get_status_code()

        if code < _REDIRECTION:
            return
        if code < _CLIENT_ERROR:
            raise RedirectionError(self, await build_message(self))
        if code < _SERVER_ERROR:
            raise ClientError(self, await build_message(self))

        raise ServerError(self, await build_message(self))

    def _recorded_error(self) -> str | None:
        """Return what the transfer wrote down as having gone wrong, if anything."""
        error = self._info.get("error")
        return error if isinstance(error, str) else None

    def _around(self, message: Response, body: StreamInterface | None = None) -> HttpResponse:
        """Return a response of this kind around ``message``.

        Built field by field rather than through the constructor, because a
        copy may carry any stream as its body — :meth:`with_body` replaces it
        — where a new response is always given the one the transfer produces.

        Args:
            message: The message the copy answers from.
            body: The body the copy reads. ``None`` keeps this response's.

        Returns:
            The copy, sharing this response's info and its way of cancelling.
        """
        copy = HttpResponse.__new__(HttpResponse)
        copy._message = message  # noqa: SLF001 — a copy of this very class.
        copy._body = self._body if body is None else body  # noqa: SLF001 — likewise.
        copy._info = self._info  # noqa: SLF001 — likewise.
        copy._on_cancel = self._on_cancel  # noqa: SLF001 — likewise.

        return copy
