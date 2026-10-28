---
name: xtr-workflow
description: How to move an object through a workflow or a state machine with xtr-workflow — definitions built in code, in configuration or declared on a class, guards that block a transition, events at every step, and definitions dumped as Graphviz, PlantUML or Mermaid. Use when an object has a status, a state, a stage or a lifecycle (draft/review/published, new/paid/shipped, open/assigned/closed), when a move must be checked before it happens or refused with a reason, when something must react to a status change, when an object must be in several places at once or a step must wait for two others, when adding WorkflowBundle to an application on xtr-dependency-injection, or when drawing a state diagram with workflow:dump.
---

# xtr-workflow

A **definition** is the places an object can be in and the named transitions that move it between
them. A **state machine** keeps the object in exactly one place; a **workflow** is a Petri net — it
can be in several, and a transition consumes and produces weighted tokens. Events go out at every
step through xtr-event-dispatcher; see the `xtr-event-dispatcher` skill for listeners in general.

## Quick reference

- Build a definition: `DefinitionBuilder().add_places([...]).add_transitions([...]).build()`, or
  `Definition(places, transitions, initial_places, metadata_store)`.
- Run it: `StateMachine(definition, marking_store, dispatcher, name)` or `Workflow(...)`, both from
  `xtr_workflow`.
- Ask, then move: `await workflow.can(subject, "publish")`,
  `await workflow.build_transition_blocker_list(subject, "publish")`,
  `await workflow.apply(subject, "publish", context)`,
  `await workflow.get_enabled_transitions(subject)`.
- Where the marking lives: `MethodMarkingStore(single_state, property)` from
  `xtr_workflow.marking_store` — the subject's `get_<property>()` / `set_<property>()`, else its
  attribute. Both its methods are `async`.
- Declare on a class: `@as_workflow(...)` with `Transition` / `Place` markers and
  `as_*_listener` methods, from `xtr_workflow.decorator`. See
  [references/declaring-workflows.md](references/declaring-workflows.md).
- Events, names and listener decorators: [references/events.md](references/events.md).
- Guard a transition: a callable taking a `GuardContext` (`xtr_workflow.event_listener`), set as
  `guard=` on a `TransitionConfig` or a `Transition` marker. Needs the security bundle active.
- Draw it: `GraphvizDumper`, `StateMachineGraphvizDumper`, `PlantUmlDumper`, `MermaidDumper` from
  `xtr_workflow.dumper`, or the `workflow:dump` command.
- In an application, with xtr-dependency-injection installed beside the package (it is not a
  dependency): activate `WorkflowBundle` and configure `WorkflowConfig`. Without the container,
  everything above works; only `xtr_workflow.bundle` imports it.
- Everything that may ask a listener is a coroutine; `get_name`, `get_definition`,
  `get_marking_store`, `get_metadata_store`, definitions, markings, dumpers, validators and the
  registry are not.

## Move an object through a state machine

The usual case: one place at a time, kept on the subject.

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
await workflow.apply(article, "request_review")
assert article.status == "review"
```

The first place added is where a subject starts; `set_initial_places(...)` changes that. A subject
read for the first time is put in the initial places and an `entered` event announces it, with the
context `{"initial": True}`.

## Wait for two things at once

`Workflow` is the Petri net. `Arc(place, weight)` says how many tokens a transition takes from a
place or puts in it; a bare place name weighs 1.

```python
from xtr_workflow import Arc, Definition, Transition, Workflow

definition = Definition(
    ["new", "paid", "picked", "shipped"],
    [
        Transition("split", "new", [Arc("paid"), Arc("picked", 2)]),
        Transition("ship", [Arc("paid"), Arc("picked")], "shipped"),  # needs both
    ],
    "new",
)
workflow = Workflow(definition, name="order_fulfilment")

marking = await workflow.apply(order, "split")
assert marking.get_places() == {"paid": 1, "picked": 2}
```

Applying a name applies **every** transition of that name the marking enables, so a subject spread
over places moves out of all of them at once. A transition is known by its identity: two built
alike are two transitions, each with its own metadata.

## Refuse a move, and say why

```python
from xtr_workflow.exception import NotEnabledTransitionError, UndefinedTransitionError

blockers = await workflow.build_transition_blocker_list(order, "ship")
if not blockers.is_empty():
    reasons = [blocker.get_message() for blocker in blockers]

try:
    await workflow.apply(order, "ship")
