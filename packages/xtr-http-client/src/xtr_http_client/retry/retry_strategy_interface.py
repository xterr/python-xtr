"""What decides whether a request is worth making again, and how long to wait."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from xtr_http_client_contracts import TransportError

    from .retry_context import RetryContext

__all__ = ["RetryStrategyInterface"]


@runtime_checkable
class RetryStrategyInterface(Protocol):
    """The two questions a retrying client asks itself after an attempt.

    Whether to try again is one decision, how long to wait before doing so is
    another, and they are asked separately because a strategy that answers the
    first often has nothing of its own to say about the second.
    :class:`RetryableHttpClient
    <xtr_http_client.retryable_http_client.RetryableHttpClient>` asks both.
    """

    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        """Say whether the attempt in ``context`` is worth making again.

        ``None`` is the third answer: "not without the body". The client then
        reads the whole body and asks again with it — once. Answering ``None``
        a second time is a strategy that cannot decide, and is reported as
        such rather than taken for a "no".

        Args:
            context: The attempt, and whatever came back from it.
            content: The whole body, once the client has read it because this
                method asked for it. ``None`` the first time round, and
                whenever the attempt ended in a transport error, where there
                is no body to read.
            error: What went wrong when nothing came back, or ``None`` when
                something did.

        Returns:
            ``True`` to try again, ``False`` to hand back what came back, or
            ``None`` to be asked again with the body.
        """
        ...

    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        """Return how long to wait before the next attempt, in milliseconds.

        Only asked when the answer has not already been given by the server: a
        ``Retry-After`` header is obeyed over this.

        Args:
            context: The attempt just made, whose ``retry_count`` is what a
                backing-off delay grows with.
            content: The body, when it was read to make the decision.
            error: What went wrong when nothing came back.

        Returns:
            The wait in milliseconds; ``0`` to try again at once.
        """
        ...
