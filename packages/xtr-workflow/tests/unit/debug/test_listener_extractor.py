"""The listener extractor lists who listens to each step of a workflow, named after their code.

A listener is named after what it runs, through the lazy and traced wrappers
an event dispatcher puts around it; a guard listener also names the guards it
runs for the transition.
"""

from __future__ import annotations

import functools
import inspect
from typing import TYPE_CHECKING, TypeAlias, final

import pytest
from xtr_event_dispatcher import CompiledEventDispatcher, EventDispatcher, LazyListener
from xtr_event_dispatcher.debug import TraceableEventDispatcher, WrappedListener
from xtr_security_core import (
    AccessDecisionManager,
    AuthenticationTrustResolver,
    AuthorizationChecker,
    RoleHierarchy,
    TokenStorage,
)

from tests.support.definitions import (
    create_complex_workflow_definition,
    create_simple_workflow_definition,
)
from xtr_workflow import Definition, Transition, Workflow
from xtr_workflow.debug.listener_extractor import ListenerExtractor
from xtr_workflow.event_listener import GuardExpression
from xtr_workflow.event_listener.guard_listener import GuardListener
from xtr_workflow.exception import LogicError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable, Mapping, Sequence

    from xtr_workflow.event_listener import GuardContext

pytestmark = pytest.mark.anyio

_Guard: TypeAlias = "GuardExpression | Callable[[GuardContext], bool | Awaitable[bool]]"

GUARD_LISTENER = "xtr_workflow.event_listener.guard_listener.GuardListener.on_transition()"


@final
class _Listeners:
    @staticmethod
    def noop() -> None:
        pass

    @classmethod
    def class_noop(cls) -> None:
        pass

    def on_leave(self) -> None:
        pass


@final
class _CallableListener:
    def __call__(self) -> None:
        pass


def _keeping_what_it_wraps(function: Callable[[], None]) -> Callable[[], None]:
    @functools.wraps(function)
    def wrapper() -> None:
        function()

    return wrapper


@_keeping_what_it_wraps
def _decorated() -> None:
    pass


def _my_expression(context: GuardContext) -> bool:
    del context
    return True


async def _build_listeners() -> object:
    return _Listeners()


def _where(function: Callable[..., object]) -> str:
    """Return where ``function``'s code starts, as inspect finds its source."""
    return f"{inspect.getsourcefile(function)}:{inspect.getsourcelines(function)[1]}"


def _on_leave() -> dict[str, object]:
    """Return how the extractor shows ``_Listeners.on_leave``."""
    return {"title": f"{__name__}._Listeners.on_leave()", "file": _where(_Listeners.on_leave)}


def _guard_listener(configuration: Mapping[str, Sequence[_Guard]]) -> GuardListener:
    token_storage = TokenStorage()
    return GuardListener(
        configuration,
        token_storage,
        AuthorizationChecker(token_storage, AccessDecisionManager()),
        AuthenticationTrustResolver(),
        RoleHierarchy({}),
    )


