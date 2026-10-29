"""A processor declared where it is written, with ``@as_processor``: every channel.

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

__all__ = ["ShopNameProcessor"]


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
