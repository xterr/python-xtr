"""Several transfers read as one run of chunks."""

from __future__ import annotations

from collections.abc import AsyncIterable
from typing import Protocol, runtime_checkable

from .chunk_interface import ChunkInterface
from .response_interface import ResponseInterface

__all__ = ["ResponseStreamInterface"]


@runtime_checkable
class ResponseStreamInterface(
    AsyncIterable[tuple[ResponseInterface, ChunkInterface]],
    Protocol,
):
    """Chunks from any number of responses, each paired with the one it is from.

    What :meth:`HttpClientInterface.stream
    <xtr_http_client_contracts.http_client_interface.HttpClientInterface.stream>`
    hands back. Iterating it pulls from every response it was given at once
    and yields whatever arrives first, so a slow transfer never holds up a
    fast one:

    ```python
    async for response, chunk in client.stream(responses):
        if chunk.is_last():
            print(response.get_info("url"), "done")
    ```

    The run ends once every response has yielded its last chunk, or been
    cancelled. A response whose chunks nobody takes keeps holding its
    connection, so leave the loop by cancelling what is left rather than by
    walking away from it.

    It is declared as an ``AsyncIterable`` of pairs with ``__anext__`` of its
    own, which makes it its own iterator: ``async for`` works on it directly
    and what satisfies it is an async iterator by the standard library's
    reckoning too. Deriving from ``AsyncIterator`` instead would say the same
    thing, but a protocol cannot have it as a base before Python 3.14.
    """

    async def __anext__(self) -> tuple[ResponseInterface, ChunkInterface]:
        """Return the next pair, once there is one.

        Returns:
            The response a chunk arrived for, and the chunk.

        Raises:
            StopAsyncIteration: Once every response has finished.
            TransportError: When a transfer failed; a chunk's own accessors
                raise the same thing, so a reader that only asks the chunk
                what it is finds out either way.
        """
        ...
