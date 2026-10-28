"""Registering the services of one workflow, configured or declared on a class."""

from __future__ import annotations

import importlib
import re
from collections.abc import Callable, Coroutine, Mapping
from typing import TYPE_CHECKING, Annotated, Final, Protocol, assert_never, cast, final

from xtr_dependency_injection import (
    ScopeFactoryInterface,
    ServiceConfigurator,
    ServiceLocator,
    Target,
    named_factory,
)
from xtr_event_dispatcher.bundle import LISTENER_TAG
from xtr_event_dispatcher_contracts import EventDispatcherInterface
from xtr_logging_contracts import LoggerInterface

from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.definition import Definition
from xtr_workflow.event import Event
from xtr_workflow.event_listener import AuditTrailListener, GuardExpression
from xtr_workflow.exception import LogicError
from xtr_workflow.marking_store import MarkingStoreInterface, MethodMarkingStore
from xtr_workflow.metadata import InMemoryMetadataStore
from xtr_workflow.registry import Registry
from xtr_workflow.state_machine import StateMachine
from xtr_workflow.support_strategy import (
    InstanceOfSupportStrategy,
    WorkflowSupportStrategyInterface,
)
from xtr_workflow.validator import (
    DefinitionValidatorInterface,
    StateMachineValidator,
    WorkflowValidator,
)
from xtr_workflow.workflow import Workflow
from xtr_workflow.workflow_interface import WorkflowInterface
from xtr_workflow.workflow_type import WorkflowType

from ._built_transitions import built_transitions
from ._injecting_factory import injecting_factory
from ._unit_of_work_guard_listener import UnitOfWorkGuardListener
from .workflow_definition_config import WorkflowDefinitionConfig

if TYPE_CHECKING:
    from xtr_workflow.event_listener.guard_listener import GuardListener

__all__ = ["WORKFLOW_CHANNEL", "WORKFLOW_TAG", "WorkflowServiceRegistrar"]

WORKFLOW_TAG: Final = "workflow"
"""The tag every workflow carries, with what it was registered from."""

WORKFLOW_CHANNEL: Final = "workflow"
"""The logging channel the audit trail writes to."""

_GUARD_LISTENER_MODULE: Final = "xtr_workflow.event_listener.guard_listener"
"""Imported only for a workflow with guards: it needs the security core."""

_NOT_IN_A_NAME: Final = re.compile(r"\W")

_NO_BUNDLE: Final = frozenset[str]()


class _AuditTrail(Protocol):
    """What the dispatcher calls on a workflow's audit trail.

    The audit trail is registered under this type, not its own: as an event
    subscriber, its own would also make it hear every workflow's events.
    """

    def on_leave(self, event: Event) -> None: ...

    def on_transition(self, event: Event) -> None: ...

    def on_enter(self, event: Event) -> None: ...


