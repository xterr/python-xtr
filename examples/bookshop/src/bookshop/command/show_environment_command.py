"""``env:show`` — every environment variable processor's result, and the typed settings."""

from __future__ import annotations

import os
from typing import cast

from xtr_console import ConsoleStyle, ExitCode, as_command, escape
from xtr_dependency_injection import Injected, KernelInterface
from xtr_dotenv import PATH_VAR, TRACKING_VAR

from bookshop.env.env_showcase import EnvShowcase
from bookshop.service.shop_settings import ShopSettings

__all__ = ["show_environment"]

_ECOSYSTEM_VARIABLES = ("APP_ENV", "APP_DEBUG", "SHELL_VERBOSITY", TRACKING_VAR, PATH_VAR)


@as_command("env:show")
async def show_environment(
    io: ConsoleStyle,
    showcase: Injected[EnvShowcase],
    settings: Injected[ShopSettings],
    kernel: Injected[KernelInterface],
) -> int:
    """Show every environment variable processor's result, and the typed settings.

    Args:
        io: Where the command writes.
        showcase: One value per env processor.
        settings: The same cascade, as a pydantic-settings model.
        kernel: The kernel's environment and debug flag.
    """
    io.title(f"Environment: {kernel.environment} (debug={kernel.debug})")
    io.section("Variables the xtr packages read or write")
    io.table(
        ["Variable", "Value"],
        [[name, escape(os.environ.get(name, "(unset)"))[:80]] for name in _ECOSYSTEM_VARIABLES],
    )
    io.section("Autowire(env=...) — one per processor")
    io.table(
        ["Processor", "Expression", "Value"],
        [
            [label, expression, escape(repr(value))[:70]]
            for label, (expression, value) in showcase.values.items()
        ],
    )
    io.section("DotenvSettings — the same cascade, typed")
    io.table(
        ["Field", "Value"],
        [[k, repr(v)] for k, v in cast("dict[str, object]", settings.model_dump()).items()],
    )
    return ExitCode.SUCCESS
