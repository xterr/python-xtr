"""Writing formatted records to a file or an open stream."""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from typing_extensions import override
from xtr_logging_contracts import Level

from .abstract_processing_handler import AbstractProcessingHandler

if TYPE_CHECKING:
    from typing import Literal, TextIO

    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

__all__ = ["StreamHandler"]


class StreamHandler(AbstractProcessingHandler):
    """Writes each formatted record to a stream, flushing as it goes.

    Given an open stream it writes there and leaves closing to the caller.
    Given a path it opens the file on the first record — creating parent
    directories, and setting ``file_permission`` on a file it creates — so a
    handler configured for a path that is never logged to touches nothing.

    A lock serialises writes, so two threads logging at once cannot splice one
    line inside another. :meth:`close` closes only a file this handler opened;
    the next record reopens it.
    """

    def __init__(  # noqa: PLR0913 — everything past `bubble` is keyword-only
        self,
        stream: TextIO | str | os.PathLike[str],
        level: LevelLike = Level.DEBUG,
        bubble: bool = True,
        *,
        file_permission: int | None = None,
        mode: Literal["a", "w", "x"] = "a",
        encoding: str = "utf-8",
    ) -> None:
        """Write to ``stream`` — an open stream, or a path opened on first use.

        Args:
            stream: An open text stream, or the path of a file to open.
            level: Handle records at this level or above.
            bubble: Let a handled record reach later handlers.
            file_permission: The mode to ``chmod`` a file this handler creates
                to; left at the system default when omitted.
            mode: How to open a path — append, truncate, or create-exclusive.
            encoding: How to encode text written to a path.

        Raises:
            InvalidLevelError: If ``level`` names no level.
        """
        super().__init__(level, bubble)
        if isinstance(stream, (str, os.PathLike)):
            self._target: TextIO | str = os.fspath(stream)
            self._stream: TextIO | None = None
        else:
            self._target = stream
            self._stream = stream
        self._file_permission: int | None = file_permission
        self._mode: Literal["a", "w", "x"] = mode
        self._encoding: str = encoding
        self._lock: threading.Lock = threading.Lock()

    @property
    def url(self) -> str | None:
        """The path this handler writes to, or ``None`` if it was given a stream."""
        return self._target if isinstance(self._target, str) else None

    @property
    def stream(self) -> TextIO | None:
        """The open stream, or ``None`` before the first write or after :meth:`close`."""
        return self._stream

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write ``formatted`` to the stream, opening a configured path if need be."""
        with self._lock:
            stream = self._resolve_stream()
            _ = stream.write(formatted)
            stream.flush()

    @override
    def close(self) -> None:
        """Close a file this handler opened; leave a stream it was handed alone."""
        with self._lock:
            if isinstance(self._target, str) and self._stream is not None:
                self._stream.close()
                self._stream = None

    def _resolve_stream(self) -> TextIO:
        if self._stream is not None:
            return self._stream
        target = self._target
        if isinstance(target, str):
            self._stream = self._open_file(target)
            return self._stream
        # A handed-in stream is kept for the handler's life; caching it here is
        # only reached if it was never cached at construction, and stays open.
        self._stream = target
        return target

    def _open_file(self, path_str: str) -> TextIO:
        path = Path(path_str)
        existed = path.exists()
        path.parent.mkdir(parents=True, exist_ok=True)
        stream = path.open(self._mode, encoding=self._encoding)
        if self._file_permission is not None and not existed:
            path.chmod(self._file_permission)
        return stream
