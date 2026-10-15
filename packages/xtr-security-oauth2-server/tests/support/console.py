"""Running this package's commands the way a shell runs them.

Nothing here is a double: a kernel builds the container, the console bundle
assembles the application out of it, and the tester drives one command through
the very invoker an entry point would — so each run gets the per-run scope that
*is* the unit of work a command's stores read and write through.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from xtr_console import Application
from xtr_console.bundle import ConsoleBundle
from xtr_dependency_injection import Kernel

from xtr_security_oauth2_server.bundle import OAuth2ServerBundle

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator, Mapping

    from xtr_dependency_injection.bundle.bundle import AnyBundle
    from xtr_service_contracts import ContainerInterface

__all__ = ["IN_MEMORY_APP", "console_kernel", "running"]

IN_MEMORY_APP = "tests.fixtures.oauth2_server_app"
"""The fully configured deployment that keeps everything in this process."""


def console_kernel(
    app_module: str = IN_MEMORY_APP,
    *,
    orm: bool = False,
    environ: Mapping[str, str] | None = None,
) -> Kernel:
    """Return a kernel of ``app_module`` with this package's bundle and a console.

    ``orm`` lists the ORM bundle too, which is what a deployment storing its
    clients and credentials in a database does.
    """
    bundles: dict[type[AnyBundle], Mapping[str, bool]] = {
        OAuth2ServerBundle: {"all": True},
        ConsoleBundle: {"all": True},
    }
    if orm:
        from xtr_orm.bundle import OrmBundle  # noqa: PLC0415 -- xtr-orm is optional, imported here

        bundles[OrmBundle] = {"all": True}

    return Kernel(
        app_module,
        env="test",
        bundles=bundles,
        concurrent_scoped_access=True,
        environ=dict(environ) if environ is not None else None,
    )


@asynccontextmanager
async def running(kernel: Kernel) -> AsyncGenerator[tuple[Application, ContainerInterface]]:
    """Boot ``kernel`` and yield its console application and its container."""
    async with await kernel.boot() as booted:
        yield await booted.container.get(Application), booted.container
