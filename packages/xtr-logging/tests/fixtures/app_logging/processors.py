"""A declared processor: exercised by the autoconfiguration path."""

from __future__ import annotations

from typing_extensions import override

from xtr_logging import LogRecord
from xtr_logging.decorator import as_processor
from xtr_logging.processor.processor_interface import ProcessorInterface


@as_processor()
class TenantProcessor(ProcessorInterface):
    """Stamps every record with the caller's tenant, from a fixed value here."""

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        """Return ``record`` with ``tenant=acme`` merged into extras."""
        return record.with_extra({"tenant": "acme"})
