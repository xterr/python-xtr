"""The first startup check, by priority — see ``startup_check`` for the order."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import KernelInterface, as_tagged_item

from bookshop.service.startup_check import StartupCheck

__all__ = ["ConfigurationCheck"]


@final
@as_tagged_item(priority=10)
class ConfigurationCheck(StartupCheck):
    """The kernel runs in an environment the application knows."""

    def __init__(self, kernel: KernelInterface) -> None:
        """Check ``kernel``."""
        self._kernel = kernel

    @override
    async def run(self) -> str:
        return f"{self._kernel.name} in {self._kernel.environment}, debug={self._kernel.debug}"
