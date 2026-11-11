"""The bundle wiring platforms, agents, conversation stores and run control into the container."""

from __future__ import annotations

from importlib.util import find_spec
from typing import TYPE_CHECKING, Final, cast, final

from pydantic_ai.agent import AbstractAgent
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.conversation_store import ConversationStore
from pydantic_ai.toolsets import AbstractToolset
from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    qualified_name,
    required_bundle,
)

from xtr_ai.exception import InvalidConfigurationError
from xtr_ai.platform_registry import PlatformRegistry
from xtr_ai.platform_registry_interface import PlatformRegistryInterface

from ._agent_factories import AI_CHANNEL, agent_factory
from ._platform_factories import platform_factory, registry_factory
from ._references import check_references, require_bridge
from ._store_factories import (
    CONVERSATION_STORE_BRIDGE,
    RUN_CONTROL_BRIDGE,
    conversation_store_factory,
    run_control_factory,
)
from ._tool_wiring import TOOL_TAG, classes_declaring_tools, tools_registrar
from .ai_config import AiConfig
from .conversation_store_configs import OrmConversationStoreConfig
from .run_control_configs import OrmRunControlConfig, ServiceRunControlConfig
from .toolset_configs import ToolsetRef

if TYPE_CHECKING:
    from xtr_orm.bundle import OrmMappingsPass

    from .agent_config import AgentConfig

__all__ = ["AiBundle"]

DEFAULT_STORE: Final = "default"
"""The conversation store also injected without a name."""

_STORE_CONNECTION: Final = "ai.conversation_store.orm_connection"
_STORE_ENABLED: Final = "ai.conversation_store.orm_enabled"
_RUN_CONNECTION: Final = "ai.run_control.orm_connection"
_RUN_ENABLED: Final = "ai.run_control.orm_enabled"


