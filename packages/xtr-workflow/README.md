<div align="center">

# xtr-workflow

**Move objects through workflows and state machines — weighted places and transitions, guards, events at every step, definitions in code, config or on a class, dumped as Graphviz, PlantUML or Mermaid.**

<img alt="python 3.11+" src="https://img.shields.io/badge/python-%E2%89%A5%203.11-3776AB?logo=python&logoColor=white">
<img alt="asyncio" src="https://img.shields.io/badge/asyncio-native-1f6feb">
<img alt="typed" src="https://img.shields.io/badge/typed-ty%20%2B%20basedpyright-1f6feb">
<img alt="license MIT" src="https://img.shields.io/badge/license-MIT-blue">

</div>

---

## Why?

An order is new, then paid, then picked, then shipped. Written as a `status` column and a handful
of `if` statements, that knowledge ends up spread over a controller, two message handlers and a
console command — and nothing tells you, in one place, whether an order can ship.

A **definition** here says it once: the places an object can be in, and the named transitions that
move it between them. Hand that definition to a **state machine** and the object is in exactly one
place at a time; hand it to a **workflow** and it can be in several, with transitions consuming and
producing weighted tokens — a Petri net, so "ship once it is both paid and picked" is the
definition rather than a condition somewhere.

- 🔁 **Ask before you move** — `can(...)` answers, `build_transition_blocker_list(...)` says why
  not, and `apply(...)` refuses rather than half-moves.
- 📣 **Seven events per step** — `guard`, `leave`, `transition`, `enter`, `entered`, `completed`,
  `announce`, each under three names (every workflow, this one, this place or transition), through
  [xtr-event-dispatcher](../xtr-event-dispatcher).
- 🛡️ **Guards are callables** — a transition carries a function taking a `GuardContext`; with
  [xtr-security](../xtr-security) active it also carries the token, the user and the roles.
- 🏷️ **Declare it where you write it** — `@as_workflow` on a class, `Transition` and `Place`
  markers on its constants, listeners as decorated methods.
- 🖼️ **Draw it** — Graphviz, PlantUML and Mermaid, from code or from the `workflow:dump` command.
- 🧪 **Nothing hidden** — no clock, no I/O, no container needed: a definition and a workflow are
  objects you build and assert on.

Everything that may ask a listener is a coroutine: `get_marking`, `can`,
`build_transition_blocker_list`, `apply`, `get_enabled_transitions`, `get_enabled_transition`, and
both methods of a marking store. The readers that only read — `get_name`, `get_definition`,
`get_marking_store`, `get_metadata_store` — are not, and neither are definitions, markings,
validators, dumpers or the registry.

## Install

```sh
uv add xtr-workflow
uv add xtr-workflow xtr-dependency-injection   # + the container, for the WorkflowBundle
uv add xtr-security                            # beside it: guards that read the security token
uv add xtr-console                             # beside it: the workflow:dump command
uv add xtr-logging                             # beside it: the audit trail's workflow channel
```

