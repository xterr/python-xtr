"""A group where one broken handler does not take the others down with it."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .group_handler import GroupHandler

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_logging.log_record import LogRecord

__all__ = ["WhatFailureGroupHandler"]


@final
class WhatFailureGroupHandler(GroupHandler):
    """Forwards to every member, swallowing whatever any of them throws.

    The opt-in "logging must never break the app" wrapper: a syslog socket
    that has gone away, or a disk that has filled, stops that one handler and
    no other. Failures are suppressed on purpose — there is nowhere left to
    report a logging failure to — so reach for this only at the outermost
    layer, never to paper over a handler that should be fixed.
    """

    @override
    def handle(self, record: LogRecord, /) -> bool:
        """Offer ``record`` to every member, ignoring any that fail."""
        record = self._process(record)
        for handler in self._handlers:
            # A failing member must not stop the rest of the group.
            with contextlib.suppress(Exception):
                _ = handler.handle(record)
        return not self._bubble

    @override
    def handle_batch(self, records: Sequence[LogRecord], /) -> None:
        """Offer the batch to every member, ignoring any that fail."""
        processed = tuple(self._process(record) for record in records)
        for handler in self._handlers:
            # A failing member must not stop the rest of the group.
            with contextlib.suppress(Exception):
                handler.handle_batch(processed)

    @override
    def close(self) -> None:
        """Close every member, ignoring any that fail."""
        for handler in self._handlers:
            # A failing member must not stop the rest closing.
            with contextlib.suppress(Exception):
                handler.close()
