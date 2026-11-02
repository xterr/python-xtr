"""Several transports, the next used only when the current one fails."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .round_robin_transport import RoundRobinTransport

if TYPE_CHECKING:
    from collections.abc import Sequence
    from collections.abc import Set as AbstractSet

    from xtr_clock import ClockInterface
    from xtr_logging_contracts import LoggerInterface

    from .transport_interface import TransportInterface

__all__ = ["FailoverTransport"]


@final
class FailoverTransport(RoundRobinTransport):
    """Sends through the first transport until it fails, then the next: ``failover(a b)``.

    Sticks with a transport while it works, so one server takes every email and the others are
    a fallback. A dead one is tried again once its ``retry_period`` is over and the transport in
    use fails in turn. Errors, cancellations and overlapping sends are handled as
    :class:`RoundRobinTransport` handles them.
    """

    def __init__(
        self,
        transports: Sequence[TransportInterface],
        retry_period: float = 60,
        *,
        logger: LoggerInterface | None = None,
        clock: ClockInterface | None = None,
    ) -> None:
        """Fall over between ``transports``, in order.

        Args:
            transports: The transports, most preferred first.
            retry_period: How many seconds a dead transport is skipped for.
            logger: Where each failure of a transport is logged; ``None`` logs nothing.
            clock: What a dead transport's rest is measured on.

        Raises:
            TransportError: ``transports`` is empty.
        """
        super().__init__(transports, retry_period, logger=logger, clock=clock)
        self._current: TransportInterface | None = None

    @override
    def _get_next_transport(self, tried: AbstractSet[int]) -> TransportInterface | None:
        """Keep the transport in use until it is dead, then move to the next live one.

        One the current send tried already is passed over even when another send revived it.
        """
        current = self._current
        if current is None or self._is_transport_dead(current) or id(current) in tried:
            self._current = super()._get_next_transport(tried)
        return self._current

    @override
    def _get_initial_cursor(self) -> int:
        """Start at the first transport: the order is a preference."""
        return 0

    @override
    def _get_name_symbol(self) -> str:
        """Return ``failover``, the DSN group that builds this transport."""
        return "failover"