except NotEnabledTransitionError as error:
    reasons = [b.get_message() for b in error.get_transition_blocker_list()]
except UndefinedTransitionError:
    ...  # no transition of that name at all
```

Codes on `TransitionBlocker`: `BLOCKED_BY_MARKING` (the places do not hold the tokens),
`BLOCKED_BY_EXPRESSION_GUARD_LISTENER` (a guard refused, the message naming it), `UNKNOWN` (a
listener called `set_blocked(True)` without a code of its own).

## Guard a transition

A guard is a callable handed a `GuardContext`, answering whether the transition may run — at once
or through an awaitable. Every guard of the transition runs, and each refusal adds a blocker.

```python
from xtr_workflow.event_listener import GuardContext


async def only_an_editor(context: GuardContext) -> bool:
    return await context.authorization_checker.is_granted("ROLE_EDITOR", context.subject)


def not_locked(context: GuardContext) -> bool:
    return not context.subject.locked
```

The context carries `subject`, `token` (`None` when no one is authenticated), `user`, `role_names`
(the token's roles plus everything they reach), `authorization_checker` and `trust_resolver`.
Importing it needs no security package. Running one does: set it with
`TransitionConfig(..., guard=only_an_editor)` or `Transition(..., guard=only_an_editor)`, and
activate the security bundle, or the build fails naming it.

## Draw the definition

```python
from xtr_workflow.dumper import MermaidDumper, StateMachineGraphvizDumper

