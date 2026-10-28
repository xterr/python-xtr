"""``workflow:dump``: a workflow's definition, written as the source of a diagram.

The upstream cases come first; completion is not ported, the console
completing nothing. The rest pin the dumper each format picks for each kind
of workflow, what the command hands the dumper, and that the dump is written
as it is.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from typing_extensions import override
from xtr_console import Application, ApplicationTester, CommandTester, ExitCode
from xtr_console.command import CommandInvokerInterface
from xtr_console.exception import MissingContainerError
from xtr_event_dispatcher import EventDispatcher

from tests.support.definitions import (
    create_complex_state_machine_definition,
    create_simple_workflow_definition,
    create_workflow_with_metadata_edge_cases,
)
from tests.support.workflow_provider import WorkflowProvider
from xtr_workflow import Definition, Marking, StateMachine, Transition, Workflow
from xtr_workflow.command import WorkflowDumpCommand
from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.dumper import (
    DumperInterface,
    GraphvizDumper,
    MermaidDumper,
    PlantUmlDumper,
    StateMachineGraphvizDumper,
)
from xtr_workflow.exception import InvalidArgumentError

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from xtr_console.command import CommandArguments, CommandDescriptor, CommandSignature
    from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface

    from xtr_workflow import WorkflowInterface

pytestmark = pytest.mark.anyio


@final
class _BuiltBeforehand(CommandInvokerInterface):
    """Runs the command built with what a container would have handed it."""

    def __init__(self, command: WorkflowDumpCommand) -> None:
        self._command = command

    @override
    async def invoke(
        self,
        command: CommandDescriptor,
        signature: CommandSignature,
        arguments: CommandArguments,
    ) -> object:
        del command, signature
        call = cast("Callable[..., Awaitable[int]]", self._command)
        return await call(*arguments.args, **arguments.kwargs)


def _tester(
    workflow: WorkflowInterface, dispatcher: ListenerIntrospectionInterface | None = None
) -> CommandTester:
    """Return a tester of the command dumping ``workflow``, which is named ``wf``."""
    application = Application(catch_exceptions=False)
    application.use_invoker(
        _BuiltBeforehand(WorkflowDumpCommand(WorkflowProvider({"wf": workflow}), dispatcher))
    )
    return CommandTester(application, "workflow:dump")


async def _dumped(workflow: WorkflowInterface, *args: str) -> str:
    """Return what the command writes dumping ``workflow`` with ``args`` after its name."""
    tester = _tester(workflow)
    _ = await tester.execute(["wf", *args])
    return tester.display


def _on_transition() -> None: ...


def _a_t1_b() -> Definition:
    return Definition(["a", "b"], [Transition("t1", "a", "b")])


async def test_with_listeners_the_listeners_are_listed_on_each_transition() -> None:
    dispatcher = EventDispatcher()
    dispatcher.add_listener("workflow.wf.transition.t1", _on_transition)
    tester = _tester(Workflow(_a_t1_b(), None, dispatcher, "wf"), dispatcher)

    _ = await tester.execute(["wf", "--with-listeners"])

    assert f"Listener #0: {__name__}._on_transition()" in tester.display


async def test_listing_the_listeners_without_a_dispatcher_is_refused() -> None:
    tester = _tester(Workflow(_a_t1_b(), name="wf"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = await tester.execute(["wf", "--with-listeners"])

    assert str(raised.value) == (
        'You cannot use the "--with-listeners" option if a dispatcher is not injected in the '
        "constructor."
    )


async def test_without_a_dispatcher_a_dump_listing_no_listener_succeeds() -> None:
    tester = _tester(Workflow(_a_t1_b(), name="wf"))

    code = await tester.execute(["wf"])

    assert code == ExitCode.SUCCESS
    assert "Listener #" not in tester.display


async def test_a_workflow_it_does_not_provide_is_refused() -> None:
    tester = _tester(Workflow(_a_t1_b(), name="wf"))

    with pytest.raises(InvalidArgumentError) as raised:
        _ = await tester.execute(["article"])

    assert str(raised.value) == 'The workflow named "article" cannot be found.'


@pytest.mark.parametrize(
    ("dump_format", "workflow_class", "dumper"),
    [
        ("dot", Workflow, GraphvizDumper()),
        ("dot", StateMachine, StateMachineGraphvizDumper()),
        ("puml", Workflow, PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION)),
        ("puml", StateMachine, PlantUmlDumper(PlantUmlDumper.STATEMACHINE_TRANSITION)),
        ("mermaid", Workflow, MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW)),
        ("mermaid", StateMachine, MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE)),
    ],
)
async def test_each_format_is_dumped_as_the_kind_of_workflow_is_drawn(
    dump_format: str, workflow_class: type[Workflow], dumper: DumperInterface
) -> None:
    definition = create_complex_state_machine_definition()

    dumped = await _dumped(workflow_class(definition, name="wf"), f"--dump-format={dump_format}")

    assert dumped == dumper.dump(definition, Marking(), {"name": "wf"}) + "\n"


@pytest.mark.parametrize("args", [(), ("--dump-format", "svg")])
async def test_dot_is_the_default_and_what_a_format_it_does_not_know_dumps(
    args: tuple[str, ...],
) -> None:
    definition = create_simple_workflow_definition()

    dumped = await _dumped(Workflow(definition, name="wf"), *args)

    assert dumped == GraphvizDumper().dump(definition) + "\n"


async def test_a_traced_workflow_is_drawn_as_the_workflow_it_traces() -> None:
    definition = create_complex_state_machine_definition()
    traced = TraceableWorkflow(StateMachine(definition, name="wf"))

    dumped = await _dumped(traced, "--dump-format=mermaid")

    expected = MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE).dump(definition)
    assert dumped == expected + "\n"


async def test_the_places_named_after_the_workflow_are_marked_a_token_each_time() -> None:
    definition = create_simple_workflow_definition()

    dumped = await _dumped(Workflow(definition, name="wf"), "a", "c", "a", "--dump-format=mermaid")

    expected = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(
        definition, Marking({"a": 2, "c": 1})
    )
    assert dumped == expected + "\n"


@pytest.mark.parametrize("args", [("-l", "Article flow"), ("--label=Article flow",)])
async def test_the_label_titles_the_graph(args: tuple[str, ...]) -> None:
    definition = create_simple_workflow_definition()

    dumped = await _dumped(Workflow(definition, name="wf"), *args)

    assert dumped == GraphvizDumper().dump(definition, options={"label": "Article flow"}) + "\n"


async def test_with_metadata_the_metadata_is_drawn() -> None:
    definition = create_workflow_with_metadata_edge_cases()

    dumped = await _dumped(Workflow(definition, name="wf"), "--with-metadata")

    assert dumped == GraphvizDumper().dump(definition, options={"with-metadata": True}) + "\n"


async def test_the_dump_is_written_as_it_is() -> None:
    long_place = "a place named at length, " * 6
    definition = Definition(
        ["[bold]draft[/bold]", ":thumbs_up:", long_place],
        [Transition("t1", "[bold]draft[/bold]", long_place)],
    )

    dumped = await _dumped(Workflow(definition, name="wf"), "--dump-format=mermaid")

    expected = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(definition)
    assert dumped == expected + "\n"


async def test_the_help_lists_the_arguments_and_the_options() -> None:
    tester = ApplicationTester(Application(catch_exceptions=False))

    code = await tester.execute(["workflow:dump", "--help"])

    assert code == ExitCode.SUCCESS
    assert {
        "NAME",
        "MARKING",
        "--label",
        "-l",
        "--with-metadata",
        "--with-listeners",
        "--dump-format",
    } <= set(tester.display.split())


async def test_without_a_container_the_console_reports_the_missing_workflows() -> None:
    tester = CommandTester(Application(catch_exceptions=False), "workflow:dump")

    with pytest.raises(MissingContainerError, match="workflows"):
        _ = await tester.execute(["wf"])
