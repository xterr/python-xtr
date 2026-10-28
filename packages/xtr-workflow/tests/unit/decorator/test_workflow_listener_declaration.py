"""A workflow listener is an event listener, marked so its workflow class can tell it apart."""

from __future__ import annotations

from typing import cast

from xtr_event_dispatcher.decorator import EventListenerDeclaration, listeners_declared_on
from xtr_event_dispatcher.decorator.event_listener_declaration import recorded_on

from xtr_workflow.decorator import WorkflowListenerDeclaration
from xtr_workflow.decorator.workflow_listener_declaration import (
    workflow_listener,
    workflow_listeners_recorded_on,
)


def test_the_listener_is_declared_to_the_event_dispatcher_and_marked() -> None:
    def listener() -> None: ...

    _ = workflow_listener("workflow.guard", priority=3, dispatcher="audit")(listener)

    declaration = EventListenerDeclaration("workflow.guard", priority=3, dispatcher="audit")
    assert listeners_declared_on(listener) == (declaration,)
    assert workflow_listeners_recorded_on(listener) == (WorkflowListenerDeclaration(declaration),)


def test_repeating_it_marks_each_declaration() -> None:
    def listener() -> None: ...

    _ = workflow_listener("workflow.enter")(workflow_listener("workflow.leave")(listener))

    assert workflow_listeners_recorded_on(listener) == tuple(
        WorkflowListenerDeclaration(declaration) for declaration in recorded_on(listener)
    )


def test_on_a_class_it_marks_the_class_naming_the_method() -> None:
    @workflow_listener("workflow.completed", method="handle")
    class Listener:
        def handle(self) -> None: ...

    assert workflow_listeners_recorded_on(Listener) == (
        WorkflowListenerDeclaration(EventListenerDeclaration("workflow.completed", "handle")),
    )


def test_a_subclass_does_not_carry_the_marks_of_its_base() -> None:
    @workflow_listener("workflow.completed", method="handle")
    class Listener:
        def handle(self) -> None: ...

    class Child(Listener): ...

    assert workflow_listeners_recorded_on(Child) == ()


def test_above_staticmethod_it_marks_the_function_it_wraps() -> None:
    class Listener:
        @workflow_listener("workflow.announce")
        @staticmethod
        def announce() -> None: ...

    function = cast("staticmethod[[], None]", vars(Listener)["announce"]).__func__
    assert workflow_listeners_recorded_on(function) == (
        WorkflowListenerDeclaration(EventListenerDeclaration("workflow.announce")),
    )


def test_an_unmarked_object_carries_no_mark() -> None:
    assert workflow_listeners_recorded_on(object()) == ()
