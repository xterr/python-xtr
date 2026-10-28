"""Anything that dumps a definition to text is a dumper."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest

from xtr_workflow.dumper import (
    DumperInterface,
    GraphvizDumper,
    MermaidDumper,
    PlantUmlDumper,
    StateMachineGraphvizDumper,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from xtr_workflow import Definition, Marking


@final
class _Dumps:
    def dump(
        self,
        definition: Definition,
        marking: Marking | None = None,
        options: Mapping[str, object] | None = None,
    ) -> str:
        return f"{definition}{marking}{options}"


@final
class _Draws:
    def draw(self, definition: Definition) -> str:
        return str(definition)


@pytest.mark.parametrize(
    "dumper",
    [
        pytest.param(GraphvizDumper(), id="graphviz"),
        pytest.param(StateMachineGraphvizDumper(), id="state-machine-graphviz"),
        pytest.param(PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION), id="plant-uml"),
        pytest.param(MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW), id="mermaid"),
    ],
)
def test_every_dumper_satisfies_the_contract(dumper: object) -> None:
    assert isinstance(dumper, DumperInterface)


def test_an_object_that_dumps_satisfies_the_contract() -> None:
    assert isinstance(_Dumps(), DumperInterface)


def test_an_object_that_cannot_dump_does_not() -> None:
    assert not isinstance(_Draws(), DumperInterface)
