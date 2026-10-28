# ruff: noqa: E501 -- the expected dumps are byte-exact; their lines cannot wrap.
"""A state machine's Graphviz dump draws each transition as a labelled edge, byte for byte."""

from __future__ import annotations

from tests.support.definitions import (
    create_complex_state_machine_definition,
    create_workflow_with_same_name_back_transition,
)
from xtr_workflow import Definition, Marking, Transition
from xtr_workflow.dumper import GraphvizDumper, StateMachineGraphvizDumper
from xtr_workflow.metadata import InMemoryMetadataStore

DUMP_WITHOUT_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="t1" style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="My custom transition
label 3" style="solid" fontcolor="Grey" color="Red"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label="t2" style="solid" color="Blue"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_3c363836cf4e16666669a25da280a1865c2d2874 [label="t3" style="solid"];
}
"""

DUMP_WITH_MARKING = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle color="#FF0000" shape="doublecircle"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_3c363836cf4e16666669a25da280a1865c2d2874 [label=<<B>d</B>>, shape=circle];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="t1" style="solid"];
  place_3c363836cf4e16666669a25da280a1865c2d2874 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="My custom transition
label 3" style="solid" fontcolor="Grey" color="Red"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label="t2" style="solid" color="Blue"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_3c363836cf4e16666669a25da280a1865c2d2874 [label="t3" style="solid"];
}
"""

WITH_METADATA_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_5fc7e38bffe00ca46add89145464a2eaf759d5c2 [label=<<B>open</B><BR/><I>Initial state</I>>, shape=circle style="filled" fillcolor="Gold"];
  place_dba928f4ece84b8c361d19595284bfb3c79d03fe [label=<<B>in_progress</B>>, shape=circle];
  place_e5fd9cfe0e8039111d54b588e77b2bb0cad41c3a [label=<<B>done</B>>, shape=circle style="filled" fillcolor="LimeGreen"];
  place_5fc7e38bffe00ca46add89145464a2eaf759d5c2 -> place_dba928f4ece84b8c361d19595284bfb3c79d03fe [label="start" style="solid"];
  place_dba928f4ece84b8c361d19595284bfb3c79d03fe -> place_e5fd9cfe0e8039111d54b588e77b2bb0cad41c3a [label="finish" style="solid"];
}
"""

SAME_NAME_BACK_TRANSITION_DUMP = """digraph workflow {
  ratio="compress" rankdir="LR"
  node [fontsize="9" fontname="Arial" color="#333333" fillcolor="lightblue" fixedsize="false" width="1"];
  edge [fontsize="9" fontname="Arial" color="#333333" arrowhead="normal" arrowsize="0.5"];

  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label=<<B>a</B>>, shape=circle style="filled"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label=<<B>b</B>>, shape=circle];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label=<<B>c</B>>, shape=circle];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="a_to_bc" style="solid"];
  place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label="a_to_bc" style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label="back1" style="solid"];
  place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 -> place_86f7e437faa5a7fce15d1ddcb9eaeaea377667b8 [label="back2" style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="back1" style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="back2" style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> place_e9d71f5ee7c92d6dc9e92ffdad17b8bd49418f98 [label="c_to_cb" style="solid"];
  place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 -> place_84a516841ba77a5b4648de2cd0dfcb30ea46dbb4 [label="c_to_cb" style="solid"];
}
"""


def _open_in_progress_done() -> Definition:
    store = InMemoryMetadataStore(
        {},
        {
            "open": {"bg_color": "Gold", "description": "Initial state"},
            "done": {"bg_color": "LimeGreen"},
        },
    )
    transitions = [
        Transition("start", "open", "in_progress"),
        Transition("finish", "in_progress", "done"),
    ]
    return Definition(["open", "in_progress", "done"], transitions, None, store)


def test_dump_without_marking() -> None:
    dump = StateMachineGraphvizDumper().dump(create_complex_state_machine_definition())

    assert dump == DUMP_WITHOUT_MARKING


def test_dump_with_marking() -> None:
    dump = StateMachineGraphvizDumper().dump(
        create_complex_state_machine_definition(), Marking({"b": 1})
    )

    assert dump == DUMP_WITH_MARKING


def test_dump_with_metadata() -> None:
    dump = StateMachineGraphvizDumper().dump(
        _open_in_progress_done(), None, {"with-metadata": True}
    )

    # A colour fills the place rather than showing as text; a description shows in italics.
    assert 'fillcolor="Gold"' in dump
    assert "bg_color" not in dump
    assert "<I>Initial state</I>" in dump
    assert 'fillcolor="LimeGreen"' in dump


def test_dump_with_metadata_is_byte_exact() -> None:
    dump = StateMachineGraphvizDumper().dump(
        _open_in_progress_done(), None, {"with-metadata": True}
    )

    assert dump == WITH_METADATA_DUMP


def test_dump_groups_edges_by_the_place_they_leave() -> None:
    dump = StateMachineGraphvizDumper().dump(create_workflow_with_same_name_back_transition())

    assert dump == SAME_NAME_BACK_TRANSITION_DUMP


def test_it_is_a_graphviz_dumper() -> None:
    assert isinstance(StateMachineGraphvizDumper(), GraphvizDumper)
