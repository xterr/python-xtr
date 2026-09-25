from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from xtr_logging.exception.invalid_option_error import InvalidOptionError
from xtr_logging.processor.processor_registry import (
    ProcessorDescriptor,
    ProcessorRegistry,
    default_processor_registry,
)

if TYPE_CHECKING:
    from xtr_logging import LogRecord


def _identity(record: LogRecord, /) -> LogRecord:
    return record


def test_a_registry_keeps_declarations_in_order() -> None:
    registry = ProcessorRegistry()
    first, second = ProcessorDescriptor(_identity), ProcessorDescriptor(_identity, channel="db")

    registry.register(first)
    registry.register(second)

    assert registry.descriptors == (first, second)


def test_clear_forgets_everything() -> None:
    registry = ProcessorRegistry()
    registry.register(ProcessorDescriptor(_identity))

    registry.clear()

    assert registry.descriptors == ()


def test_a_descriptor_may_not_target_both_a_channel_and_a_handler() -> None:
    with pytest.raises(InvalidOptionError):
        _ = ProcessorDescriptor(_identity, channel="app", handler="main")


def test_the_default_registry_is_one_per_process() -> None:
    assert default_processor_registry() is default_processor_registry()
