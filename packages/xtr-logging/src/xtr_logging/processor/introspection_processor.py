"""Adds where in the code a record was logged: file, line, function, module."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.level import Level

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from collections.abc import Sequence
    from types import FrameType

    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["IntrospectionProcessor"]

_INTERNAL_PREFIX: Final = "xtr_logging"


@final
class IntrospectionProcessor(ProcessorInterface):
    """Adds ``extra["file"]``, ``"line"``, ``"function"`` and ``"module"``.

    Points at the code that logged, not at this library: frames inside
    ``xtr_logging`` — and any module prefix you name — are walked past, so the
    record shows the caller's own file and line. Skipping the walk below a level
    keeps its cost off the records a busy channel makes most of.
    """

    __slots__ = ("_level", "_prefixes", "_skip_frames")

    def __init__(
        self,
        level: LevelLike = Level.DEBUG,
        *,
        skip_module_prefixes: Sequence[str] = (),
        skip_frames: int = 0,
    ) -> None:
        """Introspect records at ``level`` or above.

        Args:
            level: Records below this are returned untouched.
            skip_module_prefixes: Module prefixes to walk past in addition to
                this library's own, for a wrapper between a caller and the
                logger.
            skip_frames: Frames to step over after the first outside frame, for
                a caller that is itself one frame removed.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        self._level: Level = Level.parse(level)
        self._prefixes: tuple[str, ...] = (_INTERNAL_PREFIX, *skip_module_prefixes)
        self._skip_frames: int = skip_frames

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with its origin in ``extra``, if it is at ``level``."""
        if record.level.is_lower_than(self._level):
            return record
        frame = inspect.currentframe()
        try:
            while frame is not None and self._is_internal(frame):
                frame = frame.f_back
            for _ in range(self._skip_frames):
                if frame is None:
                    break
                frame = frame.f_back
            if frame is None:
                return record
            code = frame.f_code
            module: object = frame.f_globals.get("__name__")
            return record.with_extra(
                {
                    "file": code.co_filename,
                    "line": frame.f_lineno,
                    "function": code.co_qualname,
                    "module": module,
                }
            )
        finally:
            del frame

    def _is_internal(self, frame: FrameType) -> bool:
        module: object = frame.f_globals.get("__name__")
        return isinstance(module, str) and module.startswith(self._prefixes)
