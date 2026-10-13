"""A response whose head has arrived and whose body is on its way."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final, Self, cast, final

import anyio

from xtr_http_client.chunk.first_chunk import FirstChunk
from xtr_http_client.exception import (
    ClientError,
    HttpError,
    JsonError,
    RedirectionError,
    ServerError,
    TransportError,
)
from xtr_http_client.exception._http_error_message import build_message
from xtr_http_client.internal.debug_type import debug_type
from xtr_http_client.internal.response_body import ResponseBody
from xtr_http_client.internal.transfer import Transfer
from xtr_http_client.internal.transfer_source import TransferSource
from xtr_http_client.response.message_response_mixin import MessageResponseMixin
from xtr_http_client.response.response_stream import ResponseStream

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Iterable
    from types import TracebackType

    from xtr_http_client_contracts import ChunkInterface, ResponseInterface
    from xtr_http_message_contracts import ResponseInterface as MessageResponseInterface

__all__ = ["HttpClientResponse"]

_READ_TWICE: Final = "Cannot get the content of the response twice: buffering is disabled."

# What each class of unsuccessful status is raised as, by its first digit.
_ERRORS: Final[dict[int, type[HttpError]]] = {3: RedirectionError, 4: ClientError, 5: ServerError}


@final
class HttpClientResponse(MessageResponseMixin):
    """A response, the same whatever brought it in.

    Three things make one up: the message carrying its head, the transfer its
    body follows on, and the info the backend keeps about it. A backend builds
    one once the head is in and goes on pushing to the transfer; everything a
    caller asks of a response is answered here, alike for every backend.

    The body is read off the transfer by whichever reader asks first —
    ``get_body()``, :meth:`get_content`, :meth:`to_array` or a :meth:`stream`
    run — and what a run takes is handed to the body as well, so a body being
    kept stays whole however it was read.
    """

    __slots__ = ("_body", "_info", "_json", "_transfer")

    def __init__(
        self,
        message: MessageResponseInterface,
        info: dict[str, object],
        transfer: Transfer,
        buffered: bool,
    ) -> None:
        """Hold the head that arrived, the transfer the body follows on, and the info.

        Args:
            message: The status line and the headers. Its body is replaced by
                the one read off ``transfer``.
            info: The transfer info, shared with the backend so what it
                records later shows in :meth:`get_info`.
            transfer: Where the backend pushes the rest of the response.
            buffered: Whether the body is kept for a second read.
        """
        self._body = ResponseBody(TransferSource(transfer, info), buffered)
        super().__init__(message.with_body(self._body))
        self._info = info
        self._transfer = transfer
        self._json: dict[str, object] | None = None

    def get_info(self, key: str | None = None) -> object:
        """Return what the transfer knows about itself as it stands, or one entry of it."""
        info = dict(self._info)
        if info.get("error") is None and self._transfer.error is not None:
            info["error"] = self._transfer.error
        return info if key is None else info.get(key)

    async def get_content(self, throw: bool = True) -> bytes:
        """Read the whole body, waiting for the rest of it to arrive.

        Raises:
            TransportError: When the transfer failed or was canceled, or the
                body was read already and not kept.
            HttpError: For a 3xx, 4xx or 5xx, when ``throw``.
        """
        self._look()
        if throw:
            await self._check_status_code()
        if self._transfer.canceled:
            raise TransportError(Transfer.CANCELED)
        body = self._body
        await body.receive_all()
        content = await body.get_contents()
        if not content and not body.buffered:
            raise TransportError(_READ_TWICE)
        return content

    async def to_array(self, throw: bool = True) -> dict[str, object]:
        """Read the whole body and decode it as a JSON object, once when it is kept.

        Raises:
            JsonError: When the body is empty, not JSON, or not a JSON object.
        """
        content = await self.get_content(throw)
        if not content:
            raise JsonError("Response body is empty.")
        if self._json is not None:
            return self._json

        url = self._info.get("url")
        try:
            decoded = cast("object", json.loads(content))
        except ValueError as error:
            raise JsonError(f'{error} for "{url}".') from error
        if not isinstance(decoded, dict):
            raise JsonError(
                "JSON content was expected to decode to an array, "
                f'"{debug_type(decoded)}" returned for "{url}".'
            )

        document = cast("dict[str, object]", decoded)
        if self._body.buffered:
            self._json = document
        return document

    async def cancel(self) -> None:
        """Abandon the transfer; one whose end was already taken is left alone."""
        if self._transfer.finished:
            return
        self._info["canceled"] = True
        self._info["error"] = Transfer.CANCELED
        self._transfer.cancel()
        await self._body.close()

    async def __aenter__(self) -> Self:
        """Enter a block that owns the transfer."""
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Close the body, raising first for a 3xx-5xx nobody looked at."""
        try:
            if exc_type is None and not self._looked and self.get_info("error") is None:
                await self._check_status_code()
        finally:
            await self._body.close()

    @staticmethod
    def stream(
        responses: Iterable[ResponseInterface],
        timeout: float | None = None,
    ) -> ResponseStream:
        """Read several responses at once, chunk by chunk as they arrive.

        A run opens with the head of every response not yet announced, then
        hands over chunks as they arrive, taking one from each response in
        turn. A response leaves the run with its last chunk, with the failure
        that ended it, when it is canceled — saying nothing more — or when
        the run went quiet for ``timeout``: then every response still in it
        gets a timeout chunk, and a later run picks up where this one stopped.

        Args:
            responses: Responses made by this package's clients.
            timeout: How long the run may go quiet for, in seconds. ``None``
                takes the longest idle timeout among the responses.

        Raises:
            TypeError: When a response was not made by this package.
        """
        checked: list[HttpClientResponse] = []
        for response in responses:
            if not isinstance(response, HttpClientResponse):
                raise TypeError(
                    "HttpClientResponse.stream() expects responses made by this package, "
                    f'"{debug_type(response)}" given.'
                )
            checked.append(response)
        return ResponseStream(HttpClientResponse._run(list(dict.fromkeys(checked)), timeout))

    @staticmethod
    async def _run(
        responses: list[HttpClientResponse],
        idle: float | None,
    ) -> AsyncIterator[tuple[ResponseInterface, ChunkInterface]]:
        # Every response here is of this very class: a run is the class's own business.
        running = [(response, response._transfer) for response in responses]  # noqa: SLF001
        running = [(response, transfer) for response, transfer in running if not transfer.canceled]
        for response, _transfer in running:
            if (head := response._head()) is not None:  # noqa: SLF001 — see above.
                yield response, head
        if idle is None:
            idle = max((transfer.timeout for _response, transfer in running), default=0.0)

        while running:
            taken = 0
            for lane in list(running):
                response, transfer = lane
                chunk = await response._take()  # noqa: SLF001 — see above.
                if transfer.canceled or (chunk is not None and _leaves_run(chunk)):
                    running.remove(lane)
                if chunk is not None:
                    taken += 1
                    yield response, chunk
            if taken or not running:
                continue
            with anyio.move_on_after(idle):
                await Transfer.wait_any([transfer for _response, transfer in running])
                continue
            for response, transfer in running:
                yield response, transfer.idle_chunk(response.get_info("url"), idle)
            return

    def _head(self) -> FirstChunk | None:
        """Announce the head once, unless somebody has looked at it already."""
        if not self._first_pending:
            return None
        self._first_pending = False
        return FirstChunk()

    async def _take(self) -> ChunkInterface | None:
        """Take the next chunk for a run, and hand the body what it carries."""
        if self._transfer.canceled:
            return None
        chunk = self._transfer.take_ready()
        if chunk is None or chunk.get_error() is not None:
            return chunk
        if chunk.is_last():
            self._body.end()
        elif content := chunk.get_content():
            await self._body.feed(content)
        return chunk

    async def _check_status_code(self) -> None:
        """Raise what the status means for this request, when it is not a success."""
        error = _ERRORS.get(self._message.get_status_code() // 100)
        if error is not None:
            raise error(self, await build_message(self))


def _leaves_run(chunk: ChunkInterface) -> bool:
    """Tell whether a run is done with a response after ``chunk``."""
    return chunk.get_error() is not None or chunk.is_last()
