"""Whether a configured client makes a failed request again, and how."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, final

from xtr_http_client.exception import InvalidArgumentError

__all__ = ["RetryFailedConfig"]

_DELAY_MS: Final = 1000
_MULTIPLIER: Final = 2.0
_MAX_DELAY_MS: Final = 0
_JITTER: Final = 0.1


@final
@dataclass(frozen=True, slots=True)
class RetryFailedConfig:
    """The retrying layer of a configured client: off unless ``enabled``.

    What is retried, and how long is waited in between, is decided either by a
    :class:`~xtr_http_client.retry.GenericRetryStrategy` built from the numbers
    here, or by the strategy service ``retry_strategy`` names — one or the
    other, since numbers next to a service that ignores them would be settings
    that silently never apply.

    Attributes:
        enabled: Whether a failed request is made again.
        max_retries: How many further attempts a request may have.
        delay: How many milliseconds to wait before the first retry, and what
            the growing delay starts from.
        multiplier: What the delay is multiplied by per attempt already made.
        max_delay: The longest wait, in milliseconds; ``0`` sets no ceiling.
        jitter: How much of each delay is randomness, from ``0`` to ``1``.
        http_codes: The status codes retried, each mapped to the methods it is
            retried for — ``None`` for every method. ``None`` keeps the
            strategy's own list.
        base_uris: The base URIs each further attempt moves along, after the
            client's own ``base_uri``.
        retry_strategy: The qualifier of a
            :class:`~xtr_http_client.retry.RetryStrategyInterface` service
            deciding instead of the numbers above.
    """

    enabled: bool = False
    max_retries: int = 3
    delay: int = _DELAY_MS
    multiplier: float = _MULTIPLIER
    max_delay: int = _MAX_DELAY_MS
    jitter: float = _JITTER
    http_codes: Mapping[int, Sequence[str] | None] | None = None
    base_uris: Sequence[str] = ()
    retry_strategy: str | None = None

    def __post_init__(self) -> None:
        """Refuse fallback URIs nothing retries towards, and numbers a strategy service ignores.

        Raises:
            InvalidArgumentError: When the configuration cannot be used.
        """
        if self.base_uris and not self.enabled:
            raise InvalidArgumentError('The "base_uris" option requires retries to be enabled.')
        tuned = (self.http_codes, self.delay, self.multiplier, self.max_delay, self.jitter) != (
            None,
            _DELAY_MS,
            _MULTIPLIER,
            _MAX_DELAY_MS,
            _JITTER,
        )
        if self.retry_strategy is not None and tuned:
            raise InvalidArgumentError(
                'The "retry_strategy" option cannot be used along with the "http_codes", '
                '"delay", "multiplier", "max_delay" or "jitter" options.'
            )
