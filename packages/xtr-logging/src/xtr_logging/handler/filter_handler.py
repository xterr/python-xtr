"""Let only a chosen band of levels through to the wrapped handler."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_logging_contracts import Level
from xtr_service_contracts import ResetInterface

from ._lazy_handler import LazyHandler
from ._processor_stack import ProcessorStack
from .handler_interface import HandlerInterface

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from typing import TypeAlias

    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

    _HandlerFactory: TypeAlias = Callable[
        ["LogRecord | None", "FilterHandler"],
        HandlerInterface,
    ]

__all__ = ["FilterHandler"]


@final
class FilterHandler(ProcessorStack, LazyHandler, HandlerInterface, ResetInterface):
    """Forwards only records whose level is in an accepted set.

    A handler's minimum level lets everything above it through; this instead
    carves out a band — a file of just notices and warnings, say, with errors
    left to a handler that pages someone. Give it a min/max pair or an explicit
    list of levels.

    The wrapped handler may be a factory ``handler(record, self)``, resolved
    and cached the first time a record actually needs it.
    """

    def __init__(
        self,
        handler: HandlerInterface | _HandlerFactory,
        min_level_or_list: LevelLike | Sequence[LevelLike] = Level.DEBUG,
        max_level: LevelLike = Level.EMERGENCY,
        bubble: bool = True,
    ) -> None:
        """Wrap ``handler``, accepting a band or a list of levels.

        Args:
            handler: The handler forwarded to, or a factory that builds it.
            min_level_or_list: The lowest level to accept, or an explicit list
                of the only levels to accept.
            max_level: The highest level to accept; ignored when a list was
                given.
            bubble: Whether accepted records still reach later handlers.

        Raises:
            InvalidLevelError: If any level names no level.
        """
        self._wrap(handler)
        self._bubble: bool = bubble
        self._accepted_levels: frozenset[Level] = frozenset()
        self.set_accepted_levels(min_level_or_list, max_level)

    @property
    def accepted_levels(self) -> tuple[Level, ...]:
        """The levels let through, least severe first."""
        return tuple(sorted(self._accepted_levels))

    def set_accepted_levels(
        self,
        min_level_or_list: LevelLike | Sequence[LevelLike] = Level.DEBUG,
        max_level: LevelLike = Level.EMERGENCY,
    ) -> None:
        """Accept a band from ``min_level_or_list`` to ``max_level``, or an exact list.

        Raises:
            InvalidLevelError: If any level names no level.
        """
        if isinstance(min_level_or_list, (str, int)):
            minimum = Level.parse(min_level_or_list)
            maximum = Level.parse(max_level)
            self._accepted_levels = frozenset(
                level for level in Level if minimum <= level <= maximum
            )
        else:
            self._accepted_levels = frozenset(Level.parse(item) for item in min_level_or_list)

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether ``record``'s level is one this handler accepts."""
        return record.level in self._accepted_levels

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Forward ``record`` if its level is accepted, after this handler's processors."""
        if not self.is_handling(record):
            return False
        record = self._process(record)
        _ = self._resolve_handler(record).handle(record)
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Forward the accepted records of ``records`` as one batch."""
        accepted = tuple(record for record in records if self.is_handling(record))
        if accepted:
            self._resolve_handler(accepted[-1]).handle_batch(accepted)

    @override
    def reset(self) -> None:
        """Reset this handler's processors and the wrapped handler."""
        self._reset_processors()
        self._reset_handler()

    @override
    def close(self) -> None:
        """Close the wrapped handler."""
        self._close_handler()
