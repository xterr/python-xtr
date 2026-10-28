# Declaring a workflow on a class

`@as_workflow` records on a class what the configuration would otherwise say. The workflow bundle
reads the declaration from every class its scan finds and registers the workflow; without the
container the declaration is inert data, and the class is just a class.

Everything here comes from `xtr_workflow.decorator`.

## A full example

```python
from enum import StrEnum
from typing import Annotated, ClassVar

from xtr_workflow import WorkflowTrait, WorkflowType
from xtr_workflow.decorator import Place, Transition, as_guard_listener, as_workflow
from xtr_workflow.event import GuardEvent


class Step(StrEnum):
    NEW = "new"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class Task:
    step: Step | None = None
    blocked: bool = False


@as_workflow(
    supports=Task,
    marking_property="step",
    places=Step,
    place_markers={Step.NEW: Place(description="Waiting to be picked up", initial=True)},
    metadata={"title": "Task"},
)
class TaskStateMachine(WorkflowTrait):
    START: ClassVar[Annotated[str, Transition(froms=Step.NEW, tos=Step.PROCESSING)]] = "start"
    FINISH: ClassVar[
        Annotated[
            str,
            Transition(froms=Step.PROCESSING, tos=Step.DONE),
            Transition(froms=Step.FAILED, tos=Step.DONE),
        ]
    ] = "finish"
    FAIL: ClassVar[Annotated[str, Transition(froms=Step.PROCESSING, tos=Step.FAILED)]] = "fail"

    async def start(self, task: Task) -> None:
        _ = await self.apply(task, self.START, {"started_by": "start()"})

    @as_guard_listener(transition=START)
    def refuse_blocked_tasks(self, event: GuardEvent) -> None:
        subject = event.get_subject()
        if isinstance(subject, Task) and subject.blocked:
            event.set_blocked(True, "The task is blocked.")
```

## `@as_workflow` arguments

| Argument | Does |
| --- | --- |
| `name=` | The workflow's name; derived from the class otherwise |
| `type=` | `WorkflowType.STATE_MACHINE` (default) or `WorkflowType.WORKFLOW` |
| `supports=` | The class, or classes, of the subjects it moves — puts it in the `Registry` |
| `support_strategy=` | The qualifier of a `WorkflowSupportStrategyInterface` service instead |
| `initial_marking=` | The place, or places, a subject starts in |
| `marking_property=` | The subject's attribute (or `get_`/`set_` pair) keeping the marking |
| `marking_store=` | The qualifier of a `MarkingStoreInterface` service instead |
| `description=` | Kept under `metadata["description"]` |
| `metadata=` | The workflow's metadata |
| `audit_trail=` | `True` logs every move on the `workflow` channel |
| `events_to_dispatch=` | Which events ever go out; see `references/events.md` |
| `definition_validators=` | Validators run on the definition besides the type's own |
| `places=` | A string enum whose every member is a place, and outside which no place is named |
| `place_markers=` | A `Place` per enum member that needs one, keyed by the member |

- The derived name is the class's name snake-cased, without a `Workflow` or `StateMachine` suffix:
  `TaskStateMachine` → `task`, `PullRequestStateMachine` → `pull_request`.
- `supports` with `support_strategy`, `marking_property` with `marking_store`, or a `description`
  plus one in `metadata`, each raise `LogicError` at decoration.
- The declaration belongs to the decorated class alone: the reader looks in the class's own
  `__dict__`, so a subclass declares nothing unless it is decorated too. Decorating one class twice
  raises.
- A name already used by the configuration, or by another class, is a build error naming both.
- With neither `supports` nor `support_strategy` the workflow is not in the `Registry` — it is
  reached by injection only.

## The `Transition` marker

`Transition` here is **not** `xtr_workflow.Transition`: it is the marker, and it goes inside
`Annotated` on a class constant valued with the transition's name.

```python
SUBMIT: ClassVar[Annotated[str, Transition(froms="draft", tos="review")]] = "submit"
```

| Argument | Does |
| --- | --- |
| `froms=` | The places it leaves: a name, a string-enum member, an `Arc`, or a sequence of those |
| `tos=` | The places it enters, the same way |
| `guard=` | A callable taking a `GuardContext`; the transition runs only when it answers true |
| `description=` | Kept under `metadata["description"]` |
| `metadata=` | The transition's metadata |

`from` and `to` are not the keywords — `from` is a reserved word, and `froms` / `tos` match
`Transition.get_froms()` / `get_tos()` on the built transition. Repeat the marker inside one
`Annotated` to declare several transitions of that name: a state machine needs one per pair of
places, and a workflow applies every enabled transition of the name at once.

Weigh an arc with `Arc(place, weight)` from `xtr_workflow`; a bare name weighs 1, which is all a
state machine ever uses.

## The `Place` marker

A place a transition leaves or enters is a place already. `Place` adds one nothing uses, fixes the
order of the places, or says something about one.

```python
ARCHIVED: ClassVar[Annotated[str, Place(description="Kept, never shown")]] = "archived"
```

That holds without `places=`. With it, the enum is the whole list: a `Place` constant — or a
transition — naming a place outside it fails the build, the error saying the place
`is not a case of` the enum. Value such a constant with one of the enum's members.

| Argument | Does |
| --- | --- |
| `description=` | Kept under `metadata["description"]` |
| `metadata=` | The place's metadata — `label`, `bg_color` and the rest a dumper reads |
| `initial=` | The place is in the initial marking, unless `initial_marking=` says otherwise |

**Enum members take no marker of their own.** An annotation on an enum member survives at runtime
but type checkers reject it, so the markers for an enum's members go in `@as_workflow`:

```python
@as_workflow(places=Step, place_markers={Step.NEW: Place(initial=True)})
```

A key that is not a member of the `places` enum raises `LogicError` at decoration.

## `WorkflowTrait`

Mixing it in is optional, and makes the class answer for its own workflow: it delegates every
`WorkflowInterface` method — `get_marking`, `can`, `build_transition_blocker_list`, `apply`,
`get_enabled_transitions`, `get_enabled_transition`, `get_name`, `get_definition`,
`get_marking_store`, `get_metadata_store` — to the workflow handed to `set_workflow(...)`, which
the bundle calls after building it (the traced one, in debug mode). The class keeps whatever
constructor it likes.

Called before a workflow is set, every delegate raises `LogicError` naming the class. The workflow
is kept under a name-mangled attribute, so `_workflow` is free for your own use.

## Listeners on the class

The `as_*_listener` decorators name a workflow with their first positional argument. Inside a class
decorated `@as_workflow`, leave it out and the listener is that workflow's: the decorator records
the placeholder `workflow.@self.guard.start`, and `@as_workflow` rewrites it to
`workflow.task.guard.start` when it decorates the class.

- Keep `@as_workflow` **above** every listener decorator: it resolves what is already recorded.
- An inherited listener method is resolved per class, so two workflow classes sharing a base each
  listen to their own workflow.
- A **concrete** class carrying such declarations inside a scanned package fails the build: there
  is no workflow to resolve the name to. Make a shared listener base abstract, or keep it out of
  the scanned packages.
- A plain function cannot use the placeholder: name the workflow, or listen to every one.

See [events.md](events.md) for the decorators and the names they build.