async def _listed(
    dispatcher: EventDispatcher | TraceableEventDispatcher,
) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Return what the extractor lists for a workflow of one place, ``a``, nobody moves out of."""
    return await ListenerExtractor(dispatcher).extract_listeners("article", Definition(["a"], []))


async def test_a_workflow_nobody_listens_to_lists_no_listener() -> None:
    workflow = Workflow(create_complex_workflow_definition(), name="workflow1")
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.workflow2.leave.a", _Listeners.noop)

    listeners = await ListenerExtractor(dispatcher).extract_listeners(
        workflow.get_name(), workflow.get_definition()
    )

    assert listeners == {}


async def test_each_listener_is_titled_after_the_code_it_runs() -> None:
    workflow = Workflow(create_simple_workflow_definition(), name="workflow2")
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.workflow2.leave.a", lambda: True)
    dispatcher.add_listener("workflow.workflow2.leave.a", _Listeners.noop)
    dispatcher.add_listener("workflow.workflow2.leave.a", _Listeners().on_leave)
    dispatcher.add_listener("workflow.workflow2.leave.a", _Listeners.class_noop)
    dispatcher.add_listener("workflow.workflow2.leave.a", print)

    listeners = await ListenerExtractor(dispatcher).extract_listeners(
        workflow.get_name(), workflow.get_definition()
    )

    titles = [summary["title"] for summary in listeners["place__a"]["workflow.workflow2.leave.a"]]
    assert "<lambda>" in str(titles[0])
    assert titles[1:] == [
        f"{__name__}._Listeners.noop()",
        f"{__name__}._Listeners.on_leave()",
        f"{__name__}._Listeners.class_noop()",
        "builtins.print()",
    ]


async def test_a_guard_listener_lists_the_guards_it_runs_for_the_transition() -> None:
    workflow = Workflow(create_simple_workflow_definition(), name="workflow2")
    guard_listener = _guard_listener({"workflow.workflow2.guard.t1": [_my_expression]})
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.workflow2.guard.t1", guard_listener.on_transition)

    listeners = await ListenerExtractor(dispatcher).extract_listeners(
        workflow.get_name(), workflow.get_definition()
    )

    assert listeners == {
        "transition__0": {
            "workflow.workflow2.guard.t1": [
                {
                    "title": GUARD_LISTENER,
                    "file": _where(GuardListener.on_transition),
                    "guardExpressions": [f"{__name__}._my_expression"],
                }
            ]
        }
    }


async def test_a_guard_expression_is_listed_for_the_transition_it_guards_only() -> None:
    guarded = Transition("go", "c", "b")
    guard_listener = _guard_listener(
        {"workflow.article.guard.go": [GuardExpression(guarded, _my_expression)]}
    )
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.article.guard.go", guard_listener.on_transition)
    definition = Definition(["a", "b", "c"], [Transition("go", "a", "b"), guarded])

    listeners = await ListenerExtractor(dispatcher).extract_listeners("article", definition)

    assert [
        listeners[node]["workflow.article.guard.go"][0]["guardExpressions"]
        for node in ("transition__0", "transition__1")
    ] == [[], [f"{__name__}._my_expression"]]


async def test_a_guard_listener_listening_to_a_place_is_refused() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", _guard_listener({}).on_transition)

    with pytest.raises(LogicError) as raised:
        _ = await _listed(dispatcher)

    assert str(raised.value) == "Missing event name or transition."


async def test_each_step_is_listed_under_its_three_names_in_order() -> None:
    dispatcher = EventDispatcher()
    steps = [("leave", "a"), ("enter", "a"), ("entered", "a")]
    steps += [("guard", "go"), ("transition", "go"), ("completed", "go"), ("announce", "go")]
    for step, node in steps:
        for event_name in (
            f"workflow.{step}",
            f"workflow.article.{step}",
            f"workflow.article.{step}.{node}",
        ):
            dispatcher.add_listener(event_name, _Listeners.noop)
    definition = Definition(["a", "b"], [Transition("go", "a", "b")])

    listeners = await ListenerExtractor(dispatcher).extract_listeners("article", definition)

    assert {node: list(events) for node, events in listeners.items()} == {
        "place__a": [
            "workflow.leave",
            "workflow.article.leave",
            "workflow.article.leave.a",
            "workflow.enter",
            "workflow.article.enter",
            "workflow.article.enter.a",
            "workflow.entered",
            "workflow.article.entered",
            "workflow.article.entered.a",
        ],
        "place__b": [
            "workflow.leave",
            "workflow.article.leave",
            "workflow.enter",
            "workflow.article.enter",
            "workflow.entered",
            "workflow.article.entered",
        ],
        "transition__0": [
            "workflow.guard",
            "workflow.article.guard",
            "workflow.article.guard.go",
            "workflow.transition",
            "workflow.article.transition",
            "workflow.article.transition.go",
            "workflow.completed",
            "workflow.article.completed",
            "workflow.article.completed.go",
            "workflow.announce",
            "workflow.article.announce",
            "workflow.article.announce.go",
        ],
    }


async def test_each_listener_is_given_the_file_and_line_its_code_starts_at() -> None:
    dispatcher = EventDispatcher()
    for listener in (_Listeners.noop, _Listeners().on_leave, _CallableListener(), _decorated):
        dispatcher.add_listener("workflow.leave", listener)

    listeners = await _listed(dispatcher)

    assert [summary["file"] for summary in listeners["place__a"]["workflow.leave"]] == [
        _where(_Listeners.noop),
        _where(_Listeners.on_leave),
        _where(_CallableListener.__call__),
        _where(_decorated),
    ]


async def test_a_listener_built_into_the_interpreter_has_no_file() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", print)

    listeners = await _listed(dispatcher)

    assert listeners == {
        "place__a": {"workflow.leave": [{"title": "builtins.print()", "file": None}]}
    }


async def test_a_built_in_method_of_an_object_is_titled_by_its_qualified_name_alone() -> None:
    appended: list[object] = []
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", appended.append)

    listeners = await _listed(dispatcher)

    assert listeners == {"place__a": {"workflow.leave": [{"title": "list.append()", "file": None}]}}


async def test_a_class_listening_is_titled_after_itself_and_has_no_file() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", _CallableListener)

    listeners = await _listed(dispatcher)

    assert listeners == {
        "place__a": {"workflow.leave": [{"title": f"{__name__}._CallableListener()", "file": None}]}
    }


async def test_a_lazy_listener_is_named_after_the_method_it_builds_into() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", LazyListener(_build_listeners, "on_leave"))

    listeners = await _listed(dispatcher)

    assert listeners == {"place__a": {"workflow.leave": [_on_leave()]}}


async def test_a_lazy_listener_of_a_callable_object_is_named_after_that_object() -> None:
    async def build() -> object:
        return _CallableListener()

    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", LazyListener(build))

    listeners = await _listed(dispatcher)

    assert listeners == {
        "place__a": {
            "workflow.leave": [
                {
                    "title": f"{__name__}._CallableListener.__call__()",
                    "file": _where(_CallableListener.__call__),
                }
            ]
        }
    }


async def test_a_traced_listener_is_named_after_the_listener_it_wraps() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", WrappedListener(_Listeners().on_leave))

    listeners = await _listed(dispatcher)

    assert listeners == {"place__a": {"workflow.leave": [_on_leave()]}}


async def test_a_traced_lazy_listener_is_named_after_what_the_lazy_one_builds() -> None:
    lazy = LazyListener(_build_listeners, "on_leave")
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.leave", WrappedListener(lazy))

    listeners = await _listed(dispatcher)

    assert listeners == {"place__a": {"workflow.leave": [_on_leave()]}}


async def test_the_listeners_of_a_traced_container_dispatcher_are_named_after_their_code() -> None:
    lazy = LazyListener(_build_listeners, "on_leave")
    dispatcher = TraceableEventDispatcher(CompiledEventDispatcher({"workflow.leave": [(lazy, 0)]}))

    listeners = await _listed(dispatcher)

    assert listeners == {"place__a": {"workflow.leave": [_on_leave()]}}


async def test_a_lazily_built_guard_listener_lists_its_guards() -> None:
    guard_listener = _guard_listener({"workflow.article.guard.go": [_my_expression]})

    async def build() -> object:
        return guard_listener

    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.article.guard.go", LazyListener(build, "on_transition"))
    definition = Definition(["a", "b"], [Transition("go", "a", "b")])

    listeners = await ListenerExtractor(dispatcher).extract_listeners("article", definition)

    assert listeners == {
        "transition__0": {
            "workflow.article.guard.go": [
                {
                    "title": GUARD_LISTENER,
                    "file": _where(GuardListener.on_transition),
                    "guardExpressions": [f"{__name__}._my_expression"],
                }
            ]
        }
    }