print(MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE).dump(definition, marking))
print(StateMachineGraphvizDumper().dump(definition, options={"label": "Blog"}))
```

`GraphvizDumper` draws a workflow, `StateMachineGraphvizDumper` a state machine; `PlantUmlDumper`
and `MermaidDumper` take the transition style (`STATEMACHINE_TRANSITION` /
`TRANSITION_TYPE_STATEMACHINE` for labelled arrows, `WORKFLOW_TRANSITION` /
`TRANSITION_TYPE_WORKFLOW` for transition nodes). Metadata styles it: `label`, `bg_color`,
`description`, `color`, `arrow_color`.

With the console bundle active:

```sh
<script> workflow:dump blog_publishing --dump-format=mermaid
<script> workflow:dump blog_publishing review --with-metadata --with-listeners
<script> workflow:dump order_fulfilment -l "Order fulfilment" | dot -Tpng > wf.png
```

The places after the name are the marking to highlight; `--dump-format` is `dot` (default), `puml`
or `mermaid`. The output is raw diagram source, meant to be piped.

## Testing

Nothing needs a kernel, a clock or a dispatcher: build the definition, build the workflow, assert.

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

- To test what went out, hand the workflow a dispatcher that records what it is given.
- To test a guard, call it with a `GuardContext` built by hand: the fields are plain data and two
  protocols, so a fake checker is a class with `is_granted`.
- To test a dump, compare the string; the dumpers are deterministic and read no clock.
- A bundle test calls `await assert_zero_config(WorkflowBundle)`: with no workflow it builds, boots,
  and its `Registry` raises `Unable to find a workflow for class "object".`

## Use in an application

`uv run xtr-recipes recipes:sync` applies the recipe shipped with this package: it lists
`WorkflowBundle` and writes `<app>/config/packages/workflow.py` with the bundle's own defaults — no
workflow — and a commented starter one. That is the steps below a recipe can do; the workflows
themselves it prints for you to make.

1. **Install** — `uv add xtr-workflow xtr-dependency-injection`: the bundle needs the container
   installed beside it, never as an extra. Install xtr-security beside it for guards, xtr-console
   for `workflow:dump`, xtr-logging for the audit trail's `workflow` channel.
2. **Activate** — `WorkflowBundle: {"all": True}` in `BUNDLES` in `<app>/config/bundles.py`
   (`from xtr_workflow.bundle import WorkflowBundle`).
3. **Brings along** — nothing of its own. The event dispatcher, logging, security and console
   bundles are read where they are active; a workflow needing one that is missing fails the build
   naming it.
4. **Configure** — `<app>/config/packages/workflow.py`. A workflow declared with `@as_workflow`
   needs no entry; `WorkflowConfig()` with no workflow is valid.

   ```python
   # <app>/config/packages/workflow.py
   from xtr_dependency_injection import configure
   from xtr_workflow import WorkflowType
   from xtr_workflow.bundle import (
       AuditTrailConfig,
       MarkingStoreConfig,
       TransitionConfig,
       WorkflowConfig,
       WorkflowDefinitionConfig,
   )

   from app.blog import Article, only_an_editor


   @configure
   def workflow() -> WorkflowConfig:
       return WorkflowConfig(
           workflows={
               "blog_publishing": WorkflowDefinitionConfig(
                   type=WorkflowType.STATE_MACHINE,
                   supports=Article,
                   marking_store=MarkingStoreConfig(property="status"),
                   audit_trail=AuditTrailConfig(enabled=True),
                   places=("draft", "review", "published"),
                   transitions={
                       "request_review": TransitionConfig(froms="draft", tos="review"),
                       "publish": TransitionConfig(
                           froms="review", tos="published", guard=only_an_editor
                       ),
                       "reject": TransitionConfig(froms="review", tos="draft"),
                   },
               ),
           },
       )
   ```

   Lists take the shortest shape that says them: one supported class or initial place on its own,
   places as names, string-enum members or `PlaceConfig`s — or keyed by name — transitions keyed by
   name, arcs as a name, an enum member, an `Arc` or an `ArcConfig`.
5. **Inject** — each workflow is registered once, as `WorkflowInterface` under its name:
   `Annotated[WorkflowInterface, Target("blog_publishing")]`, or
   `ServiceLocator[WorkflowInterface]` by name, or `Registry` by subject (`registry.get(article)`,
   for a workflow listing `supports` or a `support_strategy`). Its `Definition` and metadata store
   are under the name too. In debug mode the service is a `TraceableWorkflow`, so code needing the
   concrete class calls `get_inner()`.
6. **Environment** — nothing. **Ignore** — nothing.
7. **Check** — `debug:bundles` lists `workflow` as active; `workflow:dump <name>` prints the
   definition the container built.
8. **Remove** — drop the `BUNDLES` entry, delete every `@as_workflow` class and workflow listener;
   `uv run xtr-recipes recipes:remove xtr-workflow` deletes
   `<app>/config/packages/workflow.py`, unless you edited it, in which case it is moved aside to
   `workflow.py.removed`. Then `uv remove xtr-workflow`.

## Errors

All derive from `WorkflowError` (`xtr_workflow.exception`):

- `InvalidArgumentError` (also a `ValueError`) — a value it cannot use: a weight below 1, an empty
  place name, unmarking a place that holds nothing, an unknown entry in `events_to_dispatch`, no
  workflow for a subject or several, a direction or transition type a dumper does not know.
- `LogicError` — a state that cannot be: an empty marking with no initial place, a place the
  definition lacks, a subject with neither accessor nor attribute for its marking, a class
  decorated `@as_workflow` twice, a workflow name taken twice, a bundle a workflow needs that is
  not active, a `WorkflowTrait` used before `set_workflow(...)`.
- `InvalidDefinitionError` — a validator refused the definition at build.
- `TransitionError` — carrying the subject, the transition's name, the workflow and the context:
  `UndefinedTransitionError` (no transition of that name) and `NotEnabledTransitionError` (blocked,
  with the blocker list).
- `WorkflowRuntimeError` — a failure while running.

`Transition` raises a plain `TypeError` for an arc that is neither a place name nor an `Arc`.

## Do not

- Do not call `apply`, `can`, `get_marking` or the blocker list without `await`: every one is a
  coroutine, and so are both methods of a marking store.
- Do not import `Transition` from `xtr_workflow` where you mean the marker: the marker is
  `xtr_workflow.decorator.Transition`, and the two are different classes.
- Do not write `from=` / `to=`: the keywords are `froms=` and `tos=`.
- Do not expect a guard to see a token outside a request or a message: the unit of work opened for
  a guard event in a console command has nobody authenticated, so a role check refuses. Guard on
  the subject's own data where a transition must run headless.
- Do not leave a concrete class carrying `@self` workflow listeners inside a scanned package — the
  build fails with nothing to resolve the name to. Make a shared listener base abstract, or keep it
  out of the scan.
- Do not rely on `TransitionConfig(weight=...)`: it is validated and read by nothing. Weigh the arc
  instead, with `ArcConfig(place, weight)`.
- Do not write a guard as a string expression; there is no expression language here, and no
  `is_valid(...)`.
- Do not subclass a `@as_workflow` class expecting a second workflow: the declaration is the
  decorated class's alone.
- Do not inject `Workflow` or `StateMachine` from the container; the key is `WorkflowInterface`
  under the workflow's name.
