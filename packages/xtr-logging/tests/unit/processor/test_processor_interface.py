from __future__ import annotations

from typing import TYPE_CHECKING

from xtr_logging import UidProcessor
from xtr_logging.processor.processor_interface import ProcessorInterface

if TYPE_CHECKING:
    from xtr_logging import LogRecord


def test_a_shipped_processor_and_a_plain_function_satisfy_it() -> None:
    def tag(record: LogRecord, /) -> LogRecord:
        return record

    assert isinstance(UidProcessor(), ProcessorInterface)
    assert isinstance(tag, ProcessorInterface)


def test_an_object_that_cannot_be_called_does_not() -> None:
    assert not isinstance(object(), ProcessorInterface)
