"""A backend fed by hand: one response, and whatever the test pushes to its transfer."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_http_message import Response

from xtr_http_client.chunk import DataChunk, LastChunk
from xtr_http_client.internal.transfer import Transfer
from xtr_http_client.response.http_client_response import HttpClientResponse

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

__all__ = ["URL", "FakeBackend", "FakeBackends"]

URL = "https://example.com/resource"


@final
class FakeBackend:
    """What a network backend does, done by the test holding this.

    It builds the response the way a backend does once the head is in — the
    message, the info, the transfer — and then the test pushes the body as it
    pleases. ``stopped`` tells whether the response asked the producer to
    stop, which is what cancelling and closing it are about.
    """

    def __init__(
        self,
        status: int = 200,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        *,
        buffered: bool = True,
        timeout: float = 60.0,
    ) -> None:
        message = Response(status, headers)
        self.stopped = False
        self.transfer = Transfer(timeout)
        self.transfer.on_cancel = self._stop
        head = [f"HTTP/1.1 {status} {message.get_reason_phrase()}"]
        head += [
            f"{name}: {line}" for name, lines in message.get_headers().items() for line in lines
        ]
        self.info: dict[str, object] = {
            "canceled": False,
            "error": None,
            "http_code": status,
            "http_method": "GET",
            "redirect_count": 0,
            "redirect_url": None,
            "response_headers": head,
            "start_time": 0.0,
            "url": URL,
            "user_data": None,
        }
        self.response = HttpClientResponse(message, self.info, self.transfer, buffered)

    def send(self, *pieces: bytes) -> None:
        """Push pieces of the body, each where the previous one ended."""
        for piece in pieces:
            self.transfer.push(DataChunk(self.transfer.offset, piece))

    def finish(self) -> None:
        """Push the end of the body."""
        self.transfer.push(LastChunk(self.transfer.offset))

    def answer(self, *pieces: bytes) -> HttpClientResponse:
        """Push a whole body at once, and hand over the response it belongs to."""
        self.send(*pieces)
        self.finish()
        return self.response

    def _stop(self) -> None:
        self.stopped = True


@final
class FakeBackends:
    """Makes fake backends, and closes every response they made once the test is over.

    A body being kept holds a temporary file, so a test that leaves a response
    open leaves the file behind too; closing them here is what leaving an
    ``async with`` block does in an application.
    """

    def __init__(self) -> None:
        self._made: list[FakeBackend] = []

    def make(
        self,
        status: int = 200,
        headers: Mapping[str, str | Sequence[str]] | None = None,
        *,
        buffered: bool = True,
        timeout: float = 60.0,
    ) -> FakeBackend:
        """Make a backend, answering with ``status`` and ``headers``."""
        backend = FakeBackend(status, headers, buffered=buffered, timeout=timeout)
        self._made.append(backend)
        return backend

    async def close(self) -> None:
        """Close the body of every response made."""
        for backend in self._made:
            await backend.response.get_body().close()
