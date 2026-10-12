"""What posts the built bytes, behind which any HTTP client can stand."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from collections.abc import Mapping

__all__ = ["HttpSenderInterface"]


@runtime_checkable
class HttpSenderInterface(Protocol):
    """One POST, answered with a status code.

    This is the seam that keeps the transport free of any HTTP client: the
    transport decides what a delivery *means* — which url, which headers, what
    counts as accepted — while whatever implements this merely carries bytes.
    The client library then stays an optional dependency, reached only through
    the bridge that wraps it.
    """

    async def post(self, url: str, headers: Mapping[str, str], body: bytes) -> int:
        """Post ``body`` to ``url`` under ``headers``.

        Args:
            url: Where to post.
            headers: The headers to send, exactly as built — nothing added,
                nothing rewritten, or the signature over them breaks.
            body: The exact bytes to send, for the same reason.

        Returns:
            The status code the receiver answered with. Answered, not judged:
            what a status *means* for the delivery is the transport's call.
        """
        ...
