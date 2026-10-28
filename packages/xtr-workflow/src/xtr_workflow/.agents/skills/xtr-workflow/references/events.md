# Workflow events

Every step of a move goes out as an event, through xtr-event-dispatcher. Without a dispatcher
nothing is asked and nothing told: every transition the marking enables is enabled.

## The seven events, in order

| Name | Class | When | A listener can |
| --- | --- | --- | --- |
| `workflow.guard` | `GuardEvent` | Before a transition is applied or reported enabled, for every transition the marking enables | Block it: `set_blocked(True, "why")`, or `add_transition_blocker(...)` |
| `workflow.leave` | `LeaveEvent` | Before the tokens leave each place | React |
| `workflow.transition` | `TransitionEvent` | While applying the transition | Replace the rest of the call's context: `set_context(...)` |
| `workflow.enter` | `EnterEvent` | Before the tokens enter each place, before the marking is stored | React |
| `workflow.entered` | `EnteredEvent` | After the marking is stored — and for a subject's first marking, with the context `{"initial": True}` | React |
| `workflow.completed` | `CompletedEvent` | The transition has been applied | React |
| `workflow.announce` | `AnnounceEvent` | Once per transition enabled **after** the move | React |

The guard is never turned off. `announce` asks every guard again to find what is now enabled, so it
is the one worth turning off when guards are expensive.

## Three names each

Each event is dispatched under its bare name, then narrowed to the workflow, then to each place or
transition concerned:

```
workflow.enter
workflow.blog.enter
workflow.blog.enter.published      # one per place the transition enters
```

- `leave`, `enter` and `entered` narrow to a **place** — one dispatch per arc.
- `guard`, `transition`, `completed` and `announce` narrow to a **transition**.
- `WorkflowEvents` (from `xtr_workflow`) holds the seven bare names, and `WorkflowEvents.ALIASES`
  maps each event class to its name. With the bundle active, those aliases are given to the event
  dispatcher, so a listener annotated `def on_guard(self, event: GuardEvent)` hears
  `workflow.guard` without naming it.

Each event class has a static `get_name(workflow_name=None, node=None)` building the name:
`GuardEvent.get_name("blog", "publish")` is `"workflow.blog.guard.publish"`. A node without a
workflow raises `InvalidArgumentError`.

## Reading an event

Every event answers `get_subject()`, `get_marking()`, `get_transition()` (`None` only for an
initial marking), `get_workflow_name()` and `get_metadata(key, subject)`.
`GuardEvent.get_transition()` is never `None`. `LeaveEvent`, `TransitionEvent`, `EnterEvent`,
`EnteredEvent`, `CompletedEvent` and `AnnounceEvent` also carry `get_context()`.

## The listener decorators

From `xtr_workflow.decorator`. Each builds the event name and otherwise declares an event listener
the way `@as_event_listener` does, taking the same `method`, `priority`, `dispatcher`, `before` and
`after` keywords.

| Decorator | Second positional argument |
| --- | --- |
| `as_guard_listener(workflow, transition)` | `transition=` |
| `as_leave_listener(workflow, place)` | `place=` |
| `as_transition_listener(workflow, transition)` | `transition=` |
| `as_enter_listener(workflow, place)` | `place=` |
| `as_entered_listener(workflow, place)` | `place=` |
| `as_completed_listener(workflow, transition)` | `transition=` |
| `as_announce_listener(workflow, transition)` | `transition=` |

```python
from xtr_workflow.decorator import as_entered_listener, as_guard_listener
from xtr_workflow.event import EnteredEvent, GuardEvent


@as_entered_listener("blog", place="published")  # workflow.blog.entered.published
async def ping_the_feed(event: EnteredEvent) -> None: ...


@as_guard_listener("blog")  # workflow.blog.guard — every transition of that workflow
def refuse_unsigned(event: GuardEvent) -> None:
    if not event.get_subject().author:
        event.set_blocked(True, "An article needs an author before it goes out.")
```

Naming neither a workflow nor a node listens to every workflow. Naming a node without a workflow
means "the workflow of my class" — see
[declaring-workflows.md](declaring-workflows.md); outside a class declaring one it is a build
error.

Adding a listener by hand needs no decorator:

```python
dispatcher.add_listener("workflow.blog.guard.publish", refuse_unsigned)
dispatcher.add_listener(WorkflowEvents.ENTERED, announce)
```

## Choosing what goes out

`events_to_dispatch`, on the constructor, in `WorkflowDefinitionConfig` or on `@as_workflow`, says
which events a workflow ever dispatches:

| Value | Dispatches |
| --- | --- |
| `None` | Every event |
| `[]` | None of them — the guard still goes out |
| `["workflow.enter", "workflow.entered"]` | Only those |
| `["!workflow.announce"]` | Every one but those, so an event added later still goes out |

Mixing listed and `!`-prefixed entries, or blocking `workflow.guard`, raises
`InvalidArgumentError`.

For one call, pass the context key instead — each a constant on `Workflow`:
`DISABLE_LEAVE_EVENT`, `DISABLE_TRANSITION_EVENT`, `DISABLE_ENTER_EVENT`,
`DISABLE_ENTERED_EVENT`, `DISABLE_COMPLETED_EVENT`, `DISABLE_ANNOUNCE_EVENT`.

```python
await workflow.apply(article, "publish", {Workflow.DISABLE_ANNOUNCE_EVENT: True})
```

## The audit trail

`AuditTrailListener` (`xtr_workflow.event_listener`) logs an info line per place a subject leaves,
one for the transition, and one per place it enters, each naming the subject's class and the
workflow. Built by hand it takes a `LoggerInterface`; with the bundle,
`audit_trail=AuditTrailConfig(enabled=True)` registers it on the workflow's `leave`, `transition`
and `enter` events, writing to the `workflow` logging channel — which needs the event dispatcher
and logging bundles active.
