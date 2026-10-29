"""``debug:bundles``, ``debug:config`` and ``debug:container`` — the kernel's report."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, cast, final

from xtr_dependency_injection import (
    Injected,
    KernelInterface,
    ServiceKey,
    qualified_name,
)
from xtr_dependency_injection.bundle import advertised_bundles

from xtr_console import CommandsLocator, ConsoleStyle, ExitCode, as_command

if TYPE_CHECKING:
    from collections.abc import Sequence

    from xtr_dependency_injection.diagnostics import BundleReport

__all__ = ["DebugBundlesCommand", "DebugConfigCommand", "DebugContainerCommand"]

# The bundle finds these commands on the classes themselves; this registry only
# keeps the declaration out of the process-wide one a container-less app reads.
_DEBUG_REGISTRY = CommandsLocator()


@as_command("debug:bundles", registry=_DEBUG_REGISTRY)
@final
class DebugBundlesCommand:
    """List every bundle the kernel considered, and the installed ones it did not."""

    async def __call__(self, io: ConsoleStyle, kernel: Injected[KernelInterface]) -> int:
        """Print the ``bundles`` section of the kernel's report, then the bundles left out.

        A bundle an installed distribution advertises but the application
        neither lists nor has required is usually a package added and never
        activated — nothing fails, its services are simply absent.

        An advertised entry that cannot be loaded is listed too, with what it
        said: it would otherwise be missing from both lists.

        A bundle the application lists by name and this environment disables
        is listed all the same, so it is not left out either — though the
        kernel, which never imports it here, reports it by the string it is
        listed under rather than by its class.
        """
        io.console.print(kernel.report.render("bundles"))
        advertised = advertised_bundles()
        considered = {bundle.qualname for bundle in kernel.report.bundles}
        named = _named_by_disabled_entries(kernel.report.bundles)
        left_out = tuple(
            (bundle.metadata().name, qualified_name(bundle))
            for bundle in advertised.bundles
            if qualified_name(bundle) not in considered and bundle not in named
        )
        if left_out:
            io.newline()
            io.section("Installed, not active")
            io.table(("Name", "Class"), left_out)
            io.note("List a bundle in the application's config/bundles.py to activate it.")
        if advertised.unusable:
            io.newline()
            io.section("Advertised, could not be loaded")
            io.table(("Entry point", "Error"), advertised.unusable)
            io.note("Install what the package's bundle needs, or drop the package.")
        return ExitCode.SUCCESS


@as_command("debug:config", registry=_DEBUG_REGISTRY)
@final
class DebugConfigCommand:
    """Show the resolved configuration of every bundle, or of one when named."""

    async def __call__(
        self, io: ConsoleStyle, kernel: Injected[KernelInterface], bundle: str | None = None
    ) -> int:
        """Print the ``configs`` section, filtered by ``bundle`` when given."""
        configs = kernel.report.configs
        if bundle is not None:
            configs = tuple(config for config in configs if config.bundle == bundle)
            if not configs:
                io.error(f"No bundle named {bundle!r}")
                return ExitCode.INVALID
        for config in configs:
            io.section(config.bundle)
            io.text(" -> ".join(config.steps))
            io.text(repr(config.value))
            io.newline()
        return ExitCode.SUCCESS


@as_command("debug:container", registry=_DEBUG_REGISTRY)
@final
class DebugContainerCommand:
    """List every compiled definition; ``--tag`` filters by tag name."""

    async def __call__(
        self,
        io: ConsoleStyle,
        kernel: Injected[KernelInterface],
        *,
        tag: str | None = None,
    ) -> int:
        """Print the ``definitions`` section, filtered by ``tag`` when given."""
        if tag is None:
            io.console.print(kernel.report.render("definitions"))
            return ExitCode.SUCCESS
        matches = tuple(
            definition for definition in kernel.report.definitions if tag in definition.tags
        )
        if not matches:
            io.text(f"No definition tagged {tag!r}")
            return ExitCode.SUCCESS
        rows = tuple(
            (
                _service_name(definition.key),
                definition.provider_qualname,
                definition.kind,
                definition.lifetime,
            )
            for definition in matches
        )
        io.table(("Service", "Provider", "Kind", "Lifetime"), rows)
        return ExitCode.SUCCESS


def _service_name(key: ServiceKey) -> str:
    """Render a service key readably: ``module.Class`` or ``module.Class['qualifier']``."""
    service, qualifier = key
    name = service.__qualname__
    return name if qualifier is None else f"{name}[{qualifier!r}]"


def _named_by_disabled_entries(reports: Sequence[BundleReport]) -> list[object]:
    """Return what each disabled entry's ``"module:Class"`` names.

    A diagnostic may import what the build did not: every installed bundle has
    just been imported to list them, so such a module is usually loaded
    already, and one that does not import is not installed — so it cannot be
    among the installed bundles left out.
    """
    return [_named_by(report.qualname) for report in reports if report.state == "env_disabled"]


def _named_by(target: str) -> object:
    """Return what ``"module:Class"`` names, or ``None`` when its module does not import."""
    module_name, _, attribute = target.partition(":")
    try:
        module = importlib.import_module(module_name)
    except Exception:  # noqa: BLE001 — what the application names may fail any way as it imports; the report must still print.
        return None
    return cast("object", getattr(module, attribute, None))
