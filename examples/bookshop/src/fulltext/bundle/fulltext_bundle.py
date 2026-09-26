"""The fulltext bundle: every hook a bundle has, each doing the one job it is for.

=====================  ==========================================================
Hook                   What this bundle does there
=====================  ==========================================================
``build``              autoconfiguration (by marker and by base type), a compiler
                       pass, a parameter
``prepend_extension``  adds a ``search`` channel to the logging bundle's config,
                       only when that bundle is active
``load_extension``     defines the services, from the resolved config
``process``            runs as a compiler pass: validates the configured pipeline
``boot``               builds the engine now, so a broken wiring fails at boot
``shutdown``           empties the index
=====================  ==========================================================
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, cast, final

from typing_extensions import override
from xtr_clock import ClockInterface
from xtr_clock.bundle import ClockBundle
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    PassStage,
    ServiceConfigurator,
    ServiceKey,
    ServiceLocator,
    Target,
    as_bundle,
    bundle_active,
    required_bundle,
)
from xtr_logging_contracts import LoggerInterface, NullLogger
from xtr_service_contracts import ContainerInterface

from fulltext.analyzer_interface import AnalyzerInterface
from fulltext.analyzer_registry import AnalyzerRegistry
from fulltext.decorator import AnalyzerDeclaration, analyzers_declared_on
from fulltext.exception import UnknownAnalyzerError
from fulltext.query_log import QueryLog
from fulltext.search_engine import SearchEngine
from fulltext.search_engine_interface import SearchEngineInterface
from fulltext.search_index import SearchIndex

from .analyzer_pipeline_pass import ANALYZER_TAG, AnalyzerPipelinePass
from .fulltext_config import FulltextConfig
from .timed_search_engine import TimedSearchEngine

__all__ = ["FulltextBundle"]

_SEARCH_CHANNEL = "search"


@final
# A hard peer, by class: the index stamps updates with the clock, and FulltextConfig.clock
# forwards to the clock bundle's config through AliasOf, which needs that bundle active.
@required_bundle(ClockBundle)
# A soft peer, by "module:Class": pulled in when installed, skipped silently when not.
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
# Never installed in this example: the kernel reports it as skipped, and nothing fails.
@required_bundle("fulltext_metrics.bundle:MetricsBundle", ignore_on_invalid=True)
@as_bundle("fulltext", config=FulltextConfig, resources=("fulltext.analyzers",))
class FulltextBundle(Bundle[FulltextConfig]):
    """Registers an index, an engine and every declared analyzer.

    Everything per kernel lives on the instance: the kernel builds one bundle instance per
    ``build()``, so two kernels in one process never share an :class:`AnalyzerRegistry`.
    """

    def __init__(self) -> None:
        """Start with an empty registry; the scan fills it while the container compiles."""
        self._registry = AnalyzerRegistry()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Wire what must exist before any bundle loads.

        - marker autoconfiguration: every scanned class carrying ``@as_analyzer`` becomes a
          service, qualified by its name;
        - nominal autoconfiguration: every definition whose type subclasses
          :class:`AnalyzerInterface` gets the ``fulltext.analyzer`` tag;
        - a compiler pass, at ``BEFORE_REMOVING``, wiring the pipeline;
        - a parameter, readable anywhere as ``%fulltext.analyzer_tag%``.
        """
        registry = self._registry

        def register_analyzer(
            obj: object, declaration: AnalyzerDeclaration, services: ServiceConfigurator
        ) -> None:
            analyzer = cast("type[AnalyzerInterface]", obj)
            registry.declare(declaration.name, analyzer)
            _ = services.set(analyzer, qualifier=declaration.name)

        builder.register_attribute_for_autoconfiguration(analyzers_declared_on, register_analyzer)
        _ = builder.register_for_autoconfiguration(AnalyzerInterface).add_tag(ANALYZER_TAG)
        builder.add_compiler_pass(
            AnalyzerPipelinePass(), stage=PassStage.BEFORE_REMOVING, priority=10
        )
        builder.set_parameter("fulltext.analyzer_tag", ANALYZER_TAG)

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Give the logging bundle a ``search`` channel — when it is active.

        By config type rather than by name, to show both spellings work; the import is
        deferred because logging is an optional peer of this library.
        """
        if not bundle_active(builder, "logging"):
            return
        from xtr_logging.bundle import LoggingConfig  # noqa: PLC0415 — optional peer.

        def add_search_channel(config: LoggingConfig) -> LoggingConfig:
            return config.with_channels(_SEARCH_CHANNEL)

        builder.prepend_extension_config(LoggingConfig, add_search_channel)

    @override
    def load_extension(
        self,
        config: FulltextConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Define the services.

        ``config`` may hold ``env()`` placeholders. It is read here only to decide what the
        container contains or to hand values over with ``set_argument`` — both keep the
        placeholder until the service is built. A factory that needs the values injects
        ``FulltextConfig`` instead of closing over ``config``.
        """
        # The registry instance itself: ``services.instance`` keys it by its own type.
        _ = services.instance(self._registry)

        # The index: built by a factory whose ``pipeline`` argument a compiler pass sets.
        _ = services.set(_search_index)

        # Per-unit-of-work state, opted in to ``kernel.reset`` explicitly: its method is not
        # ``reset``, so it names it. ``ServicesResetter`` calls it between messages/requests.
        _ = services.set(QueryLog).add_tag("kernel.reset", method="clear")

        # The engine: a different factory depending on whether logging is there at all.
        if bundle_active(builder, "logging"):
            _ = services.set(_search_engine_with_channel)
        else:
            _ = services.set(_search_engine_without_logging)
        services.alias(SearchEngineInterface, SearchEngine)

        # A decorator registered from a bundle, and an argument given instead of injected.
        _ = (
            services.set(TimedSearchEngine)
            .set_decorated_service(SearchEngine)
            .set_argument("threshold_ms", config.slow_query_ms)
        )

        # Commands only make sense with a console: scan them late, only then.
        if bundle_active(builder, "console"):
            services.load("fulltext.command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Refuse a pipeline naming an analyzer nothing declared.

        Overriding ``process`` makes the bundle a compiler pass, at ``BEFORE_OPTIMIZATION``
        priority -10000 — after every autoconfiguration, so every analyzer is tagged by now.
        """
        config = builder.get_extension_config(FulltextConfig)
        declared = tuple(
            qualifier
            for _, qualifier in builder.find_tagged_service_ids(ANALYZER_TAG)
            if isinstance(qualifier, str)
        )
        for name in config.pipeline:
            if name not in declared:
                raise UnknownAnalyzerError(name, declared)
        builder.log(self, f"{len(declared)} analyzers declared: {', '.join(declared)}")

    @override
    async def boot(self) -> None:
        """Build the engine now: a missing dependency fails the boot, not the first query."""
        container = self._container()
        _ = await container.get(SearchEngineInterface)

    @override
    async def shutdown(self) -> None:
        """Empty the index; ``self.container`` is still set during shutdown."""
        index = await self._container().get(SearchIndex)
        index.clear()

    def _container(self) -> ContainerInterface:
        container = self.container
        if container is None:  # pragma: no cover — the kernel sets it before boot.
            raise RuntimeError("FulltextBundle ran without a container")
        return container


async def _search_index(
    container: ContainerInterface,
    clock: ClockInterface,
    pipeline: Sequence[tuple[str, ServiceKey]],
) -> SearchIndex:
    """Build the index with the pipeline's analyzers, resolved lazily through a locator.

    ``pipeline`` is not injected: :class:`AnalyzerPipelinePass` sets it as an argument on this
    factory's definition. A :class:`ServiceLocator` builds only the analyzers it is asked for.
    """
    locator = ServiceLocator[AnalyzerInterface](container, dict(pipeline))
    analyzers = [analyzer async for _, analyzer in locator]
    return SearchIndex(analyzers, clock)


def _search_engine_with_channel(
    index: SearchIndex,
    config: FulltextConfig,
    queries: QueryLog,
    logger: Annotated[LoggerInterface, Target(_SEARCH_CHANNEL)],
) -> SearchEngine:
    """Build the engine, logging through the ``search`` channel this bundle prepended."""
    return SearchEngine(index, config.max_results, config.min_score, logger, queries)


def _search_engine_without_logging(
    index: SearchIndex, config: FulltextConfig, queries: QueryLog
) -> SearchEngine:
    """Build the engine with a null logger: the library keeps working without logging."""
    return SearchEngine(index, config.max_results, config.min_score, NullLogger(), queries)
