from __future__ import annotations

from typing import TYPE_CHECKING, final

from xtr_logging.decorator import as_processor
from xtr_logging.processor.processor_registry import (
    ProcessorDeclaration,
    ProcessorRegistry,
    processors_declared_on,
)

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


def test_a_decorated_function_carries_its_declaration() -> None:
    def add_region(record: LogRecord, /) -> LogRecord:
        return record.with_extra({"region": "eu"})

    _ = as_processor(channel="billing", priority=3, registry=ProcessorRegistry())(add_region)

    assert tuple(processors_declared_on(add_region)) == (
        ProcessorDeclaration(channel="billing", priority=3),
    )


def test_a_function_declared_twice_carries_both_declarations() -> None:
    def add_region(record: LogRecord, /) -> LogRecord:
        return record

    registry = ProcessorRegistry()
    _ = as_processor(channel="billing", registry=registry)(add_region)
    _ = as_processor(handler="file", registry=registry)(add_region)

    assert tuple(processors_declared_on(add_region)) == (
        ProcessorDeclaration(channel="billing"),
        ProcessorDeclaration(handler="file"),
    )
