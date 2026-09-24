"""Stamps every record with the machine it was logged on."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, ClassVar, final

from typing_extensions import override

from .processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging.log_record import LogRecord

__all__ = ["HostnameProcessor"]


@final
class HostnameProcessor(ProcessorInterface):
    """Adds ``extra["hostname"]`` — which machine a record came from.

    Worth having once logs from several hosts are read together. The name is
    read from the operating system once and shared by every instance, since it
    does not change while the process runs.
    """

    __slots__ = ()

    _hostname: ClassVar[str | None] = None

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with the host's name in ``extra``."""
        return record.with_extra({"hostname": self._resolve()})

    @classmethod
    def _resolve(cls) -> str:
        if cls._hostname is None:
            cls._hostname = socket.gethostname()
        return cls._hostname
