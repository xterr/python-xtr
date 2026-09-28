from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.processor.processor_descriptor import ProcessorDescriptor

if TYPE_CHECKING:
    from xtr_logging import LogRecord


def _identity(record: LogRecord, /) -> LogRecord:
    return record


def test_it_runs_everywhere_at_priority_zero_by_default() -> None:
    descriptor = ProcessorDescriptor(_identity)

    assert (descriptor.channel, descriptor.handler, descriptor.priority) == (None, None, 0)


def test_it_may_not_target_both_a_channel_and_a_handler() -> None:
    with pytest.raises(InvalidOptionError):
        _ = ProcessorDescriptor(_identity, channel="app", handler="main")
