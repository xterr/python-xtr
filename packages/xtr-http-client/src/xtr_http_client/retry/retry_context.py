"""One attempt at a request, as whoever decides whether to repeat it sees it."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

if TYPE_CHECKING:
    from xtr_http_client_contracts import HttpResponseInterface, RequestOptions

__all__ = ["RetryContext"]


@final
@dataclass(frozen=True, slots=True)
class RetryContext:
    """What one attempt was made of, and what came back from it.

    Handed to a :class:`RetryStrategyInterface
    <xtr_http_client.retry.retry_strategy_interface.RetryStrategyInterface>`
    so it can decide on the attempt rather than on the request alone: the same
    503 is worth repeating on the first try and not on the fourth, and a
    method that may be sent twice is not every method.

    The request side is carried as it was sent — the URL resolved against the
    base URI this attempt used, the options merged — so a strategy reading
    them reads what actually went out.

    Attributes:
        method: The HTTP method the attempt was made with.
        url: The URL it was made to, as it was given to the wrapped client.
        options: The options it was made with, this attempt's ``base_uri``
            among them.
        retry_count: How many attempts came before this one, so ``0`` is the
            first.
        response: What came back, or ``None`` when nothing did and the
            attempt ended in a transport error.
    """

    method: str
    url: str
    options: RequestOptions
    retry_count: int
    response: HttpResponseInterface | None

    def get_status_code(self) -> int:
        """Return the status the attempt was answered with.

        Returns:
            The three-digit code, or ``0`` when nothing was answered — which
            is the same thing a response says before its status line arrives,
            so a strategy has one number to read either way.
        """
        if self.response is None:
            return 0

        return self.response.get_status_code()

    def get_info(self, key: str | None = None) -> object:
        """Return what the attempt's transfer knows about itself.

        Args:
            key: One entry to look up. ``None`` asks for all of them.

        Returns:
            What the response reports; with nothing to report — an attempt
            that ended in a transport error — every entry is empty and one
            entry is ``None``.
        """
        if self.response is None:
            return None if key is not None else {}

        return self.response.get_info(key)
