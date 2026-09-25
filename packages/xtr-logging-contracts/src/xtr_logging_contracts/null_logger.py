"""A logger that discards everything."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .abstract_logger import AbstractLogger

if TYPE_CHECKING:
    from .context import Context
    from .level import LevelLike

__all__ = ["NullLogger"]


@final
class NullLogger(AbstractLogger):
    """Discards everything it is given.

    The default for a library that accepts a logger: logging stays optional
    for its callers, and the library's code never has to ask whether it has
    one.
    """

    __slots__ = ()

    @override
    def log(self, level: LevelLike, message: str, /, context: Context | None = None) -> None:
        """Do nothing — not even check ``level``, which costs a call site nothing."""
        del level, message, context
