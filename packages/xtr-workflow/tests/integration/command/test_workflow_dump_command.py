"""``workflow:dump`` on the console of a booted kernel, every workflow traced in debug mode.

The command reaches the workflows the bundle registered and draws each as its
kind is drawn, through the trace; with ``--with-listeners`` it names each
listener after the code it runs — through the container's lazy listeners, the
traced dispatcher, and the guard listener built for each unit of work.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

import pytest
from xtr_console import Application, CommandTester, ExitCode
from xtr_dependency_injection import Kernel
from xtr_dependency_injection.testing import boot_for_test

from xtr_workflow import Definition, Marking
from xtr_workflow.dumper import (
    DumperInterface,
    GraphvizDumper,
    MermaidDumper,
    PlantUmlDumper,
    StateMachineGraphvizDumper,
)

pytestmark = pytest.mark.anyio

_APPLICATION = "tests.fixtures.app_workflow_dump"
_GUARDS = "tests.fixtures.app_workflow_dump.guards"
_LISTENERS = "tests.fixtures.app_workflow_dump.listeners"


@dataclass(frozen=True, slots=True)
class _Run:
    """What a run of the command ended with, and the definition of the workflow it named."""

    code: int
    display: str
    error_display: str
    definition: Definition


async def _run(application: str, workflow: str, *options: str) -> _Run:
    """Run ``workflow:dump`` for ``workflow`` on the console of ``application``, in debug mode."""
    kernel = Kernel(application, env="test", debug=True)
    async with await boot_for_test(kernel) as booted:
        tester = CommandTester(await booted.container.get(Application), "workflow:dump")
        code = await tester.execute([workflow, *options])
        definition = await booted.container.get(Definition, workflow)
    return _Run(code, tester.display, tester.error_display, definition)


@pytest.mark.parametrize(
    ("workflow", "dump_format", "dumper"),
    [
        ("article", "dot", GraphvizDumper()),
        ("article", "puml", PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION)),
        ("article", "mermaid", MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW)),
        ("pull_request", "dot", StateMachineGraphvizDumper()),
        ("pull_request", "puml", PlantUmlDumper(PlantUmlDumper.STATEMACHINE_TRANSITION)),
        ("pull_request", "mermaid", MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE)),
    ],
)
async def test_each_format_draws_a_traced_workflow_as_its_kind(
    workflow: str, dump_format: str, dumper: DumperInterface
) -> None:
    run = await _run(_APPLICATION, workflow, f"--dump-format={dump_format}")

    assert run.code == ExitCode.SUCCESS
    assert run.display == dumper.dump(run.definition, Marking(), {"name": workflow}) + "\n"


async def test_with_listeners_each_is_named_after_the_code_it_runs_and_a_guard_by_its_guards() -> (
    None
):
    run = await _run(_APPLICATION, "article", "--with-listeners")

    assert run.code == ExitCode.SUCCESS
    assert (
        f"<BR/>Listener #0: Guard: {_GUARDS}.is_editor"
        f"<BR/>Listener #1: {_LISTENERS}.Publication.on_publish()>"
    ) in run.display
    wrappers = ("LazyListener", "WrappedListener", "UnitOfWorkGuardListener")
    assert [wrapper for wrapper in wrappers if wrapper in run.display] == []


async def test_without_an_event_dispatcher_listing_the_listeners_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Both are installed here: make them bundles that cannot be imported. The
    # security bundle goes too, as it cannot do without the event dispatcher.
    monkeypatch.setitem(sys.modules, "xtr_event_dispatcher.bundle", None)
    monkeypatch.setitem(sys.modules, "xtr_security.bundle", None)

    run = await _run("tests.fixtures.app_workflow", "article", "--with-listeners")

    assert run.code == ExitCode.FAILURE
    assert (
        'You cannot use the "--with-listeners" option if a dispatcher is not injected in the '
        "constructor."
    ) in " ".join(run.error_display.split())