The package depends on [xtr-event-dispatcher](../xtr-event-dispatcher) and its contracts,
[xtr-logging-contracts](../xtr-logging-contracts), [xtr-service-contracts](../xtr-service-contracts),
[xtr-clock](../xtr-clock) and `typing-extensions`. There are no extras, and the container is not a
dependency: [xtr-dependency-injection](../xtr-dependency-injection) is used when it is installed
beside the package — see [Kernel / bundle](#kernel--bundle) — and definitions, workflows, guards
and dumpers work without it, as the [Quick start](#quick-start) shows. Only
`xtr_workflow.bundle` imports the container, only `xtr_workflow.command` imports xtr-console, and
only `xtr_workflow.event_listener.guard_listener` imports xtr-security-core.

Requires Python 3.11+.

## Quick start

```python
from xtr_workflow import DefinitionBuilder, StateMachine, Transition
from xtr_workflow.marking_store import MethodMarkingStore


class Article:
    status: str | None = None


definition = (
    DefinitionBuilder()
    .add_places(["draft", "review", "published"])
    .add_transitions(
        [
            Transition("request_review", "draft", "review"),
            Transition("publish", "review", "published"),
            Transition("reject", "review", "draft"),
        ]
    )
    .build()
)

workflow = StateMachine(definition, MethodMarkingStore(True, "status"), name="blog_publishing")

article = Article()

assert await workflow.can(article, "request_review")
assert not await workflow.can(article, "publish")

await workflow.apply(article, "request_review")
assert article.status == "review"

marking = await workflow.apply(article, "publish")
assert marking.get_places() == {"published": 1}
```

The first place added is where a subject starts, unless `set_initial_places(...)` says otherwise.
`MethodMarkingStore(True, "status")` keeps one place in `article.status`; without a store a state
machine uses `MethodMarkingStore(single_state=True)` on `marking`, and a workflow
`MethodMarkingStore()`, which keeps a dict of places there. The store reads
`get_<property>()` / `set_<property>(places, context)` when the subject has them — awaiting either
if it is a coroutine — and the attribute otherwise; an attribute annotated with an enum is written
as a member of it.

### Several places at once

`Workflow` is the Petri net: a transition takes tokens from every place it leaves and puts tokens
in every place it enters, `Arc(place, weight)` saying how many.

```python
from xtr_workflow import Arc, Definition, Transition, TransitionBlocker, Workflow
from xtr_workflow.exception import NotEnabledTransitionError


class Order:
    marking: dict[str, int] | None = None


definition = Definition(
    ["new", "paid", "picked", "shipped"],
    [
        Transition("split", "new", [Arc("paid"), Arc("picked", 2)]),
        # Ships only once both a payment and a picking token are in.
        Transition("ship", [Arc("paid"), Arc("picked")], "shipped"),
    ],
    "new",
)

workflow = Workflow(definition, name="order_fulfilment")

order = Order()
marking = await workflow.apply(order, "split")
assert marking.get_places() == {"paid": 1, "picked": 2}

await workflow.apply(order, "ship")
assert order.marking == {"picked": 1, "shipped": 1}

try:
    await workflow.apply(order, "ship")
except NotEnabledTransitionError as error:
    blockers = list(error.get_transition_blocker_list())
    assert [b.get_code() for b in blockers] == [TransitionBlocker.BLOCKED_BY_MARKING]
```

Several transitions may share a name — a state machine needs one per pair of places, and a
workflow applies **every** transition of that name the marking enables, so a subject spread over
places moves out of all of them at once. A transition is known by its identity, not by its name:
two built alike are two transitions, each with metadata of its own.

## Declaring a workflow on a class

`@as_workflow` records on the class what the configuration would otherwise say; `Transition` and
`Place` from `xtr_workflow.decorator` are `Annotated` markers on its constants. The
[workflow bundle](#kernel--bundle) builds the workflow from the declaration — and, for a class
mixing in `WorkflowTrait`, hands it the workflow so the class answers for it.

```python
from enum import StrEnum
from typing import Annotated, ClassVar

from xtr_workflow import WorkflowTrait
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

    @as_guard_listener(transition=START)
    def refuse_blocked_tasks(self, event: GuardEvent) -> None:
        subject = event.get_subject()
        if isinstance(subject, Task) and subject.blocked:
            event.set_blocked(True, "The task is blocked.")
```

- The workflow's name is the class's, snake-cased, without a `Workflow` or `StateMachine` suffix:
  `TaskStateMachine` declares `task`. `name=` overrides it.
- `type=WorkflowType.WORKFLOW` makes it a Petri net; the default is a state machine.
- A marker's `froms` / `tos` take a place name, a member of a string enum, an `Arc`, or a sequence
  of those. Repeat `Transition(...)` inside one `Annotated` for several transitions of that name.
- `places=` names a string enum whose every member is a place. Enum members carry no annotation of
  their own, so their `Place` markers go in `place_markers={Step.NEW: Place(...)}`; a `Place` on a
  class constant valued with a place's name works the same way, and is how a place no transition
  uses gets added.
- `description=` on the workflow, a place or a transition is kept under the `description` key of
  its metadata — a dump shows it, and giving both raises.
- The declaration belongs to the decorated class alone: a subclass declares no workflow unless it
  is decorated too, and decorating one class twice raises.
- `@as_workflow` resolves the class's listeners, so keep it **above** every listener decorator.
- Mixing in `WorkflowTrait` is optional. It delegates every `WorkflowInterface` method to the
  workflow handed to `set_workflow(...)`; called before that, it raises `LogicError`.

See [references/declaring-workflows.md](src/xtr_workflow/.agents/skills/xtr-workflow/references/declaring-workflows.md)
for the full marker reference.

## Events

Each step goes out under three names: for every workflow, for this one, and for the place or
transition concerned — `workflow.enter`, `workflow.blog.enter`, `workflow.blog.enter.published`.

| Event | Class | When |
| --- | --- | --- |
| `workflow.guard` | `GuardEvent` | Before a transition is applied or reported enabled; a listener blocks it |
| `workflow.leave` | `LeaveEvent` | Before the tokens leave each place |
| `workflow.transition` | `TransitionEvent` | While applying it; a listener may replace the call's context |
| `workflow.enter` | `EnterEvent` | Before the tokens enter each place |
| `workflow.entered` | `EnteredEvent` | After the marking is stored, and for a subject's first marking |
| `workflow.completed` | `CompletedEvent` | The transition has been applied |
| `workflow.announce` | `AnnounceEvent` | Once per transition enabled after the move |

```python
from xtr_event_dispatcher import EventDispatcher

from xtr_workflow import StateMachine, WorkflowEvents
from xtr_workflow.event import EnteredEvent, GuardEvent

dispatcher = EventDispatcher()


def refuse_unsigned(event: GuardEvent) -> None:
    if event.get_subject().author == "nobody":
        event.set_blocked(True, "An article needs an author before it goes out.")


def announce(event: EnteredEvent) -> None:
    log.info("now in %s", event.get_marking().get_places())


dispatcher.add_listener("workflow.blog.guard.publish", refuse_unsigned)
dispatcher.add_listener(WorkflowEvents.ENTERED, announce)

workflow = StateMachine(definition, dispatcher=dispatcher, name="blog")
blockers = await workflow.build_transition_blocker_list(article, "publish")
assert [b.get_message() for b in blockers] == ["An article needs an author before it goes out."]
```

Without a dispatcher nothing is asked and nothing told: every transition the marking enables is
enabled.

### Listener decorators

`as_guard_listener`, `as_leave_listener`, `as_transition_listener`, `as_enter_listener`,
`as_entered_listener`, `as_completed_listener` and `as_announce_listener` build the name for you
and otherwise declare an event listener the way `@as_event_listener` does — same `method`,
`priority`, `dispatcher`, `before` and `after`. The first positional argument is the workflow; the
second is a `transition=` (guard, transition, completed, announce) or a `place=` (leave, enter,
entered).

```python
from xtr_workflow.decorator import as_entered_listener


@as_entered_listener("blog", place="published")  # workflow.blog.entered.published
async def ping_the_feed(event: EnteredEvent) -> None: ...
```

Inside a class decorated with `@as_workflow`, leave the workflow out and it is that class's:
`@as_guard_listener(transition=START)` listens to `workflow.task.guard.start`. Outside such a
class, a listener naming only a place or a transition is a build error — there is no workflow to
narrow it to.

### Choosing what goes out

`events_to_dispatch` on the constructor — and `events_to_dispatch` in the configuration or on
`@as_workflow` — says which events a workflow ever dispatches: every one when `None`, none when
empty, only those listed, or, with every entry prefixed `!`, every one but those. The guard always
goes out, so `!workflow.guard` and a mix of listed and prefixed entries both raise
`InvalidArgumentError`.

```python
workflow = StateMachine(
    definition, dispatcher=dispatcher, events_to_dispatch=["!workflow.announce"]
)
```

For one call, pass the context key instead: `DISABLE_LEAVE_EVENT`, `DISABLE_TRANSITION_EVENT`,
`DISABLE_ENTER_EVENT`, `DISABLE_ENTERED_EVENT`, `DISABLE_COMPLETED_EVENT`,
`DISABLE_ANNOUNCE_EVENT`, each a constant on `Workflow`.

```python
await workflow.apply(article, "publish", {Workflow.DISABLE_ANNOUNCE_EVENT: True})
```

`announce` is worth a thought: it asks every transition's guard again, after the move, to find
which are now enabled. Turn it off for a workflow whose guards are expensive and whose listeners
do not need it.

## Guards

A guard is a callable on a transition, handed a `GuardContext` and answering whether the transition
may run — at once, or through an awaitable. It is set in the configuration
(`TransitionConfig(..., guard=...)`) or on a marker (`Transition(..., guard=...)`).

```python
from xtr_workflow.event_listener import GuardContext


async def only_an_editor(context: GuardContext) -> bool:
    return await context.authorization_checker.is_granted("ROLE_EDITOR", context.subject)


def by_anyone(context: GuardContext) -> bool:
    return context.token is None or "ROLE_USER" in context.role_names
```

The context carries `subject`, `token` (`None` when no one is authenticated), `user`, `role_names`
(the token's roles and everything they reach through the role hierarchy), `authorization_checker`
and `trust_resolver`. Every guard of a transition runs, and each refusal adds a
`BLOCKED_BY_EXPRESSION_GUARD_LISTENER` blocker naming the guard, so one call learns every reason.

Guards read the security services, so the [security bundle](../xtr-security) must be active: a
workflow with a guard and no security bundle fails the build. Importing `GuardContext` needs
nothing — its security types are read by the type checker only — so a module of guards imports
wherever the package does.

## Dumping a definition

```python
from xtr_workflow.dumper import (
    GraphvizDumper,
    MermaidDumper,
    PlantUmlDumper,
    StateMachineGraphvizDumper,
)

print(MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE).dump(definition, marking))
print(StateMachineGraphvizDumper().dump(definition))
print(PlantUmlDumper(PlantUmlDumper.STATEMACHINE_TRANSITION).dump(definition))
print(GraphvizDumper().dump(definition, options={"label": "blog"}))
```

Each dumper takes the definition, an optional marking to highlight, and options it reads and
otherwise ignores. `GraphvizDumper` draws a workflow (places as circles, transitions as boxes) and
`StateMachineGraphvizDumper` a state machine; `PlantUmlDumper` and `MermaidDumper` take the
transition style — `STATEMACHINE_TRANSITION` / `TRANSITION_TYPE_STATEMACHINE` for labelled arrows,
`WORKFLOW_TRANSITION` / `TRANSITION_TYPE_WORKFLOW` for transition nodes. Metadata styles the
drawing: `label`, `bg_color`, `description`, `color` and `arrow_color`, read where each dumper
documents them.

With the [console bundle](../xtr-console) active, `workflow:dump` does it from the command line:

```sh
uv run python -m app.console workflow:dump blog_publishing --dump-format=mermaid
uv run python -m app.console workflow:dump blog_publishing review --with-metadata --with-listeners
uv run python -m app.console workflow:dump order_fulfilment -l "Order fulfilment" | dot -Tpng > wf.png
```

The places after the name are the marking to highlight. `-l` / `--label` titles the diagram,
`--with-metadata` lists what the definition carries, `--with-listeners` lists who listens to each
transition, and `--dump-format` picks `dot` (the default), `puml` or `mermaid`. The command writes
the source unchanged, so piping it to `dot`, PlantUML or a file is the point.

## Use in an application

Everything adding this package to an application on
[xtr-dependency-injection](../xtr-dependency-injection) takes — and, read backwards, what removing
it undoes.

- **Install** — `uv add xtr-workflow xtr-dependency-injection`: the bundle needs the container
  installed beside it, never as an extra. Install [xtr-security](../xtr-security) beside it for
  guards, [xtr-console](../xtr-console) for `workflow:dump`, and [xtr-logging](../xtr-logging) for
  the audit trail's `workflow` channel.
- **Recipe** — `uv run xtr-recipes recipes:sync` does the *Activate* and *Configure* steps below:
  it lists `WorkflowBundle` and writes `<app>/config/packages/workflow.py` holding the bundle's own
  defaults — no workflow — with a commented starter one. There is no environment variable and no
  ignore line to write; it prints the steps it cannot make, which are writing the workflows
  themselves, and activating the security, console and logging bundles if guards, `workflow:dump`
  or an audit trail are wanted.
- **Activate** — `WorkflowBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`,
  imported from `xtr_workflow.bundle`.
- **Brings along** — nothing of its own. It reads the event dispatcher, logging, security and
  console bundles when they are active: the dispatcher to send events and to let a listener declare
  a workflow event by its class, logging for the `workflow` channel it adds, security for guards,
  console for `workflow:dump`. None is required, and a workflow needing one that is missing fails
  the build naming it.
- **Configure** — `<app>/config/packages/workflow.py`, where the workflows are configured as a
  `WorkflowConfig`; see [Kernel / bundle](#kernel--bundle). A workflow declared with
  `@as_workflow` needs no entry there, and a `WorkflowConfig()` with no workflow is valid.
- **Environment** — nothing.
- **Ignore** — nothing.
- **Remove** — drop the `BUNDLES` entry, and delete every `@as_workflow` class and every workflow
  listener; `uv run xtr-recipes recipes:remove xtr-workflow` deletes
  `<app>/config/packages/workflow.py`, unless you edited it, in which case it is moved aside to
  `workflow.py.removed`. Then `uv remove xtr-workflow`.
- **Check** — `debug:bundles` lists `workflow` as active; `workflow:dump <name>` prints the
  definition the container built.

## Kernel / bundle

With [xtr-dependency-injection](../xtr-dependency-injection) installed beside the package — it is
not a dependency, and nothing outside `xtr_workflow.bundle` imports it — list the bundle:

```python
# app/config/bundles.py
from xtr_workflow.bundle import WorkflowBundle

BUNDLES = {WorkflowBundle: {"all": True}}
```

Then configure the workflows, or declare them with `@as_workflow` and configure nothing:

```python
# app/config/packages/workflow.py
from xtr_dependency_injection import configure

from xtr_workflow import WorkflowType
from xtr_workflow.bundle import (
    ArcConfig,
    AuditTrailConfig,
    MarkingStoreConfig,
    PlaceConfig,
    TransitionConfig,
    WorkflowConfig,
    WorkflowDefinitionConfig,
)

from app.blog import Article, Status, only_an_editor


@configure
def workflow() -> WorkflowConfig:
    return WorkflowConfig(
        workflows={
            "blog_publishing": WorkflowDefinitionConfig(
                type=WorkflowType.STATE_MACHINE,
                supports=Article,
                marking_store=MarkingStoreConfig(property="status"),
                audit_trail=AuditTrailConfig(enabled=True),
                initial_marking=Status.DRAFT,
                places=(
                    PlaceConfig("draft", metadata={"description": "Being written"}),
                    "review",
                    Status.PUBLISHED,
                ),
                transitions={
                    "request_review": TransitionConfig(froms=Status.DRAFT, tos=Status.REVIEW),
                    "publish": TransitionConfig(
                        froms=Status.REVIEW, tos=Status.PUBLISHED, guard=only_an_editor
                    ),
                    "reject": TransitionConfig(froms=Status.REVIEW, tos=Status.DRAFT),
                },
                metadata={"title": "Blog publishing"},
            ),
            "order_fulfilment": WorkflowDefinitionConfig(
                type=WorkflowType.WORKFLOW,
                places=("new", "paid", "picked", "shipped"),
                transitions=(
                    TransitionConfig("split", froms="new", tos=("paid", ArcConfig("picked", 2))),
                    TransitionConfig("ship", froms=("paid", "picked"), tos="shipped"),
                ),
            ),
        },
    )
```

Lists may be written the shortest way that says them: one supported class or initial place on its
own, places as names or enum members or `PlaceConfig`s — or keyed by name — transitions keyed by
name, arcs as a name, an enum member, an `Arc` or an `ArcConfig`. A `MarkingStoreConfig` with a
`type` or a `property` keeps the marking on the subject; with a `service` it names a
`MarkingStoreInterface` service; with nothing it is the type's default store. The definition is
built and run through its validators — `StateMachineValidator` or `WorkflowValidator`, plus any
`definition_validators` — at build time, so a definition no workflow could run fails the build.

### Injecting a workflow

Each workflow is registered **once**, as `WorkflowInterface` under its name:

```python
from typing import Annotated

from xtr_dependency_injection import ServiceLocator, Target
from xtr_workflow import Registry, WorkflowInterface


class Publisher:
    def __init__(
        self,
        blog: Annotated[WorkflowInterface, Target("blog_publishing")],
        workflows: ServiceLocator[WorkflowInterface],  # by name, when it is decided at runtime
        registry: Registry,  # by subject: registry.get(article)
    ) -> None: ...
```

Its `Definition` and its `InMemoryMetadataStore` are registered under the name too. A workflow
listing `supports` classes, or naming a `support_strategy` service, is in the `Registry`, where
`get(subject)` or `get(subject, "blog_publishing")` finds it; one that says neither is reached by
injection only. Every workflow carries the `workflow` tag (`WORKFLOW_TAG`) with its name, type,
supported classes, source class, metadata and validators, plus a `workflow.workflow` or
`workflow.state_machine` tag.

A class declaring a workflow and mixing in `WorkflowTrait` is registered as a service of its own
and handed its workflow, so injecting `TaskStateMachine` gives something that both carries your
methods and answers `apply(...)`.

In debug mode every service tagged `workflow` is wrapped in a `TraceableWorkflow`, which records
each call — method, duration, arguments,
the marking before an `apply`, and what came back or was raised. That is why the injection key is
the interface and not `Workflow` or `StateMachine`: code needing the concrete class calls
`get_inner()` first, as `workflow:dump` does.

With `audit_trail=AuditTrailConfig(enabled=True)`, each workflow logs every place a subject leaves
and enters and every transition it takes, on the `workflow` logging channel the bundle adds —
which needs the event dispatcher and logging bundles active.

## Testing

A definition and a workflow are objects; nothing needs a kernel, a clock or a dispatcher.

```python
from xtr_workflow import DefinitionBuilder, StateMachine, Transition


async def test_a_draft_cannot_be_published() -> None:
    definition = (
        DefinitionBuilder()
        .add_places(["draft", "review", "published"])
        .add_transitions([Transition("publish", "review", "published")])
        .build()
    )
    workflow = StateMachine(definition, name="blog")

    assert not await workflow.can(Article(), "publish")
```

To check a guard, call it with a `GuardContext` you build yourself — the fields are plain data and
two protocols. To check what a workflow dispatched, hand it a dispatcher that records; to check a
dump, compare the string.

## Known limitations

- **Guards need a request, or they see no one.** A guard runs inside a unit of work opened for its
  guard event, which reads the security token of the request or message being handled. A workflow
  moved from a console command, or anywhere outside such a unit, opens one with nobody
  authenticated: `context.token` is `None`, `role_names` is empty, and a guard asking for a role
  refuses. Guard with the subject's own data where a transition must also run headless.
- **The security bundle needs an HTTP-capable kernel.** Guards require it to be active, which in
  turn requires its own peers; a worker or command-only application cannot take guards along for
  the ride.
- **A `@self` listener base class must stay abstract.** A concrete class carrying workflow listener
  declarations, inside a package the container scans, fails the build: its `workflow.@self.…`
  names have no workflow to resolve to. Make a shared listener base abstract, or keep it out of the
  scanned packages.
- **`TransitionConfig.weight` is read by nothing.** It is checked to be at least 1 and kept so a
  configuration setting it still reads; only the weights of the arcs count. Weigh an arc with
  `ArcConfig(place, weight)` or `Arc(place, weight)`.
- **No expression language.** Guards are callables, not strings, so there is no `is_granted(...)`
  or `is_valid(...)` expression to write in configuration, and no expression cache.
- **No `is_valid()` guard.** There is no validator component to call.
- **No shell completion** for `workflow:dump`, and no place list given as a class-and-glob string.
- **No profiler collector yet.** `TraceableWorkflow` records the calls and the listener listing is
  built, but nothing presents them in a profiler; `workflow:dump --with-listeners` is what reads
  them today.
- **`announce` re-runs every guard** after each `apply`, to find what is enabled next. With async
  guards that is visible latency; `DISABLE_ANNOUNCE_EVENT`, or `events_to_dispatch`, turns it off.

## Errors

Everything the library raises derives from `WorkflowError` (`xtr_workflow.exception`):

- `InvalidArgumentError` (also a `ValueError`) — a value it cannot use: a weight below 1, an empty
  place, unmarking a place that holds nothing, an unknown event in `events_to_dispatch`, a subject
  no registry entry supports or several do, a direction or transition type a dumper does not know.
- `LogicError` — a state that cannot be: a marking with no initial place to fall back on, a place
  the definition lacks, a subject with neither accessor nor attribute for its marking, a class
  decorated `@as_workflow` twice, a workflow name already taken, a bundle a workflow needs that is
  not active, a `WorkflowTrait` used before `set_workflow(...)`.
- `InvalidDefinitionError` — a validator refused the definition.
- `TransitionError` — a transition that did not happen, carrying the subject, the transition's
  name, the workflow and the context: `UndefinedTransitionError` (no transition of that name) and
  `NotEnabledTransitionError` (blocked, with the `TransitionBlockerList` explaining it).
- `WorkflowRuntimeError` — a failure while running.

`Transition` raises a plain `TypeError` for an arc that is neither a place name nor an `Arc`.

## Development

Developed in the [python-xtr](https://github.com/xterr/python-xtr) monorepo, under
`packages/xtr-workflow`; run the commands below from there. The `python-xtr-workflow` repository is
a read-only copy, so send issues and pull requests to the monorepo.

```sh
uv sync
uv run ruff check && uv run ruff format --check && uv run basedpyright && uv run ty check && uv run pytest
```

## License

MIT — see [LICENSE](LICENSE).
