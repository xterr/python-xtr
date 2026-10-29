"""The first code run as the kernel boots: an ``@on_boot`` hook of the highest priority.

::

    boot()      bundle.boot() in bundle order -> @on_boot, highest priority first
    shutdown()  @on_shutdown, highest priority first -> bundle.shutdown() in reverse
                -> the container closes (every generator factory's cleanup runs)

Hooks are injected — ``Injected[...]``, ``Autowire(...)``, ``Target(...)`` — and may be sync
or async. A *sync* hook can only receive services the container builds synchronously: a
service built by an async factory — or depending on one, like every logger (the logger
factory is an async generator) and the console ``Application`` — needs an ``async def`` hook.
A failing boot hook shuts down what already booted, in reverse, and propagates;
``@on_shutdown`` hooks run only after a boot that succeeded.
"""

from __future__ import annotations

from typing import Annotated

from xtr_dependency_injection import Autowire, Injected, KernelInterface, on_boot
from xtr_logging_contracts import LoggerInterface

__all__ = ["announce_boot"]


@on_boot(priority=100)
def announce_boot(
    kernel: Injected[KernelInterface],
    logger: Injected[LoggerInterface],
    shop: Annotated[str, Autowire(param="shop.name")],
) -> None:
    """Runs first (highest priority): a sync hook, with a parameter holding an ``env()``."""
    logger.info(
        "{shop} booting in {env}",
        {"shop": shop, "env": kernel.environment, "bundles": list(kernel.bundles)},
    )