@final
@required_bundle("xtr_clock.bundle:ClockBundle", ignore_on_invalid=True)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@as_bundle("ai", config=AiConfig)
class AiBundle(Bundle[AiConfig]):
    """Registers each configured platform, agent, conversation store and run control.

    Nothing is built, imported from a provider's SDK or read from the
    environment while the container builds or boots: an agent is built the
    first time it is injected, and its platform the first time a run needs a
    model. Agents are injected by name — ``Annotated[AbstractAgent,
    Target("chat")]`` — and all of them as ``Mapping[Hashable, AbstractAgent]``.
    """

    def __init__(self) -> None:
        """Hold no mapping passes and no agents yet."""
        self._store_mappings: OrmMappingsPass | None = None
        self._run_mappings: OrmMappingsPass | None = None
        self._agents: tuple[str, ...] = ()
        self._service_types: dict[type, tuple[type, str]] = {}
        self._tool_classes: set[type] = set()

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Collect ``@as_tool`` methods, and ready the orm bridges' tables when both are there."""
        builder.register_attribute_for_autoconfiguration(
            classes_declaring_tools, tools_registrar(self._tool_classes)
        )
        if not bundle_active(builder, "orm"):
            return
        from xtr_orm.bundle import OrmMappingsPass  # noqa: PLC0415 — the orm is an optional peer

        if find_spec(CONVERSATION_STORE_BRIDGE) is not None:
            self._store_mappings = OrmMappingsPass(_STORE_CONNECTION, _STORE_ENABLED)
            builder.add_compiler_pass(self._store_mappings)
        if find_spec(RUN_CONTROL_BRIDGE) is not None:
            self._run_mappings = OrmMappingsPass(_RUN_CONNECTION, _RUN_ENABLED)
            builder.add_compiler_pass(self._run_mappings)

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Add the ``ai`` channel to the logging configuration, when logging is active."""
        if not bundle_active(builder, "logging"):
            return
        from xtr_logging.bundle import LoggingConfig  # noqa: PLC0415 — logging is an optional peer

        def add_ai_channel(config: LoggingConfig) -> LoggingConfig:
            return config.with_channels(AI_CHANNEL)

        builder.prepend_extension_config(LoggingConfig, add_ai_channel)

    @override
    def load_extension(
        self,
        config: AiConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register what ``config`` names; build none of it.

        Raises:
            InvalidConfigurationError: When a literal reference names nothing
                configured, agents call each other in a cycle, or an orm
                adapter lacks its bridge package.
        """
        check_references(config)
        has_clock = bundle_active(builder, "clock")
        has_logging = bundle_active(builder, "logging")
        for name, platform in config.platforms.items():
            _ = services.set(platform_factory(name), qualifier=name).set_argument(
                "platform_config", platform
            )
        _ = services.set(registry_factory(tuple(config.platforms)))
        services.alias(PlatformRegistryInterface, PlatformRegistry)
        self._agents = tuple(config.agents)
        for name, agent in config.agents.items():
            definition = services.set(agent_factory(name), qualifier=name).set_arguments(
                {
                    "agent_config": agent,
                    "capability_qualifiers": self._capability_qualifiers(agent),
                    "toolset_qualifiers": self._toolset_qualifiers(agent),
                }
            )
            if not has_clock:
                _ = definition.set_argument("clock", None)
            if not has_logging:
                _ = definition.set_argument("logger", None)
        self._register_conversation_stores(config, services, builder)
        self._register_run_control(config, services, builder, has_clock=has_clock)
        if bundle_active(builder, "console"):
            services.load(
                "xtr_ai.command.debug_ai_command",
                "xtr_ai.command.platform_invoke_command",
                "xtr_ai.command.agent_call_command",
            )
            if config.runs is not None:
                services.load("xtr_ai.command.run_cancel_command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Register what agents are built from, and give each the toolsets its tools make.

        A capability, toolset or tool class the application registered itself
        is used as registered; any other is registered as a singleton.

        Raises:
            InvalidConfigurationError: When a tool names an agent that is not
                configured, or a capability, toolset or tool class is not a
                singleton — an agent is one, and outlives any scope.
        """
        for service_type, (base, qualifier) in self._service_types.items():
            if not builder.has_definition(service_type):
                _ = builder.register(service_type)
            builder.set_alias(base, service_type, alias_qualifier=qualifier)
        for tool_class in self._tool_classes:
            if not builder.has_definition(tool_class):
                _ = builder.register(tool_class)
        self._hand_over_tools(builder)
        for service_type in (*self._service_types, *self._tool_classes):
            lifetime = builder.find_definition(service_type).lifetime
            if lifetime != "singleton":
                raise InvalidConfigurationError(
                    f"{qualified_name(service_type)} is registered {lifetime}, but an agent "
                    "is built from it once: register it as a singleton, and read per-run state "
                    "from the run's deps.",
                )

    def _hand_over_tools(self, builder: ContainerBuilder) -> None:
        """Add the toolsets ``@as_tool`` methods make to the agents they are declared for.

        Raises:
            InvalidConfigurationError: When a tool names an agent that is not configured.
        """
        tools: dict[str, list[str]] = {name: [] for name in self._agents}
        for (_, qualifier), tags in builder.find_tagged_service_ids(TOOL_TAG).items():
            attributes = tags[0]
            agent = str(attributes["agent"])
            if agent not in tools:
                raise InvalidConfigurationError(
                    f'{attributes["service"]} declares a tool for the "{agent}" agent, '
                    f"which is not configured.",
                )
            tools[agent].append(str(qualifier))
        for agent, qualifiers in tools.items():
            if not qualifiers:
                continue
            definition = builder.get_definition(AbstractAgent, qualifier=agent)
            given = cast(
                "tuple[str, ...]", definition.get_arguments().get("toolset_qualifiers", ())
            )
            _ = definition.set_argument("toolset_qualifiers", (*given, *sorted(qualifiers)))

    def _capability_qualifiers(self, agent: AgentConfig) -> tuple[str, ...]:
        return tuple(
            self._remember_service(entry, AbstractCapability)
            for entry in agent.capabilities
            if isinstance(entry, type)
        )

    def _toolset_qualifiers(self, agent: AgentConfig) -> tuple[str, ...]:
        return tuple(
            self._remember_service(entry.service, AbstractToolset)
            for entry in agent.toolsets
            if isinstance(entry, ToolsetRef)
        )

    def _remember_service(self, service_type: type, base: type) -> str:
        """Remember ``service_type``, to be reachable as ``base`` under a qualifier of its own."""
        known = self._service_types.get(service_type)
        if known is not None:
            return known[1]
        qualifier = f"ai_{qualified_name(service_type)}"
        self._service_types[service_type] = (base, qualifier)
        return qualifier

    def _register_conversation_stores(
        self, config: AiConfig, services: ServiceConfigurator, builder: ContainerBuilder
    ) -> None:
        orm: list[tuple[str, OrmConversationStoreConfig]] = []
        for name, entry in config.conversation_stores.items():
            if isinstance(entry, OrmConversationStoreConfig):
                require_bridge(
                    f'The "{name}" conversation store',
                    CONVERSATION_STORE_BRIDGE,
                    orm_active=bundle_active(builder, "orm"),
                )
                orm.append((name, entry))
            _ = services.set(conversation_store_factory(name, entry), qualifier=name)
            if name == DEFAULT_STORE:
                services.alias(ConversationStore, ConversationStore, target_qualifier=name)
        if not orm:
            return
        layouts = {(entry.connection, entry.table_prefix) for _, entry in orm}
        if len(layouts) > 1:
            raise InvalidConfigurationError(
                "Every orm conversation store keeps its conversations in the same tables: give "
                f"{', '.join(repr(name) for name, _ in orm)} one connection and one table_prefix.",
            )
        connection, table_prefix = layouts.pop()
        from xtr_ai_orm_conversation_store import (  # noqa: PLC0415 — the bridge is optional
            ConversationMappingDriver,
        )

        builder.set_parameter(_STORE_CONNECTION, connection)
        builder.set_parameter(_STORE_ENABLED, True)  # noqa: FBT003 — a parameter's value
        if self._store_mappings is not None:
            self._store_mappings.set_driver(ConversationMappingDriver(table_prefix))

    def _register_run_control(
        self,
        config: AiConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
        *,
        has_clock: bool,
    ) -> None:
        entry = config.runs
        if entry is None:
            return
        if isinstance(entry, OrmRunControlConfig):
            require_bridge(
                "Run control", RUN_CONTROL_BRIDGE, orm_active=bundle_active(builder, "orm")
            )
            # The bridge is optional; it was just checked to be installed.
            from xtr_ai_orm_run_control import RunMappingDriver  # noqa: PLC0415

            builder.set_parameter(_RUN_CONNECTION, entry.connection)
            builder.set_parameter(_RUN_ENABLED, True)  # noqa: FBT003 — a parameter's value
            if self._run_mappings is not None:
                self._run_mappings.set_driver(RunMappingDriver(entry.table_prefix))
        definition = services.set(run_control_factory(entry))
        if not has_clock and not isinstance(entry, ServiceRunControlConfig):
            _ = definition.set_argument("clock", None)
