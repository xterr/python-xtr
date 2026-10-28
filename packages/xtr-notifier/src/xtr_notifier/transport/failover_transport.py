"""Several transports, the next used only when the current one fails."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .round_robin_transport import RoundRobinTransport

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_clock import ClockInterface

    from xtr_notifier.message import MessageInterface

    from .transport_interface import TransportInterface

__all__ = ["FailoverTransport"]


@final
class FailoverTransport(RoundRobinTransport):
    """Sends through the first transport until it fails, then the next: ``a || b``.

    Sticks with a transport while it works, so one provider takes every message
    and the others are a fallback; a dead one is tried again once its
    ``retry_period`` is over and the transport in use fails in turn.
    """

    def __init__(
        self,
        transports: Sequence[TransportInterface],
        retry_period: float = 60,
        clock: ClockInterface | None = None,
    ) -> None:
        """Fall over between ``transports``, in order.

        Args:
            transports: The transports, most preferred first.
            retry_period: How many seconds a dead transport is skipped for.
            clock: What a dead transport's rest is measured on.

        Raises:
            LogicError: If ``transports`` is empty.
        """
        super().__init__(transports, retry_period, clock)
        self._current: int | None = None

    @override
    def _get_next_transport(self, message: MessageInterface) -> int | None:
        """Keep the transport in use until it is dead, then move to the next live one."""
        if self._current is None or self._is_transport_dead(self._current):
            self._current = super()._get_next_transport(message)
        return self._current

    @override
    def _get_initial_cursor(self) -> int:
        """Start at the first transport: the order is a preference."""
        return 0

    @override
    def _get_name_symbol(self) -> str:
        """Join with ``||``, the DSN operator that builds a failover."""
        return "||"
