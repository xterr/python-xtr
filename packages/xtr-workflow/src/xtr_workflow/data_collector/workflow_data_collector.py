"""Every workflow call the profiled request made, and the workflows it could make them to."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final, NotRequired, TypedDict, cast, final

from xtr_http_kernel.data_collector import RequestTrace

from xtr_workflow.decorator._workflow_name import class_name
from xtr_workflow.exception import NotEnabledTransitionError
from xtr_workflow.marking import Marking

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence

    from xtr_http_kernel.data_collector import ProfiledRequest

    from xtr_workflow.transition import Transition
    from xtr_workflow.transition_blocker_list import TransitionBlockerList

__all__ = ["WorkflowDataCollector"]

_NAME: Final = "workflow"
_TAKES_A_TRANSITION: Final = frozenset(
    {"can", "build_transition_blocker_list", "apply", "get_enabled_transition"}
)
_RETURNS_A_MARKING: Final = frozenset({"get_marking", "apply"})


class _BlockerData(TypedDict):
    message: str
    code: str
    expression: NotRequired[str]


# "class" is a keyword, so only the functional form can name the key.
_Error = TypedDict("_Error", {"class": str, "message": str})


class _CallData(TypedDict):
    workflow: str
    method: str
    subject: str
    transition: str | None
    previous_marking: list[str] | None
    marking: list[str] | None
    result: bool | list[_BlockerData] | list[str] | None
    blocked: bool
    duration_ms: float
    error: _Error | None


@final
class WorkflowDataCollector:
    """Keeps every call the workflows answered while the profiled request was handled.

    A traced workflow hands :meth:`record` each call as it ends; the call is
    turned into plain data there and then, because the subject goes on moving
    after it and a later read would show where it went, not where it was. The
    calls belong to the request being profiled — two served at once each see
    their own — and nothing is kept, or even turned into data, outside one.
    They are read once the response has left, so a call made while the body
    streamed is in too.

    The workflows the application defines are known when the container is
    built, and handed to the constructor as plain data.
    """

    __slots__ = ("_trace", "_workflows")

    def __init__(self, workflows: Sequence[Mapping[str, object]]) -> None:
        """Show ``workflows``, each a ``name``, a ``type`` and what it ``supports``, as defined."""
        self._workflows = tuple(dict(workflow) for workflow in workflows)
        self._trace: RequestTrace[_CallData] = RequestTrace(_NAME)

    @property
    def name(self) -> str:
        """``"workflow"``."""
        return _NAME

    def begin_request(self) -> None:
        """Start recording the profiled request that just arrived."""
        self._trace.begin()

    def record(self, workflow: str, call: Mapping[str, object]) -> None:
        """Keep ``call``, a traced workflow's record of one call to ``workflow``, for the request.

        Outside a profiled request the call is left as it is: nothing reads it.
        """
        if self._trace.is_recording():
            self._trace.record(_call(workflow, call))

    def collect(self, profiled: ProfiledRequest) -> dict[str, object]:
        """Return the defined workflows; the calls follow once the response has left."""
        del profiled
        return {"workflows": [dict(workflow) for workflow in self._workflows]}

    def late_collect(self, data: dict[str, object], profiled: ProfiledRequest) -> dict[str, object]:
        """Return every call the request made, and how many applied a transition or were blocked."""
        del profiled
        calls = list(self._trace.entries())
        return {
            **data,
            "calls": calls,
            "counts": {
                "calls": len(calls),
                "applied": sum(
                    1 for call in calls if call["method"] == "apply" and call["error"] is None
                ),
                "blocked": sum(1 for call in calls if call["blocked"]),
            },
        }


def _call(workflow: str, call: Mapping[str, object]) -> _CallData:
    method = str(call["method"])
    arguments = cast("tuple[object, ...]", call["args"])
    returned = call.get("return")
    raised = call.get("exception")
    transition = arguments[1] if method in _TAKES_A_TRANSITION else None
    if isinstance(raised, NotEnabledTransitionError):
        result = _blockers(raised.get_transition_blocker_list())
    else:
        result = _answer(method, returned) if raised is None else None
    return {
        "workflow": workflow,
        "method": method,
        "subject": class_name(type(arguments[0])),
        "transition": transition if isinstance(transition, str) else None,
        "previous_marking": _places(call.get("previous_marking")),
        "marking": _places(returned) if method in _RETURNS_A_MARKING else None,
        "result": result,
        "blocked": isinstance(raised, NotEnabledTransitionError)
        or (method == "can" and result is False),
        "duration_ms": cast("float", call["duration"]),
        "error": _error(raised),
    }


def _answer(method: str, returned: object) -> bool | list[_BlockerData] | list[str] | None:
    """Return what the call answered, as plain data; ``None`` for a marking, kept apart."""
    match method:
        case "can":
            return returned is True
        case "build_transition_blocker_list":
            return _blockers(cast("TransitionBlockerList", returned))
        case "get_enabled_transitions":
            return [transition.get_name() for transition in cast("list[Transition]", returned)]
        case "get_enabled_transition":
            return [] if returned is None else [cast("Transition", returned).get_name()]
        case _:
            return None


def _blockers(blockers: TransitionBlockerList) -> list[_BlockerData]:
    found: list[_BlockerData] = []
    for blocker in blockers:
        data: _BlockerData = {"message": blocker.get_message(), "code": blocker.get_code()}
        expression = blocker.get_parameters().get("expression")
        if isinstance(expression, str):
            data["expression"] = expression
        found.append(data)
    return found


def _places(marking: object) -> list[str] | None:
    return list(marking.get_places()) if isinstance(marking, Marking) else None


def _error(raised: object) -> _Error | None:
    if not isinstance(raised, BaseException):
        return None
    return {"class": class_name(type(raised)), "message": str(raised)}
