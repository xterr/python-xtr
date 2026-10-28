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
is moving the subject. In debug mode, every workflow is traced.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final, Never, cast, final

from typing_extensions import override
from xtr_dependency_injection import (
    Bundle,
    ContainerBuilder,
    ServiceConfigurator,
    as_bundle,
    bundle_active,
    named_factory,
    required_bundle,
)
from xtr_event_dispatcher.bundle import EventDispatcherConfig

from xtr_workflow.workflow_events import WorkflowEvents

from ._declared_workflows import (
    misplaced_listeners_on,
    register_declared_workflow,
    workflows_declared_on,
)
from .workflow_config import WorkflowConfig
from .workflow_debug_pass import WorkflowDebugPass
from .workflow_service_registrar import WORKFLOW_CHANNEL, WorkflowServiceRegistrar

__all__ = ["WorkflowBundle"]

_PEERS: Final = ("event_dispatcher", "logging", "security")
"""The bundles whose presence changes what a workflow is registered with."""


@final
@required_bundle("xtr_event_dispatcher.bundle:EventDispatcherBundle", ignore_on_invalid=True)
@required_bundle("xtr_console.bundle:ConsoleBundle", ignore_on_invalid=True)
@required_bundle("xtr_logging.bundle:LoggingBundle", ignore_on_invalid=True)
@required_bundle("xtr_security.bundle:SecurityBundle", ignore_on_invalid=True)
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
        """Register the registry and every configured workflow."""
        del builder
        registrar = self._registrar
        _ = services.set(named_factory(registrar.registry_factory(), "workflow_registry"))
        for name, workflow in config.workflows.items():
            registrar.register(services, name, workflow)


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
