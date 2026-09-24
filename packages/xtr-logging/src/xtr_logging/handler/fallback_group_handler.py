"""A group that stops at the first member that manages to handle a record."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

from typing_extensions import override

from .group_handler import GroupHandler

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["FallbackGroupHandler"]


@final
class FallbackGroupHandler(GroupHandler):
    """Tries each member in turn until one handles a record without raising.

    A primary handler with backups: send to the network service, fall back to
    a local file if it is down, fall back to stderr if even that fails. The
    last failure is re-raised rather than swallowed — if every
    backup is broken the caller should hear about it, through the logger's own
    exception handler, rather than lose the record in silence.
    """

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Offer ``record`` to each member until one succeeds; re-raise if none do.

        Raises:
            Exception: The failure of the last member, if every member raised.
        """
        record = self._process(record)
        last_error: Exception | None = None
        for handler in self._handlers:
            try:
                _ = handler.handle(record)
            except Exception as error:  # noqa: BLE001 — try the next member; re-raise only if all fail
                last_error = error
            else:
                return not self._bubble
        if last_error is not None:
            raise last_error
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Offer the batch to each member until one succeeds; re-raise if none do.

        Raises:
            Exception: The failure of the last member, if every member raised.
        """
        processed = tuple(self._process(record) for record in records)
        last_error: Exception | None = None
        for handler in self._handlers:
            try:
                handler.handle_batch(processed)
            except Exception as error:  # noqa: BLE001 — try the next member; re-raise only if all fail
                last_error = error
            else:
                return
        if last_error is not None:
            raise last_error
