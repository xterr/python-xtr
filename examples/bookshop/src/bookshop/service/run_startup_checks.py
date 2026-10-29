"""A boot hook running every startup check, in the order the kernel emitted them."""

from __future__ import annotations

from typing import Annotated, cast

from xtr_dependency_injection import Injected, KernelInterface, Target, on_boot
from xtr_logging_contracts import LoggerInterface
from xtr_service_contracts import ContainerInterface

from bookshop.service.startup_check import STARTUP_CHECK_TAG, StartupCheck

__all__ = ["run_startup_checks"]


@on_boot
async def run_startup_checks(
    kernel: Injected[KernelInterface],
    container: Injected[ContainerInterface],
    logger: Annotated[LoggerInterface, Target("app")],
) -> None:
    """Run every startup check, in the order the kernel emitted them.

    The kernel's report lists definitions in emission order — the order ``priority``,
    ``before`` and ``after`` decided — with their tags; this hook reads it back.
    """
    for definition in kernel.report.definitions:
        if STARTUP_CHECK_TAG not in definition.tags:
            continue
        provided, qualifier = definition.key
        check = cast("StartupCheck", await container.get(provided, qualifier))
        outcome = await check.run()
        logger.info(
            "startup check {check}: {outcome}", {"check": provided.__name__, "outcome": outcome}
        )
