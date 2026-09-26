"""The application's compiler passes: each sees, and may change, every definition.

``@compiler_pass`` goes on a class implementing ``CompilerPassInterface``; the kernel builds
it with no arguments. Passes run stage by stage — ``BEFORE_OPTIMIZATION``, ``OPTIMIZE``,
``BEFORE_REMOVING``, ``REMOVE``, ``AFTER_REMOVING`` — and within a stage by priority, highest
first: the built-in passes first, then bundles', then the application's in scan order.
``@compiler_pass`` must be found by the early scan (the application package is).
"""

from __future__ import annotations

from collections.abc import Hashable
from dataclasses import dataclass
from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    CompilerPassInterface,
    ContainerBuilder,
    Definition,
    Origin,
    PassStage,
    ServiceKey,
    compiler_pass,
)

from bookshop.reporting.export_registry import ExportRegistry
from bookshop.reporting.exporters import EXPORTER_TAG

__all__ = [
    "CompilationSummary",
    "CompilationSummaryPass",
    "ExporterRegistryPass",
    "TagApplicationServicesPass",
]

_APP_TAG = "bookshop.app_service"


@final
@compiler_pass
class TagApplicationServicesPass(CompilerPassInterface):
    """Tags every definition the application contributed. Bare: ``BEFORE_OPTIMIZATION``, 0.

    It runs after the built-in autoconfiguration passes (priority 100), so decorators
    and autoconfigured definitions are already there to see.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        tagged = 0
        for definition in builder.get_definitions():
            if definition.origin.kind == "app" and not definition.has_tag(_APP_TAG):
                _ = definition.add_tag(_APP_TAG, module=definition.origin.name.split(":")[0])
                tagged += 1
        builder.log(self, f"tagged {tagged} application services")


@final
@compiler_pass(stage=PassStage.OPTIMIZE, priority=-100)
class ExporterRegistryPass(CompilerPassInterface):
    """Finds every tagged exporter and hands the registry their keys, by format.

    ``OPTIMIZE``, after autoconfiguration has tagged every ``Exporter`` subclass.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        formats: dict[Hashable, ServiceKey] = {}
        for key, attributes in builder.find_tagged_service_ids(EXPORTER_TAG).items():
            for attribute in attributes:
                formats[str(attribute["format"])] = key
        _ = builder.get_definition(ExportRegistry).set_argument("formats", formats)
        builder.log(self, f"exporters: {', '.join(sorted(map(str, formats)))}")


@dataclass(frozen=True, slots=True)
class CompilationSummary:
    """What the container looked like once compiled — an instance a pass registered.

    Attributes:
        definitions: How many definitions there are.
        aliases: How many aliases there were before they became definitions.
        log: The compiler's log, every pass's messages.
    """

    definitions: int
    aliases: int
    log: tuple[str, ...]


@final
@compiler_pass(stage=PassStage.AFTER_REMOVING, priority=-1000)
class CompilationSummaryPass(CompilerPassInterface):
    """Registers a :class:`CompilationSummary` instance — the last thing to run.

    ``builder.set_definition`` stores a fully built ``Definition``; ``kind="instance"``
    provides the object itself. ``bookshop di:show`` prints it.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        summary = CompilationSummary(
            definitions=len(builder.get_definitions()),
            aliases=len(builder.get_aliases()),
            log=tuple(builder.get_compiler().get_log()),
        )
        _ = builder.set_definition(
            Definition(
                key=(CompilationSummary, None),
                provider=summary,
                kind="instance",
                lifetime="singleton",
                origin=Origin("app", "bookshop.compiler_passes:CompilationSummaryPass"),
            )
        )
