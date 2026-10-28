"""The workflows, and the workflow listeners, the application's scan finds.

The bundle hands both readers to the container's autoconfiguration, which
runs them over every class and function the scan finds:
:func:`workflows_declared_on` reads the workflow a class declares with
``@as_workflow``, which :func:`register_declared_workflow` registers;
:func:`misplaced_listeners_on` refuses a listener naming a place or a
transition of no workflow.
"""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable, Mapping
from typing import Annotated, Final, Never, cast

from xtr_dependency_injection import (
    AutowireDecorated,
    ServiceConfigurator,
    Target,
    named_factory,
)
from xtr_event_dispatcher.decorator.event_listener_declaration import listeners_declared_on

from xtr_workflow.decorator._build_event_name import NAME_PLACEHOLDER
from xtr_workflow.decorator._workflow_name import class_name, workflow_name
from xtr_workflow.decorator.as_workflow import workflow_declared_on
from xtr_workflow.exception import LogicError
from xtr_workflow.workflow_interface import WorkflowInterface
from xtr_workflow.workflow_trait import WorkflowTrait

from ._declaration_reader import read_declaration
from ._injecting_factory import injecting_factory
from .workflow_definition_config import WorkflowDefinitionConfig
from .workflow_service_registrar import WorkflowServiceRegistrar

__all__ = ["misplaced_listeners_on", "register_declared_workflow", "workflows_declared_on"]

_PLACEHOLDER_PREFIX: Final = f"workflow.{NAME_PLACEHOLDER}."

_NOT_IN_A_NAME: Final = re.compile(r"\W")

_DeclaredWorkflow = tuple[str, WorkflowDefinitionConfig]


def workflows_declared_on(obj: object) -> tuple[_DeclaredWorkflow, ...]:
    """Return the name and configuration of the workflow ``obj`` declares, if a class declaring one.

    Only the class's own declaration counts: a class deriving a workflow
    class declares no workflow unless decorated too. How the declaration is
    read is :func:`~._declaration_reader.read_declaration`'s.

    Raises:
        LogicError: If the declaration cannot be read into a workflow.
        InvalidArgumentError: If the configuration read is invalid, as one
            written by hand would be.
    """
    if not isinstance(obj, type):
        return ()
    declaration = workflow_declared_on(obj)
    if declaration is None:
        return ()

    return ((workflow_name(declaration.name, obj), read_declaration(obj, declaration)),)


def register_declared_workflow(
    registrar: WorkflowServiceRegistrar,
) -> Callable[[object, _DeclaredWorkflow, ServiceConfigurator], None]:
    """Return the callback registering, through ``registrar``, the workflow a class declares.

    A class mixing in :class:`~xtr_workflow.WorkflowTrait` is registered as a
    service too, and handed its workflow once built — the traced one, in
    debug mode — so it answers for that workflow wherever it is injected.
    """

    def register(obj: object, declared: _DeclaredWorkflow, services: ServiceConfigurator) -> None:
        # The reader finds a workflow on a class only.
        class_ = cast("type", obj)
        name, config = declared
        registrar.register(services, name, config, class_)
        if issubclass(class_, WorkflowTrait):
            _ = services.set(class_)
            factory = named_factory(
                _handing_workflow(class_, name),
                "set_workflow_" + _NOT_IN_A_NAME.sub("_", name),
            )
            _ = services.set(factory, qualifier=f"workflow.{name}").set_decorated_service(class_)

    return register


def misplaced_listeners_on(obj: object) -> tuple[Never, ...]:
    """Refuse ``obj`` when one of its listeners names a place or a transition but no workflow.

    Such a listener means the workflow of its class, which ``@as_workflow``
    names when it decorates the class; one left unnamed sits on a class
    declaring no workflow, or on a function, and would hear nothing. An
    abstract class only lends its listeners to the classes deriving it, and
    is left alone.

    Raises:
        LogicError: If ``obj`` carries such a listener.
    """
    is_class = isinstance(obj, type)
    if not (is_class or inspect.isfunction(obj)) or (is_class and inspect.isabstract(obj)):
        return ()

    for declaration in listeners_declared_on(obj):
        event = declaration.event
        if not (isinstance(event, str) and event.startswith(_PLACEHOLDER_PREFIX)):
            continue
        if isinstance(obj, type):
            method = declaration.method or "__call__"
            listener = f'"{method}()" listener of the "{class_name(obj)}" service'
        else:
            listener = f'"{obj.__module__}.{obj.__qualname__}()" listener'
        raise LogicError(
            f"The {listener} listens to a transition or a place without defining the "
            '"workflow" argument of its decorator; set it, or move the listener to a class '
            'using the "@as_workflow" decorator.'
        )

    return ()


def _handing_workflow(class_: type[WorkflowTrait], name: str) -> Callable[..., WorkflowTrait]:
    """Return the decorator of ``class_``'s service handing it the workflow ``name``."""

    def build(arguments: Mapping[str, object]) -> WorkflowTrait:
        instance = cast("WorkflowTrait", arguments["instance"])
        instance.set_workflow(cast("WorkflowInterface", arguments["workflow"]))
        return instance

    parameters = {
        "instance": Annotated[class_, AutowireDecorated()],  # ty: ignore[invalid-type-form] -- the class decorated is only known here, at runtime
        "workflow": Annotated[WorkflowInterface, Target(name)],
    }
    return injecting_factory(build, parameters, class_)
