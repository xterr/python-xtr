"""The strategy that retries a listed status code, waiting longer each time."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from random import uniform
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_http_client.exception import InvalidArgumentError

from .retry_strategy_interface import RetryStrategyInterface

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_http_client_contracts import TransportError

    from .retry_context import RetryContext

__all__ = ["DEFAULT_RETRY_STATUS_CODES", "IDEMPOTENT_METHODS", "GenericRetryStrategy"]

IDEMPOTENT_METHODS: Final[Sequence[str]] = (
    "GET",
    "HEAD",
    "PUT",
    "DELETE",
    "OPTIONS",
    "TRACE",
    "QUERY",
)
"""The methods a server answers the same way however often they are sent."""

DEFAULT_RETRY_STATUS_CODES: Final[Mapping[int, Sequence[str] | None]] = {
    # Nothing came back at all, which is what `0` stands for everywhere a
    # status code is read; only a method that may be sent twice is.
    0: IDEMPOTENT_METHODS,
    423: None,
    425: None,
    429: None,
    500: IDEMPOTENT_METHODS,
    502: None,
    503: None,
    504: IDEMPOTENT_METHODS,
    507: IDEMPOTENT_METHODS,
    510: IDEMPOTENT_METHODS,
}
"""What is retried out of the box: each code mapped to the methods it is
retried for, or to ``None`` when every method is."""

_StatusCodes = Mapping[int, Sequence[str] | None] | Sequence[int]


@final
class GenericRetryStrategy(RetryStrategyInterface):
    """Retries a status code on the list, after a delay that grows each time.

    The decision is the status code and, for the codes where it matters, the
    method: a 503 is the server saying "not now", so asking again is the
    right thing whatever was asked; a 500 after a `POST` may have changed
    something already, so sending it again is not.

    ```python
    strategy = GenericRetryStrategy([500, 502, 503], delay_ms=500)
    client = RetryableHttpClient(inner, strategy, max_retries=2)
    ```

    The delay starts at ``delay_ms`` and is multiplied by ``multiplier`` for
    every attempt already made, so the server is given more room each time
    rather than being asked again as fast as it refused. ``jitter`` spreads
    that over a window around it, which is what keeps a thousand clients that
    failed together from coming back together.
    """

    __slots__ = (
        "_delay_ms",
        "_jitter",
        "_max_delay_ms",
        "_multiplier",
        "_random",
        "_status_codes",
    )

    def __init__(  # noqa: PLR0913, PLR0917 — the five numbers of one backing-off delay, plus what is retried
        self,
        status_codes: _StatusCodes = DEFAULT_RETRY_STATUS_CODES,
        delay_ms: int = 1000,
        multiplier: float = 2.0,
        max_delay_ms: int = 0,
        jitter: float = 0.1,
        random: Callable[[float, float], float] = uniform,
    ) -> None:
        """Retry what ``status_codes`` lists, backing off between attempts.

        Args:
            status_codes: What to retry. A sequence of codes is every method
                for each of them; a mapping says, per code, which methods —
                ``None`` for all of them. ``0`` is the entry for an attempt
                nothing came back from.
            delay_ms: How long to wait before the second attempt, and what
                the growing delay starts from.
            multiplier: What the delay is multiplied by per attempt already
                made. ``1`` waits the same every time.
            max_delay_ms: The longest wait to allow. ``0`` sets no ceiling.
            jitter: How much of the delay is randomness, from ``0`` — none —
                to ``1``, where the wait lands anywhere from nothing to twice
                the delay.
            random: Where a number between two bounds comes from. Only worth
                passing to make a test's delays repeatable.

        Raises:
            InvalidArgumentError: When a delay is negative, the multiplier is
                below one, or the jitter is outside ``0`` to ``1``; each of them
                is a strategy that would wait for a length of time nobody
                meant.
        """
        if delay_ms < 0:
            raise InvalidArgumentError(
                f'Delay must be greater than or equal to zero: "{delay_ms}" given.'
            )
        if multiplier < 1:
            raise InvalidArgumentError(
                f'Multiplier must be greater than or equal to one: "{multiplier}" given.'
            )
        if max_delay_ms < 0:
            raise InvalidArgumentError(
                f'Max delay must be greater than or equal to zero: "{max_delay_ms}" given.'
            )
        if jitter < 0 or jitter > 1:
            raise InvalidArgumentError(f'Jitter must be between 0 and 1: "{jitter}" given.')

        self._status_codes = _listed(status_codes)
        self._delay_ms = delay_ms
        self._multiplier = multiplier
        self._max_delay_ms = max_delay_ms
        self._jitter = jitter
        self._random = random

    @override
    async def should_retry(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> bool | None:
        """Say whether the attempt's status code is one on the list.

        Never ``None``: the body says nothing about a status code, so this
        strategy never needs it to decide.

        Args:
            context: The attempt, whose status code and method are read.
            content: Ignored.
            error: What went wrong when nothing came back, which sends the
                decision to the ``0`` entry.

        Returns:
            Whether to try again.
        """
        del content

        code = context.get_status_code()
        if code in self._status_codes:
            return _allows(self._status_codes[code], context.method)
        if error is None:
            return False
        if 0 in self._status_codes:
            return _allows(self._status_codes[0], context.method)

        return False

    @override
    def get_delay(
        self,
        context: RetryContext,
        content: bytes | None,
        error: TransportError | None,
    ) -> int:
        """Return the delay for the next attempt, grown and spread out.

        Args:
            context: The attempt just made, whose ``retry_count`` is the
                power the multiplier is raised to.
            content: Ignored.
            error: Ignored.

        Returns:
            The wait in whole milliseconds, never above ``max_delay_ms``
            unless that is ``0``.
        """
        del content, error

        delay = self._delay_ms * self._multiplier**context.retry_count
        if self._jitter > 0:
            spread = int(delay * self._jitter)
            delay += self._random(-spread, spread)

        if self._max_delay_ms and delay > self._max_delay_ms:
            return self._max_delay_ms

        return int(delay)


def _listed(status_codes: _StatusCodes) -> Mapping[int, Sequence[str] | None]:
    """The codes to retry as one mapping, a bare sequence meaning every method."""
    if isinstance(status_codes, Mapping):
        return dict(status_codes)

    return dict.fromkeys(status_codes)


def _allows(methods: Sequence[str] | None, method: str) -> bool:
    """Whether a code's entry covers the method the attempt was made with."""
    return methods is None or method in methods
