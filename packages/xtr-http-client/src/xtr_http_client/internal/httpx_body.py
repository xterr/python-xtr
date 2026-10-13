"""The pieces of a response body, as they come off the backend transfer."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import anyio
import httpx

from .httpx_errors import timed_out, transport_error

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from typing import Self

__all__ = ["HttpxBody"]


@final
class HttpxBody:
    """The backend's body, with the two things a response body of this package needs.

    A deadline for the whole request covers the body as well as the head, and
    the body is read long after the request was made — wherever the caller
    asked for it — so the deadline has to travel with the body rather than
    stay where the request was. It is checked on every piece.

    And a transfer that breaks half way raises the backend's own error, which
    a caller holding the client interface has never heard of. Translating it
    here means every piece passes one place where that cannot escape.
    """

    __slots__ = ("_deadline", "_pieces", "_response", "_url")

    def __init__(
        self,
        response: httpx.Response,
        pieces: AsyncIterator[bytes],
        deadline: float | None = None,
    ) -> None:
        """Hold the transfer the body comes out of.

        Args:
            response: The transfer, which closing the body lets go of.
            pieces: The body, piece by piece, as the backend produces it.
            deadline: When the whole request runs out of time, on anyio's
                clock. ``None`` is no limit, which is what ``max_duration``
                of zero means.
        """
        self._response = response
        self._pieces = pieces
        self._deadline = deadline
        self._url = str(response.url)

    def __aiter__(self) -> Self:
        """Return this iterator, which is the body itself."""
        return self

    async def __anext__(self) -> bytes:
        """Return the next piece of the body, waiting for it to arrive.

        Returns:
            The piece, which may be of any size the transfer arrived in.

        Raises:
            StopAsyncIteration: Once the whole body has arrived.
            TransportTimeoutError: When the request ran out of time.
            TransportError: When the transfer broke.
        """
        try:
            with anyio.fail_after(self._remaining()):
                return await self._pieces.__anext__()
        except StopAsyncIteration:
            raise
        except TimeoutError as error:
            raise timed_out(self._url) from error
        except (httpx.HTTPError, httpx.InvalidURL) as error:
            raise transport_error(error, self._url) from error

    async def aclose(self) -> None:
        """Let go of the transfer, which frees the connection it was holding."""
        await self._response.aclose()

    def _remaining(self) -> float | None:
        """How long the request has left, or ``None`` when it was given no limit."""
        if self._deadline is None:
            return None
        return self._deadline - anyio.current_time()
