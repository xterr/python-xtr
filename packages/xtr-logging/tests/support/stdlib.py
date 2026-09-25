"""Standard-library logging state that a test may change and must give back."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Iterator


@final
class Collector(logging.Handler):
    """A standard-library handler that keeps what it is given — a stand-in for a console."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    @override
    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)

    @property
    def messages(self) -> list[str]:
        return [record.getMessage() for record in self.records]


@dataclass(frozen=True, slots=True)
class _State:
    handlers: tuple[logging.Handler, ...]
    level: int
    propagate: bool
    disabled: bool


def _loggers() -> list[logging.Logger]:
    found = [
        candidate
        for candidate in logging.Logger.manager.loggerDict.values()
        if isinstance(candidate, logging.Logger)
    ]
    return [logging.getLogger(), *found]


def preserved_stdlib_logging() -> Iterator[None]:
    """Snapshot every standard logger, then put each back after the test."""
    saved = {
        logger: _State(tuple(logger.handlers), logger.level, logger.propagate, logger.disabled)
        for logger in _loggers()
    }
    yield
    for logger in _loggers():
        state = saved.get(logger)
        if state is None:
            logger.handlers = []
            logger.setLevel(logging.NOTSET)
            logger.propagate = True
            logger.disabled = False
            continue
        logger.handlers = list(state.handlers)
        logger.setLevel(state.level)
        logger.propagate = state.propagate
        logger.disabled = state.disabled
