"""A class mixing in the trait answers for the workflow it was handed."""

from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, cast, final

import pytest
from xtr_event_dispatcher import EventDispatcher

from tests.fixtures.subject import Subject
from xtr_workflow import Definition, Transition, Workflow, WorkflowInterface
from xtr_workflow.exception import LogicError
from xtr_workflow.marking_store import MethodMarkingStore
from xtr_workflow.metadata import InMemoryMetadataStore
from xtr_workflow.workflow_trait import WorkflowTrait

if TYPE_CHECKING:
    from collections.abc import Callable

    from xtr_workflow.event import EnteredEvent


@final
class _Facade(WorkflowTrait):
    pass


@final
class _ImplementingFacade(WorkflowTrait, WorkflowInterface):
    pass


def _public_methods_of_workflow() -> list[str]:
    return [name for name, _ in inspect.getmembers(Workflow, inspect.isfunction) if name[0] != "_"]


@pytest.mark.parametrize("name", _public_methods_of_workflow())
def test_the_trait_exposes_every_method_of_the_workflow_class(name: str) -> None:
    expected = cast("Callable[..., object]", getattr(Workflow, name))

    exposed = cast("Callable[..., object]", getattr(WorkflowTrait, name))

    assert str(inspect.signature(exposed)) == str(inspect.signature(expected))
    assert inspect.iscoroutinefunction(exposed) == inspect.iscoroutinefunction(expected)


@pytest.mark.anyio
async def test_the_trait_delegates_to_the_workflow() -> None:
    metadata_store = InMemoryMetadataStore({"title": "My workflow"})
    definition = Definition(["a", "b"], [Transition("go", "a", "b")], None, metadata_store)
    marking_store = MethodMarkingStore(single_state=True)
    workflow = Workflow(definition, marking_store, None, "my_workflow")
    facade = _Facade()
    facade.set_workflow(workflow)
    subject = Subject()

    assert facade.get_name() == "my_workflow"
    assert facade.get_definition() is definition
    assert facade.get_marking_store() is marking_store
    assert facade.get_metadata_store() is metadata_store
    assert (await facade.get_marking(subject)).get_places() == {"a": 1}
    assert await facade.can(subject, "go")
    assert (await facade.build_transition_blocker_list(subject, "go")).is_empty()
    enabled = await facade.get_enabled_transition(subject, "go")
    assert enabled is not None
    assert enabled.get_name() == "go"
    assert len(await facade.get_enabled_transitions(subject)) == 1
    assert (await facade.apply(subject, "go", {"foo": "bar"})).get_places() == {"b": 1}
    assert subject.get_context() == {"foo": "bar"}
    assert not await facade.can(subject, "go")


@pytest.mark.anyio
async def test_the_trait_forwards_the_context_of_get_marking() -> None:
    dispatcher = EventDispatcher()
    contexts: list[dict[str, object]] = []

    def remember(event: EnteredEvent) -> None:
        contexts.append(event.get_context())

    dispatcher.add_listener("workflow.entered", remember)
    facade = _Facade()
    facade.set_workflow(
        Workflow(
            Definition(["a", "b"], [Transition("go", "a", "b")]),
            MethodMarkingStore(single_state=True),
            dispatcher,
        )
    )

    _ = await facade.get_marking(Subject(), {"foo": "bar"})

    assert contexts == [{"foo": "bar"}]


def test_the_class_can_implement_the_workflow_interface() -> None:
    facade = _ImplementingFacade()
    facade.set_workflow(Workflow(Definition(["a"], []), None, None, "my_workflow"))

    assert isinstance(facade, WorkflowInterface)
    assert facade.get_name() == "my_workflow"


def test_using_the_trait_before_it_has_a_workflow_is_refused() -> None:
    with pytest.raises(LogicError) as raised:
        _ = _Facade().get_name()

    assert str(raised.value) == (
        f'"{__name__}._Facade" has no workflow yet: call set_workflow() before using it.'
    )
