"""The last shutdown hook: it runs before the bundles shut down."""

from __future__ import annotations

from xtr_dependency_injection import Injected, KernelInterface, on_shutdown
from xtr_logging_contracts import LoggerInterface

__all__ = ["goodbye"]


@on_shutdown
async def goodbye(logger: Injected[LoggerInterface], kernel: Injected[KernelInterface]) -> None:
    """Runs after the higher-priority shutdown hook, before the bundles shut down."""
    logger.info("{name} shutting down", {"name": kernel.name})
