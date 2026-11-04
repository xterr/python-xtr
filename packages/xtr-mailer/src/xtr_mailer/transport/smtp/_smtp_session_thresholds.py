"""When an SMTP transport checks its session is alive, and after how many emails it restarts it."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Self

__all__ = ["SmtpSessionThresholds"]


class SmtpSessionThresholds:
    """The ping and restart thresholds of a transport's sessions; the transport acts on them."""

    _restart_threshold: int = 100
    _restart_threshold_sleep: float = 0.0
    _ping_threshold: float = 100.0

    def set_restart_threshold(self, threshold: int, sleep: float = 0) -> Self:
        """End the session after ``threshold`` emails, ``0`` never; wait ``sleep`` seconds then."""
        self._restart_threshold = threshold
        self._restart_threshold_sleep = sleep
        return self

    def set_ping_threshold(self, seconds: float) -> Self:
        """``NOOP`` before an email idle over ``seconds`` (100); servers drop chatty sessions."""
        self._ping_threshold = seconds
        return self
