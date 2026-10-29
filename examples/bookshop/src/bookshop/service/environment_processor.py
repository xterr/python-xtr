"""A processor attached to one handler: ``@as_processor(handler=...)``."""

from __future__ import annotations

from typing import Annotated, final

from typing_extensions import override
from xtr_dependency_injection import Autowire
from xtr_logging import LogRecord, ProcessorInterface, as_processor

__all__ = ["EnvironmentProcessor"]


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
