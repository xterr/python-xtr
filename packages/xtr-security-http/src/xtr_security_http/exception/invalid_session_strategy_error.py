"""A session strategy was configured under a name it does not answer to."""

from __future__ import annotations

from xtr_security_core.exception import SecurityError

__all__ = ["InvalidSessionStrategyError"]


class InvalidSessionStrategyError(SecurityError, RuntimeError):
    """A session strategy was asked to act under a name that is none of its own.

    The strategy names — none, migrate, invalidate — are the
    application's configuration, carried as a string; one that matches
    no name is heard the first time the strategy runs, carrying the name
    as it was configured. Also a :class:`RuntimeError`.
    """

    _strategy: str

    def __init__(self, strategy: str) -> None:
        """Record the unknown strategy name.

        Args:
            strategy: The configured strategy name that matched none of
                the strategy's own.
        """
        super().__init__(f'Invalid session authentication strategy "{strategy}".')
        self._strategy = strategy

    def get_strategy(self) -> str:
        """Return the configured strategy name that matched none of the strategy's own."""
        return self._strategy
