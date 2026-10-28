"""``workflow:dump``: a workflow drawn as the source of a Graphviz, PlantUML or Mermaid diagram."""

from __future__ import annotations

from collections import Counter
from typing import Annotated, final

from xtr_console import ConsoleStyle, ExitCode, Option, as_command
from xtr_event_dispatcher_contracts import ListenerIntrospectionInterface
from xtr_service_contracts import ServiceProviderInterface

from xtr_workflow.debug import TraceableWorkflow
from xtr_workflow.debug.listener_extractor import ListenerExtractor
from xtr_workflow.dumper import (
    DumperInterface,
    GraphvizDumper,
    MermaidDumper,
    PlantUmlDumper,
    StateMachineGraphvizDumper,
)
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.marking import Marking
from xtr_workflow.state_machine import StateMachine
from xtr_workflow.workflow_interface import WorkflowInterface

__all__ = ["WorkflowDumpCommand"]


@as_command("workflow:dump")
@final
class WorkflowDumpCommand:
    """Dumps a workflow as the source of a diagram, in the format asked for.

    A container builds it with the workflows, by name, and with the
    dispatcher their listeners are registered on when there is one: without
    a dispatcher, the listeners cannot be listed. Run without a container,
    the console reports the missing ``workflows`` parameter rather than build
    it bare.
    """

    __slots__ = ("_listener_extractor", "_workflows")

    def __init__(
        self,
        workflows: ServiceProviderInterface[WorkflowInterface],
        dispatcher: ListenerIntrospectionInterface | None = None,
    ) -> None:
        """Dump the workflows of ``workflows``, listing the listeners ``dispatcher`` runs.

        Args:
            workflows: The workflows to dump, by name.
            dispatcher: Where the workflows' listeners are registered; without
                it, listing them is refused.
        """
        self._workflows = workflows
        self._listener_extractor = None if dispatcher is None else ListenerExtractor(dispatcher)

    async def __call__(  # noqa: PLR0913 -- one parameter per argument and option of the command
        self,
        io: ConsoleStyle,
        name: str,
        *marking: str,
        label: Annotated[str | None, Option(alias="-l")] = None,
        with_metadata: bool = False,
        with_listeners: bool = False,
        dump_format: str = "dot",
    ) -> int:
        r"""Dump a workflow.

        The [green]workflow:dump[/green] command dumps the graphical representation of a
        workflow in different formats

        [green]DOT[/green]:  <script> workflow:dump <workflow name> | dot -Tpng > workflow.png
        [green]PUML[/green]: <script> workflow:dump <workflow name> --dump-format=puml | java -jar plantuml.jar -p > workflow.png
        [green]MERMAID[/green]: <script> workflow:dump <workflow name> --dump-format=mermaid | mmdc -o workflow.svg

        Args:
            io: Where the command writes.
            name: A workflow name
            marking: A marking (a list of places)
            label: Label a graph
            with_metadata: Include the workflow's metadata in the dumped graph
            with_listeners: Include the workflow's listeners in the dumped graph
            dump_format: The dump format \[puml|mermaid|dot]

        Raises:
            InvalidArgumentError: If no workflow is named ``name``, or the
                listeners are asked for without a dispatcher to read them from.
        """  # noqa: E501 -- the help shows each command line whole, as it is typed
        if not self._workflows.has(name):
            raise InvalidArgumentError(f'The workflow named "{name}" cannot be found.')
        workflow = await self._workflows.get(name)
        if isinstance(workflow, TraceableWorkflow):
            workflow = workflow.get_inner()
        definition = workflow.get_definition()
        dumper = _dumper_for(dump_format, state_machine=isinstance(workflow, StateMachine))

        listeners: dict[str, dict[str, list[dict[str, object]]]] = {}
        if with_listeners:
            if self._listener_extractor is None:
                raise InvalidArgumentError(
                    'You cannot use the "--with-listeners" option if a dispatcher is not '
                    "injected in the constructor."
                )
            listeners = await self._listener_extractor.extract_listeners(name, definition)

        options: dict[str, object] = {
            "name": name,
            "with-metadata": with_metadata,
            "listeners": listeners,
            "nofooter": True,
            "label": label,
        }
        dumped = dumper.dump(definition, Marking(Counter(marking)), options)
        # A diagram's source is no markup, and a line wrapped at the terminal's width breaks it.
        io.console.print(dumped, markup=False, highlight=False, emoji=False, soft_wrap=True)
        return ExitCode.SUCCESS


def _dumper_for(dump_format: str, *, state_machine: bool) -> DumperInterface:
    """Return the dumper writing ``dump_format``, drawing a state machine's transitions as links.

    ``puml`` and ``mermaid`` name their formats; anything else is ``dot``.
    """
    match dump_format:
        case "puml":
            return PlantUmlDumper(
                PlantUmlDumper.STATEMACHINE_TRANSITION
                if state_machine
                else PlantUmlDumper.WORKFLOW_TRANSITION
            )
        case "mermaid":
            return MermaidDumper(
                MermaidDumper.TRANSITION_TYPE_STATEMACHINE
                if state_machine
                else MermaidDumper.TRANSITION_TYPE_WORKFLOW
            )
        case _:
            return StateMachineGraphvizDumper() if state_machine else GraphvizDumper()
