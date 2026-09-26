"""A compiler pass the bundle registers from ``build``: it wires the configured pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, final

from typing_extensions import override
from xtr_dependency_injection import CompilerPassInterface

from fulltext.search_index import SearchIndex

from .fulltext_config import FulltextConfig

if TYPE_CHECKING:
    from xtr_dependency_injection import ContainerBuilder, ServiceKey

__all__ = ["ANALYZER_TAG", "AnalyzerPipelinePass"]

ANALYZER_TAG: Final = "fulltext.analyzer"
"""The tag every analyzer definition carries — nominal autoconfiguration adds it."""


@final
class AnalyzerPipelinePass(CompilerPassInterface):
    """Hands the index the service key of every analyzer in the configured pipeline.

    Runs once every definition exists, so it sees the analyzers the application declared as
    well as the library's own. What it computes becomes an *argument* on the index's
    definition: the report shows it, and nothing is resolved at runtime that could have been
    decided now.
    """

    @override
    def process(self, builder: ContainerBuilder) -> None:
        config = builder.get_extension_config(FulltextConfig)
        declared: dict[str, ServiceKey] = {}
        for key in builder.find_tagged_service_ids(ANALYZER_TAG):
            _, qualifier = key
            if isinstance(qualifier, str):
                declared[qualifier] = key
        pipeline = tuple((name, declared[name]) for name in config.pipeline if name in declared)
        _ = builder.get_definition(SearchIndex).set_argument("pipeline", pipeline)
        builder.log(self, f"pipeline: {' -> '.join(name for name, _ in pipeline)}")
