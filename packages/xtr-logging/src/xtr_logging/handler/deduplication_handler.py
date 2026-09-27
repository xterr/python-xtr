"""Buffer records, then suppress ones that were already sent moments ago."""

from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING, final

from typing_extensions import override
from xtr_clock import Clock
from xtr_logging_contracts import Level

from .buffer_handler import BufferHandler

if TYPE_CHECKING:
    from xtr_clock import ClockInterface
    from xtr_logging_contracts import LevelLike

    from xtr_logging.log_record import LogRecord

    from .handler_interface import HandlerInterface

__all__ = ["DeduplicationHandler"]

_ONE_DAY_SECONDS = 86400
_PRIVATE_MODE = 0o700
_STORE_FIELDS = 3


@final
class DeduplicationHandler(BufferHandler):
    """Stops the same alert going out twice when one failure floods the logs.

    A database going down can fail every request the same way; without this a
    mail or chat handler would send the identical error hundreds of times.
    Records are buffered like :class:`BufferHandler`, and on flush each one at
    or above ``deduplication_level`` is checked against a small file of what
    was recently sent — matched by level and first line of message, within
    ``time`` seconds. The batch goes out whole, with the records below that
    level that explain it, when any of them is new or none reaches the level;
    it is dropped whole when every one of them is a repeat.

    The store defaults to a file named after the wrapped handler — its class,
    level and target — in a directory of the temporary one made for this user
    alone: another user can neither read what was sent nor plant a file there.
    One owned by someone else is not used, and nothing is deduplicated. Give
    ``store`` an explicit path shared across processes so a burst spread over
    many workers is still deduplicated. The clock is injected so a test can
    decide what "recently" means.

    Records are held until a flush, all of them unless ``buffer_limit`` caps
    how many, the oldest dropped past it — or everything forwarded, with
    ``flush_on_overflow``.
    """

    def __init__(  # noqa: PLR0913 — every option is independent; all have defaults
        self,
        handler: HandlerInterface,
        store: str | os.PathLike[str] | None = None,
        deduplication_level: LevelLike = Level.ERROR,
        time: int = 60,
        bubble: bool = True,
        *,
        clock: ClockInterface | None = None,
        buffer_limit: int = 0,
        flush_on_overflow: bool = False,
    ) -> None:
        """Deduplicate what ``handler`` sends.

        Args:
            handler: The handler whose output is deduplicated.
            store: The file recording what was recently sent; a temp-directory
                default is used when ``None``.
            deduplication_level: Only records at this level or above are
                considered for suppression.
            time: How many seconds a record suppresses later duplicates of
                itself.
            bubble: Whether buffered records still reach later handlers.
            clock: Where "now" is read from, for expiry; the clock in force
                by default.
            buffer_limit: The most records held until a flush; ``0`` holds
                them all.
            flush_on_overflow: Forward the held records when ``buffer_limit``
                is reached, rather than dropping the oldest.

        Raises:
            InvalidLevelError: If ``deduplication_level`` names no level.
        """
        super().__init__(
            handler, buffer_limit, Level.DEBUG, bubble, flush_on_overflow=flush_on_overflow
        )
        self._private: bool = store is None
        self._store_path: Path = Path(store) if store is not None else _default_store(handler)
        self._deduplication_level: Level = Level.parse(deduplication_level)
        self._time: int = time
        self._clock: ClockInterface = clock if clock is not None else Clock()
        self._gc: bool = False

    @override
    def _forward(self, records: list[LogRecord]) -> None:
        """Forward ``records``, unless every one at the deduplication level is a repeat."""
        store = self._read_store()
        passthru: bool | None = None
        for record in records:
            if record.level >= self._deduplication_level:
                passthru = (
                    passthru is True or store is None or not self._is_duplicate(store, record)
                )
                if passthru:
                    line = self._build_entry(record)
                    self._append_store(line)
                    if store is None:
                        store = []
                    store.append(line)
        if passthru is True or passthru is None:
            self._handler.handle_batch(tuple(records))
        if self._gc:
            self._collect_logs()

    def _is_duplicate(self, store: list[str], record: LogRecord) -> bool:
        newer_than = int(record.datetime.timestamp()) - self._time
        expected = _first_line(record.message)
        yesterday = int(self._clock.now().timestamp()) - _ONE_DAY_SECONDS
        for line in reversed(store):
            parts = line.split(":", _STORE_FIELDS - 1)
            if len(parts) < _STORE_FIELDS:
                continue
            timestamp = _parse_timestamp(parts[0])
            if timestamp is None:
                continue
            if parts[1] == record.level.name and parts[2] == expected and timestamp > newer_than:
                return True
            if timestamp < yesterday:
                self._gc = True
        return False

    def _build_entry(self, record: LogRecord) -> str:
        return (
            f"{int(record.datetime.timestamp())}:{record.level.name}:{_first_line(record.message)}"
        )

    def _read_store(self) -> list[str] | None:
        if not self._store_path.exists() or not self._trusted():
            return None
        return [line for line in self._store_path.read_text(encoding="utf-8").splitlines() if line]

    def _append_store(self, line: str) -> None:
        if not self._trusted():
            return
        with self._store_path.open("a", encoding="utf-8") as store:
            _ = store.write(line + "\n")

    def _trusted(self) -> bool:
        """Tell whether the store may be read and written: an explicit one always is.

        The default one's directory is made for this user alone, and is
        refused when it belongs to someone else.
        """
        if not self._private:
            return True
        return _private_directory(self._store_path.parent)

    def _collect_logs(self) -> None:
        if not self._store_path.exists() or not self._trusted():
            return
        validity = int(self._clock.now().timestamp()) - self._time
        kept: list[str] = []
        for line in self._store_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            timestamp = _parse_timestamp(line.split(":", 1)[0])
            if timestamp is not None and timestamp >= validity:
                kept.append(line)
        _ = self._store_path.write_text("".join(f"{line}\n" for line in kept), encoding="utf-8")
        self._gc = False


def _default_store(handler: HandlerInterface) -> Path:
    """Return the store of what ``handler`` sent: one per class, level and target it has."""
    kind = type(handler)
    seed = "|".join(
        (
            f"{kind.__module__}.{kind.__qualname__}",
            str(getattr(handler, "level", "")),
            str(getattr(handler, "url", "")),
        )
    )
    digest = hashlib.sha256(seed.encode()).hexdigest()[:20]
    owner = getattr(os, "getuid", lambda: "user")()
    return Path(tempfile.gettempdir()) / f"xtr-logging-{owner}" / f"dedup-{digest}.log"


def _private_directory(directory: Path) -> bool:
    """Make ``directory`` for this user alone if missing; tell whether it is theirs alone."""
    try:
        directory.mkdir(mode=_PRIVATE_MODE, exist_ok=True)
        status = directory.lstat()
    except OSError:
        return False
    owner = os.getuid() if hasattr(os, "getuid") else status.st_uid
    if not stat.S_ISDIR(status.st_mode) or status.st_uid != owner:
        return False
    if stat.S_IMODE(status.st_mode) != _PRIVATE_MODE:
        try:
            directory.chmod(_PRIVATE_MODE)
        except OSError:
            return False
    return True


def _first_line(message: str) -> str:
    return re.split(r"[\r\n]", message, maxsplit=1)[0]


def _parse_timestamp(text: str) -> int | None:
    try:
        return int(text)
    except ValueError:
        return None
