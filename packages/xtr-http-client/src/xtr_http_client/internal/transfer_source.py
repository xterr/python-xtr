"""A body's way into the transfer it comes out of."""

from __future__ import annotations

from typing import TYPE_CHECKING, Self, final

import anyio

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_http_client_contracts import ChunkInterface

    from xtr_http_client.internal.transfer import Transfer

__all__ = ["TransferSource"]


@final
class TransferSource:
    """The pieces of a body, taken off its transfer as the body asks for them.

    What a response gives its body to read from. Each piece is waited for no
    longer than the transfer's idle timeout: running out of it raises
    :class:`TransportTimeoutError
    <xtr_http_client_contracts.exception.transport_timeout_error.TransportTimeoutError>`
    and takes nothing, so the next read carries on where this one stopped. A
    failed transfer raises its failure on every read; one that ended ends the
    iteration.

    Closing it lets go of the transfer, stopping one that is still arriving:
    a body nobody will read has no use for the rest of it.
    """

    __slots__ = ("_info", "_transfer")

    def __init__(self, transfer: Transfer, info: Mapping[str, object]) -> None:
        """Read off ``transfer``, naming the URL in ``info`` when it goes quiet."""
        self._transfer = transfer
        self._info = info

    def __aiter__(self) -> Self:
        """Return this source, which is its own iterator."""
        return self

    async def __anext__(self) -> bytes:
        """Return the next piece of the body, once it has arrived.

        Raises:
            StopAsyncIteration: Once the body is complete.
            TransportTimeoutError: When nothing arrived for the idle timeout.
            TransportError: When the transfer failed.
        """
        transfer = self._transfer
        while True:
            chunk: ChunkInterface | None = None
            with anyio.move_on_after(transfer.timeout):
                chunk = await transfer.next_chunk()
            if chunk is None:
                chunk = transfer.idle_chunk(self._info.get("url"), transfer.timeout)
            # An error chunk raises from here, whether it is a timeout or a failure.
            if chunk.is_last():
                raise StopAsyncIteration
            content = chunk.get_content()
            if content:
                return content

    async def aclose(self) -> None:
        """Let go of the transfer, stopping it if it is still arriving."""
        self._transfer.cancel()