@final
class WorkflowServiceRegistrar:
    """Registers the services of a workflow: its definition, the workflow, its listeners.

    Shared by the workflows of the configuration and those declared with
    ``@as_workflow``, so both are registered alike, and a name is taken by
    one of them only. The definition is built here, as the objects it is
    made of, and checked by its validators before anything is registered:
    a definition no workflow could run fails the build.

    Each workflow is registered as ``WorkflowInterface`` under its name, the
    way to inject it; its definition and metadata store are under its name too.
    """

    __slots__ = ("_active", "_defined_by", "_registered")

    def __init__(self, active_bundles: frozenset[str] = _NO_BUNDLE) -> None:
        """Register workflows into a build where ``active_bundles`` are active."""
        self._active = active_bundles
        self._defined_by: dict[str, str | None] = {}
        self._registered: list[tuple[str, WorkflowSupportStrategyInterface | str]] = []

    def register(
        self,
        services: ServiceConfigurator,
        name: str,
        config: WorkflowDefinitionConfig,
        source_class: type | None = None,
    ) -> None:
        """Register the workflow ``name`` configured by ``config``.

        Args:
            services: Where the services are registered.
            name: The name of the workflow.
            config: Its configuration.
            source_class: The class declaring it, for one declared with ``@as_workflow``.

        Raises:
            LogicError: If the name is taken, or the workflow needs a bundle
                that is not active: the event dispatcher and logging for an
                audit trail, security for guards.
            InvalidDefinitionError: If a validator refuses the definition.
        """
        self._claim(name, source_class)
        built = built_transitions(name, config)
        places_metadata = {place.name: place.metadata for place in config.places if place.metadata}
        metadata_store = InMemoryMetadataStore(config.metadata, places_metadata, built.metadata)
        definition = Definition(
            [place.name for place in config.places],
            built.transitions,
            list(config.initial_marking),
            metadata_store,
        )
        validators = (*config.definition_validators, _validator_of(config.type))
        for validator in validators:
            validator().validate(definition, name)

        _ = services.instance(metadata_store, qualifier=name)
        _ = services.instance(definition, qualifier=name)
        factory = named_factory(self._workflow_factory(name, config, definition), _named(name))
        _ = (
            services.set(factory, qualifier=name)
            .add_tag(
                WORKFLOW_TAG,
                name=name,
                type=config.type,
                supports=config.supports,
                support_strategy=config.support_strategy,
                source_class=source_class,
                metadata=dict(config.metadata),
                definition_validators=validators,
            )
            .add_tag(f"workflow.{config.type.value}", name=name)
        )

        if config.supports:
            self._registered.extend((name, InstanceOfSupportStrategy(c)) for c in config.supports)
        elif config.support_strategy is not None:
            self._registered.append((name, config.support_strategy))
        if config.audit_trail.enabled:
            self._register_audit_trail(services, name)
        if built.guards:
            self._register_guard_listener(services, name, built.guards)

    def registry_factory(self) -> Callable[..., Coroutine[None, None, Registry]]:
        """Return the factory of the registry, holding every workflow that says what it moves.

        The workflows are read when the registry is built, so those declared
        with ``@as_workflow``, registered after it, are in it too.
        """
        registered = self._registered

        async def registry(
            workflows: ServiceLocator[WorkflowInterface],
            strategies: ServiceLocator[WorkflowSupportStrategyInterface],
        ) -> Registry:
            built = Registry()
            for name, strategy in registered:
                support_strategy = (
                    await strategies.get(strategy) if isinstance(strategy, str) else strategy
                )
                built.add_workflow(await workflows.get(name), support_strategy)
            return built

        return registry

    def _claim(self, name: str, source_class: type | None) -> None:
        """Take ``name`` for the workflow ``source_class`` declares, or the configuration's.

        Raises:
            LogicError: If a class declares a workflow whose name is taken.
        """
        if source_class is not None and name in self._defined_by:
            other = self._defined_by[name]
            by = "the configuration" if other is None else f'"{other}"'
            raise LogicError(
                f'The workflow "{name}" defined by "{class_name(source_class)}" is already '
                f"defined by {by}."
            )
        self._defined_by[name] = None if source_class is None else class_name(source_class)

    def _workflow_factory(
        self, name: str, config: WorkflowDefinitionConfig, definition: Definition
    ) -> Callable[..., WorkflowInterface]:
        """Return the factory of the workflow, taking what its configuration says it needs."""
        parameters: dict[str, object] = {}
        if "event_dispatcher" in self._active:
            parameters["dispatcher"] = EventDispatcherInterface
        store = config.marking_store
        on_subject = store is not None and (store.type is not None or store.property is not None)
        if store is not None and not on_subject and store.service is not None:
            parameters["marking_store"] = Annotated[MarkingStoreInterface, Target(store.service)]
        single_state = config.type is WorkflowType.STATE_MACHINE
        marking_property = (store.property if store is not None else None) or "marking"

        def build(arguments: Mapping[str, object]) -> WorkflowInterface:
            marking_store = (
                MethodMarkingStore(single_state, marking_property)
                if on_subject
                else cast("MarkingStoreInterface | None", arguments.get("marking_store"))
            )
            dispatcher = cast("EventDispatcherInterface | None", arguments.get("dispatcher"))
            workflow_class = StateMachine if single_state else Workflow
            return workflow_class(
                definition, marking_store, dispatcher, name, config.events_to_dispatch
            )

        return injecting_factory(build, parameters, WorkflowInterface)

    def _register_audit_trail(self, services: ServiceConfigurator, name: str) -> None:
        """Log the moves of the workflow's subjects, on the ``workflow`` channel.

        Raises:
            LogicError: If the event dispatcher or the logging bundle is not active.
        """
        for bundle in ("event_dispatcher", "logging"):
            if bundle not in self._active:
                raise LogicError(
                    f'The "{bundle}" bundle is needed to be able to use the audit trail of the '
                    f'"{name}" workflow.'
                )

        def audit_trail(
            logger: Annotated[LoggerInterface, Target(WORKFLOW_CHANNEL)],
        ) -> _AuditTrail:
            return AuditTrailListener(logger)

        listener = services.set(
            named_factory(audit_trail, f"{_named(name)}_audit_trail"), qualifier=name
        )
        for step in ("leave", "transition", "enter"):
            _ = listener.add_tag(LISTENER_TAG, event=f"workflow.{name}.{step}", method=f"on_{step}")

    def _register_guard_listener(
        self,
        services: ServiceConfigurator,
        name: str,
        guards: Mapping[str, list[GuardExpression]],
    ) -> None:
        """Run the workflow's guards, each for the guard event of its transition.

        Raises:
            LogicError: If the security bundle is not active.
        """
        if "security" not in self._active:
            raise LogicError(
                'The "security" bundle is needed to be able to use the workflow guard listener.'
            )

        module = importlib.import_module(_GUARD_LISTENER_MODULE)
        guard_listener = cast("type[object]", module.GuardListener)
        _ = services.set(guard_listener, qualifier=name, lifetime="scoped").set_argument(
            "configuration", dict(guards)
        )

        def listener(scopes: ScopeFactoryInterface) -> UnitOfWorkGuardListener:
            return UnitOfWorkGuardListener(
                scopes, cast("type[GuardListener]", guard_listener), name
            )

        definition = services.set(
            named_factory(listener, f"{_named(name)}_guard_listener"), qualifier=name
        )
        for event_name in guards:
            _ = definition.add_tag(LISTENER_TAG, event=event_name, method="on_transition")


def _validator_of(workflow_type: WorkflowType) -> type[DefinitionValidatorInterface]:
    """Return the validator every definition of ``workflow_type`` is checked by."""
    match workflow_type:
        case WorkflowType.STATE_MACHINE:
            return StateMachineValidator
        case WorkflowType.WORKFLOW:
            return WorkflowValidator
        case _:
            assert_never(workflow_type)


def _named(name: str) -> str:
    """Return the name the factories of the workflow ``name`` carry in the container's report."""
    return "workflow_" + _NOT_IN_A_NAME.sub("_", name)
