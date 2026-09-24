from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging.decorator import as_processor
from xtr_logging.processor.processor_registry import ProcessorRegistry

if TYPE_CHECKING:
    from xtr_logging import LogRecord


def test_a_decorated_function_is_declared_and_returned_unchanged() -> None:
    registry = ProcessorRegistry()

    def add_tenant(record: LogRecord, /) -> LogRecord:
        return record.with_extra({"tenant": "acme"})

    decorated = as_processor(channel="billing", priority=5, registry=registry)(add_tenant)

    assert decorated is add_tenant
    [descriptor] = registry.descriptors
    assert (descriptor.processor, descriptor.channel, descriptor.priority) == (
        add_tenant,
        "billing",
        5,
    )


def test_a_decorated_class_is_built_once_and_its_instance_declared() -> None:
    registry = ProcessorRegistry()

    @as_processor(handler="main", registry=registry)
    @final
    class AddHost:
        def __call__(self, record: LogRecord, /) -> LogRecord:
            return record.with_extra({"host": "h"})

    [descriptor] = registry.descriptors
    assert isinstance(descriptor.processor, AddHost)
    assert descriptor.handler == "main"
