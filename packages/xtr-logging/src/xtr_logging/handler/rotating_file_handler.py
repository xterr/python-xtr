"""A file per day — or per any period — named from the record's date."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Final, final

from typing_extensions import override

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.level import Level

from .stream_handler import StreamHandler

if TYPE_CHECKING:
    from xtr_logging.level import LevelLike
    from xtr_logging.log_record import LogRecord

__all__ = ["RotatingFileHandler"]

_DATE_TOKEN: Final = "{date}"  # noqa: S105 — a template token, not a secret
_FILENAME_TOKEN: Final = "{filename}"  # noqa: S105 — a template token, not a secret
_STRFTIME_DIRECTIVE: Final = re.compile(r"%[a-zA-Z]")


@final
class RotatingFileHandler(StreamHandler):
    """Writes to a file whose name carries a date, switching when the date changes.

    The date comes from the record, not the wall clock, so a batch of records
    replayed from yesterday lands in yesterday's file. ``app.log`` with the
    default format becomes ``app-2026-09-24.log`` — the extension kept, the
    date spliced into the stem.

    When the date rolls over, the current file is closed and the next opened,
    and the directory is swept: the newest ``max_files`` files matching the
    pattern are kept and older ones deleted, unless ``max_files`` is zero,
    which keeps everything.
    """

    def __init__(  # noqa: PLR0913 — everything past `bubble` is keyword-only
        self,
        filename: str | os.PathLike[str],
        max_files: int = 0,
        level: LevelLike = Level.DEBUG,
        bubble: bool = True,
        *,
        date_format: str = "%Y-%m-%d",
        filename_format: str = "{filename}-{date}",
        file_permission: int | None = None,
    ) -> None:
        """Rotate ``filename`` daily, keeping the newest ``max_files`` of them.

        Args:
            filename: The base path; its stem and extension frame each dated file.
            max_files: How many dated files to keep; zero keeps them all.
            level: Handle records at this level or above.
            bubble: Let a handled record reach later handlers.
            date_format: A :meth:`~datetime.datetime.strftime` format for the date.
            filename_format: A template with ``{filename}`` and ``{date}``.
            file_permission: The mode to ``chmod`` each file created to.

        Raises:
            InvalidOptionError: If ``filename_format`` lacks ``{date}`` or
                ``date_format`` holds no strftime directive.
            InvalidLevelError: If ``level`` names no level.
        """
        _validate_formats(date_format, filename_format)
        super().__init__(os.fspath(filename), level, bubble, file_permission=file_permission)
        self._original: Path = Path(os.fspath(filename))
        self._max_files: int = max_files
        self._date_format: str = date_format
        self._filename_format: str = filename_format
        self._current_date: str | None = None

    @override
    def write(self, record: LogRecord, formatted: str) -> None:
        """Write to the file for the record's date, rotating first if it changed."""
        date = record.datetime.strftime(self._date_format)
        rotating = date != self._current_date
        if rotating:
            self.close()
            self._current_date = date
            self._target = self._timed_path(date)
        super().write(record, formatted)
        if rotating:
            self._collect()

    def _timed_path(self, date: str) -> str:
        name = self._filename_format.replace(_FILENAME_TOKEN, self._original.stem).replace(
            _DATE_TOKEN, date
        )
        return str(self._original.with_name(f"{name}{self._original.suffix}"))

    def _glob(self) -> str:
        name = self._filename_format.replace(_FILENAME_TOKEN, self._original.stem).replace(
            _DATE_TOKEN, "*"
        )
        return f"{name}{self._original.suffix}"

    def _collect(self) -> None:
        if self._max_files <= 0:
            return
        matches = sorted(self._original.parent.glob(self._glob()))
        for stale in matches[: -self._max_files]:
            stale.unlink(missing_ok=True)


def _validate_formats(date_format: str, filename_format: str) -> None:
    if _DATE_TOKEN not in filename_format:
        raise InvalidOptionError(
            "filename_format",
            filename_format,
            "must contain {date} or files could never rotate",
        )
    if _STRFTIME_DIRECTIVE.search(date_format) is None:
        raise InvalidOptionError(
            "date_format",
            date_format,
            "must hold a strftime directive such as %Y so the date varies",
        )
