"""Keep a random fraction of a flood, when a rough idea is enough."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_logging.exception.invalid_option_error import InvalidOptionError

from ._lazy_handler import LazyHandler
from ._processor_stack import ProcessorStack
from .abstract_handler import AbstractHandler

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import TypeAlias

    from xtr_logging.log_record import LogRecord

    from .handler_interface import HandlerInterface

    _HandlerFactory: TypeAlias = Callable[
        ["LogRecord | None", "SamplingHandler"],
        HandlerInterface,
    ]

__all__ = ["SamplingHandler"]


@final
class SamplingHandler(AbstractHandler, ProcessorStack, LazyHandler):
    """Forwards roughly one record in ``factor`` and drops the rest.

    A high-frequency event does not need every occurrence logged; sampling
    keeps the volume — and the cost of the wrapped handler — down while still,
    by the law of large numbers, reflecting what is happening. The decision is
    random per record, so the sampled stream is approximate, not every Nth.

    The random source is injected so a test can seed it and know exactly which
    records survive.
    """

    def __init__(
        self,
        handler: HandlerInterface | _HandlerFactory,
        factor: int,
        bubble: bool = True,
        *,
        rng: random.Random | None = None,
    ) -> None:
        """Sample about one record in ``factor`` for ``handler``.

        Args:
            handler: The handler sampled records are forwarded to, or a factory.
            factor: The sampling divisor; ``1`` keeps everything, ``10`` keeps
                about a tenth.
            bubble: Let a sampled record reach later handlers.
            rng: The random source; a fresh :class:`random.Random` by default.

        Raises:
            InvalidOptionError: If ``factor`` is less than ``1``.
        """
        super().__init__(bubble=bubble)
        if factor < 1:
            raise InvalidOptionError("factor", str(factor), "must be 1 or greater to sample")
        self._wrap(handler)
        self._factor: int = factor
        self._rng: random.Random = rng if rng is not None else random.Random()  # noqa: S311 — sampling, not security

    @override
    def is_handling(self, record: LogRecord, /) -> bool:
        """Whether the wrapped handler would handle ``record`` at all.

        ``True`` while it is still to be built: sampling decides first, so a
        dropped record never costs building it.
        """
        return self._wrapped is None or self._wrapped.is_handling(record)

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Forward ``record`` with probability ``1 / factor``; drop it otherwise."""
        if self.is_handling(record) and self._rng.randint(1, self._factor) == 1:
            record = self._process(record)
            handler = self._resolve_handler(record)
            if handler.is_handling(record):
                _ = handler.handle(record)
        return not self._bubble

    @override
    def reset(self) -> None:
        """Reset this handler's processors and the wrapped handler."""
        self._reset_processors()
        self._reset_handler()

    @override
    def close(self) -> None:
        """Close the wrapped handler."""
        self._close_handler()
