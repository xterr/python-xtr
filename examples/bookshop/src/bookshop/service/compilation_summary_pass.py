"""The last compiler pass to run: it registers an instance, at ``AFTER_REMOVING``."""

from __future__ import annotations

from typing import final

from typing_extensions import override
from xtr_dependency_injection import (
    CompilerPassInterface,
    ContainerBuilder,
    Definition,
    Origin,
    PassStage,
    compiler_pass,
)

from bookshop.service.compilation_summary import CompilationSummary

__all__ = ["CompilationSummaryPass"]


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
                origin=Origin(
                    "app", "bookshop.service.compilation_summary_pass:CompilationSummaryPass"
                ),
            )
        )
