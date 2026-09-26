"""Processors declared where they are written, with ``@as_processor``.

In a kernel, a *class* decorated ``@as_processor`` becomes a service (so its constructor is
injected) and the logging bundle attaches its instance to every logger it builds; a
*function* is the processor itself, attached as it is:

- ``channel=`` limits it to one channel;
- ``handler=`` attaches it to one handler instead, on every channel that handler serves;
- ``priority=`` orders processors, highest first.

Both work without a kernel too: the decorator also fills the process-wide
``default_processor_registry()``, which a bare ``LoggerFactory`` reads.
"""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Autowire
from xtr_logging import LogRecord, ProcessorInterface, as_processor

__all__ = [
    "EnvironmentProcessor",
    "OrdersComponentProcessor",
    "ShopNameProcessor",
    "mark_http_requests",
]


@final
@as_processor(priority=-10)
class ShopNameProcessor(ProcessorInterface):
    """Every channel: which shop wrote the record — a parameter holding an ``env()``."""

    def __init__(self, shop: Annotated[str, Autowire(param="shop.name")]) -> None:
        """Stamp ``shop`` on every record."""
        self._shop = shop

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        return record.with_extra({"shop": self._shop})


@final
@as_processor(channel="orders", priority=10)
class OrdersComponentProcessor(ProcessorInterface):
    """Only the ``orders`` channel."""

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        return record.with_extra({"component": "ordering"})


@final
@as_processor(handler="console")
class EnvironmentProcessor(ProcessorInterface):
    """Only inside the ``console`` handler, whatever the channel."""

    def __init__(self, environment: Annotated[str, Autowire(param="kernel.environment")]) -> None:
        """Stamp the kernel's environment."""
        self._environment = environment

    @override
    def __call__(self, record: LogRecord, /) -> LogRecord:
        return record.with_extra({"env": self._environment})


@as_processor(channel="http", priority=20)
def mark_http_requests(record: LogRecord, /) -> LogRecord:
    """A function processor: nothing to inject, so the function is the processor."""
    return record.with_extra({"transport": "http/1.1"})
