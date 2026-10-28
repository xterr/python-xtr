"""The xtr-workflow bundle: every configured and declared workflow, and the registry finding them.

An application listing :class:`WorkflowBundle` gets each workflow of its
:class:`~.workflow_config.WorkflowConfig`, and each one a class its scan
finds declares with ``@as_workflow``, registered as ``WorkflowInterface``
under its name — ``Annotated[WorkflowInterface, Target("article")]`` — and,
when it says which subjects it moves, in the
:class:`~xtr_workflow.Registry`. Each workflow dispatches its events
through the event dispatcher, where a listener declares a workflow event by
its class as well as by its name; an audit trail writes to the logging
bundle's ``workflow`` channel; guards ask the security bundle about whoever
is moving the subject. The event dispatcher, logging and console bundles come
along whenever their packages are installed; the security bundle never does,
as it brings an HTTP kernel with it, so an application with guards lists it.
In debug mode, every workflow is traced. With a console, ``workflow:dump``
draws any of them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Final, Never, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    ServiceLocator,
    as_bundle,
    bundle_active,
    named_factory,
    required_bundle,
)
from xtr_event_dispatcher.bundle import EventDispatcherConfig
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

from xtr_workflow.workflow_events import WorkflowEvents
from xtr_workflow.workflow_interface import WorkflowInterface

from ._declared_workflows import (
    misplaced_listeners_on,
    register_declared_workflow,
    workflows_declared_on,
)
from ._injecting_factory import injecting_factory
from .workflow_config import WorkflowConfig
from .workflow_debug_pass import WorkflowDebugPass
from .workflow_service_registrar import WORKFLOW_CHANNEL, WorkflowServiceRegistrar

if TYPE_CHECKING:
    from xtr_workflow.command import WorkflowDumpCommand

__all__ = ["WorkflowBundle"]

_PEERS: Final = ("event_dispatcher", "logging", "security")
"""The bundles whose presence changes what a workflow is registered with."""


@final
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@as_bundle("workflow", config=WorkflowConfig)
class WorkflowBundle(Bundle[WorkflowConfig]):
    """Registers the configured and declared workflows, the registry, and their listeners."""

    def __init__(self) -> None:
        """Register into a build with no peer, until :meth:`build` says which are active."""
        self._registrar = WorkflowServiceRegistrar()

    @override
    def prepend_extension(self, builder: ContainerBuilder) -> None:
        """Map each workflow event class to its name, and add the ``workflow`` logging channel."""
        if bundle_active(builder, "event_dispatcher"):
            builder.prepend_extension_config("event_dispatcher", _add_event_aliases)
        if bundle_active(builder, "logging"):
            builder.prepend_extension_config("logging", _add_workflow_channel)

    @override
    def build(self, builder: ContainerBuilder) -> None:
        """Register the workflows the scan finds declared; trace every workflow in debug mode."""
        active = frozenset(peer for peer in _PEERS if bundle_active(builder, peer))
        self._registrar = WorkflowServiceRegistrar(active)
        builder.register_attribute_for_autoconfiguration(
            workflows_declared_on, register_declared_workflow(self._registrar)
        )
        builder.register_attribute_for_autoconfiguration(misplaced_listeners_on, _register_nothing)
        if builder.get_parameter("kernel.debug"):
            builder.add_compiler_pass(WorkflowDebugPass())

    @override
    def load_extension(
        self,
        config: WorkflowConfig,
        services: ServiceConfigurator,
        builder: ContainerBuilder,
    ) -> None:
        """Register the registry, every configured workflow, and the dump command with a console."""
        registrar = self._registrar
        _ = services.set(named_factory(registrar.registry_factory(), "workflow_registry"))
        for name, workflow in config.workflows.items():
            registrar.register(services, name, workflow)
        if bundle_active(builder, "console"):
            services.load("xtr_workflow.command")

    @override
    def process(self, builder: ContainerBuilder) -> None:
        """Build the dump command, with a console, from the workflows and any active dispatcher.

        The console registers the command as its class, whose constructor
        takes the workflows behind the service provider contract, and a
        dispatcher only when there is one; it is built instead by a factory
        taking the workflows' locator, and the dispatcher their listeners are
        on only when the event dispatcher bundle is active.
        """
        if not bundle_active(builder, "console"):
            return
        from xtr_workflow.command import WorkflowDumpCommand  # noqa: PLC0415 -- only with a console

        definition = builder.get_definition(WorkflowDumpCommand)
        definition.provider = _dump_command_factory(
            WorkflowDumpCommand, with_dispatcher=bundle_active(builder, "event_dispatcher")
        )
        definition.kind = "factory"


def _add_event_aliases(config: EventDispatcherConfig) -> EventDispatcherConfig:
    """Let a listener declare a workflow event by its class, as it is dispatched by name."""
    aliases: dict[str | type, str | type] = dict(WorkflowEvents.ALIASES.items())
    return config.with_event_aliases(aliases)


def _add_workflow_channel(config: object) -> object:
    """Declare the ``workflow`` channel through the logging config's own ``with_channels``.

    Duck-typed: this package depends on the logging contracts only, never on
    xtr-logging, so it asks the config it is handed rather than importing its
    type.
    """
    with_channels = cast("Callable[[str], object] | None", getattr(config, "with_channels", None))
    return with_channels(WORKFLOW_CHANNEL) if with_channels is not None else config


def _register_nothing(obj: object, found: Never, services: ServiceConfigurator) -> None:
    """Never called: the reader it goes with finds nothing, or raises."""
    del obj, found, services


def _dump_command_factory(
    command_class: type[WorkflowDumpCommand], *, with_dispatcher: bool
) -> Callable[..., WorkflowDumpCommand]:
    """Return the dump command's factory: the workflows by name, and the dispatcher if asked."""
    parameters: dict[str, object] = {"workflows": ServiceLocator[WorkflowInterface]}
    if with_dispatcher:
        parameters["dispatcher"] = ListenerIntrospectionInterface

    def build(arguments: Mapping[str, object]) -> WorkflowDumpCommand:
        return command_class(
            cast("ServiceLocator[WorkflowInterface]", arguments["workflows"]),
            cast("ListenerIntrospectionInterface | None", arguments.get("dispatcher")),
        )

    return injecting_factory(build, parameters, command_class)
