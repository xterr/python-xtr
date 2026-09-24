"""Stamps every record with the id of the process that logged it."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, final

from typing_extensions import override

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["ProcessIdProcessor"]


@final
class ProcessIdProcessor(ProcessorInterface):
    """Adds ``extra["process_id"]`` — the PID that made the record.

    Read afresh for each record rather than cached, so a worker that forks
    reports the child's id, not the parent's.
    """

    __slots__ = ()

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the current process id in ``extra``."""
        return record.with_extra({"process_id": os.getpid()})
