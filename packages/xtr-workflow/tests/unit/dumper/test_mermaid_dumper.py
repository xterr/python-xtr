"""A Mermaid dump draws a workflow or a state machine as a flowchart, byte for byte."""

from __future__ import annotations

import pytest

from tests.support.definitions import (
    create_complex_state_machine_definition,
    create_complex_workflow_definition,
    create_simple_workflow_definition,
    create_workflow_with_same_name_back_transition,
    create_workflow_with_same_name_transition,
)
from xtr_workflow import Arc, Definition, DefinitionBuilder, Marking, Transition
from xtr_workflow.dumper import MermaidDumper
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.metadata import InMemoryMetadataStore


def _reserved_words_definition() -> Definition:
    builder = DefinitionBuilder()
    _ = builder.add_places(["start", "subgraph", "end", "finish"])
    _ = builder.add_transitions(
        [
            Transition("t0", ["start", "subgraph"], ["end"]),
            Transition("t1", ["end"], ["finish"]),
        ]
    )
    return builder.build()


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        pytest.param(
            create_complex_workflow_definition(),
            "graph LR\n"
            'place0(["a"])\n'
            'place1(("b"))\n'
            'place2(("c"))\n'
            'place3(("d"))\n'
            'place4(("e"))\n'
            'place5(("f"))\n'
            'place6(("g"))\n'
            'transition0["t1"]\n'
            "place0-->transition0\n"
            "transition0-->place1\n"
            "transition0-->place2\n"
            'transition1["t2"]\n'
            "place1-->transition1\n"
            "transition1-->place3\n"
            "place2-->transition1\n"
            'transition2["My custom transition label 1"]\n'
            "place3-->transition2\n"
            "linkStyle 6 stroke:Red\n"
            "transition2-->place4\n"
            "linkStyle 7 stroke:Red\n"
            'transition3["t4"]\n'
            "place3-->transition3\n"
            "transition3-->place5\n"
            'transition4["t5"]\n'
            "place4-->transition4\n"
            "transition4-->place6\n"
            'transition5["t6"]\n'
            "place5-->transition5\n"
            "transition5-->place6",
            id="complex",
        ),
        pytest.param(
            create_workflow_with_same_name_transition(),
            "graph LR\n"
            'place0(["a"])\n'
            'place1(("b"))\n'
            'place2(("c"))\n'
            'transition0["a_to_bc"]\n'
            "place0-->transition0\n"
            "transition0-->place1\n"
            "transition0-->place2\n"
            'transition1["b_to_c"]\n'
            "place1-->transition1\n"
            "transition1-->place2\n"
            'transition2["to_a"]\n'
            "place1-->transition2\n"
            "transition2-->place0\n"
            'transition3["to_a"]\n'
            "place2-->transition3\n"
            "transition3-->place0",
            id="same-name-transition",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            "graph LR\n"
            'place0(["a"])\n'
            'place1(("b"))\n'
            'place2(("c"))\n'
            "style place2 fill:DeepSkyBlue\n"
            'transition0["My custom transition label 2"]\n'
            "place0-->transition0\n"
            "linkStyle 0 stroke:Grey\n"
            "transition0-->place1\n"
            "linkStyle 1 stroke:Grey\n"
            'transition1["t2"]\n'
            "place1-->transition1\n"
            "transition1-->place2",
            id="simple",
        ),
    ],
)
def test_dump_without_marking(definition: Definition, expected: str) -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(definition)

    assert dump == expected


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        pytest.param(
            _reserved_words_definition(),
            "graph LR\n"
            'place0(["start"])\n'
            'place1(("subgraph"))\n'
            'place2(("end"))\n'
            'place3(("finish"))\n'
            'transition0["t0"]\n'
            "place0-->transition0\n"
            "transition0-->place2\n"
            "place1-->transition0\n"
            'transition1["t1"]\n'
            "place2-->transition1\n"
            "transition1-->place3",
            id="reserved-words",
        ),
    ],
)
def test_dump_with_reserved_words_as_place_names(definition: Definition, expected: str) -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(definition)

    assert dump == expected


@pytest.mark.parametrize(
    ("definition", "expected"),
    [
        pytest.param(
            create_complex_state_machine_definition(),
            "graph LR\n"
            'place0(["a"])\n'
            'place1(("b"))\n'
            'place2(("c"))\n'
            'place3(("d"))\n'
            'place0-->|"t1"|place1\n'
            'place3-->|"My custom transition label 3"|place1\n'
            "linkStyle 1 stroke:Grey\n"
            'place1-->|"t2"|place2\n'
            'place1-->|"t3"|place3',
            id="complex",
        ),
    ],
)
def test_dump_as_state_machine(definition: Definition, expected: str) -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE).dump(definition)

    assert dump == expected


def _marked_b_and_c() -> Marking:
    marking = Marking()
    marking.mark("b")
    marking.mark("c")
    return marking


@pytest.mark.parametrize(
    ("definition", "marking", "expected"),
    [
        pytest.param(
            create_simple_workflow_definition(),
            _marked_b_and_c(),
            "graph LR\n"
            'place0(["a"])\n'
            'place1(("b"))\n'
            "style place1 stroke-width:4px\n"
            'place2(("c"))\n'
            "style place2 fill:DeepSkyBlue,stroke-width:4px\n"
            'transition0["My custom transition label 2"]\n'
            "place0-->transition0\n"
            "linkStyle 0 stroke:Grey\n"
            "transition0-->place1\n"
            "linkStyle 1 stroke:Grey\n"
            'transition1["t2"]\n'
            "place1-->transition1\n"
            "transition1-->place2",
            id="simple",
        ),
    ],
)
def test_dump_workflow_with_marking(
    definition: Definition, marking: Marking, expected: str
) -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(definition, marking)

    assert dump == expected


def test_label_cannot_end_its_own_node() -> None:
    definition = Definition(
        ["start", "a#quot;]-->EVIL[x"], [Transition("go", "start", "a#quot;]-->EVIL[x")]
    )

    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE).dump(definition)

    assert 'place1(("a#35;quot;]-->EVIL[x"))' in dump


@pytest.mark.parametrize("direction", ["TB", "TD", "BT", "RL", "LR"])
def test_dump_draws_in_the_given_direction(direction: str) -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_STATEMACHINE, direction).dump(
        Definition(["a"], [])
    )

    assert dump == f'graph {direction}\nplace0(["a"])'


def test_it_draws_left_to_right_by_default() -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(Definition(["a"], []))

    assert dump == 'graph LR\nplace0(["a"])'


def test_an_unknown_direction_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW, "XX")

    assert (
        str(raised.value)
        == 'Direction "XX" is not valid, valid directions are: "TB, TD, BT, RL, LR".'
    )


def test_an_unknown_transition_type_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = MermaidDumper("foo")

    assert (
        str(raised.value)
        == 'Transition type "foo" is not valid, valid types are: "statemachine, workflow".'
    )


def test_dump_shows_weights_tokens_labels_and_transition_colours() -> None:
    transition = Transition("t1", [Arc("a", 2)], [Arc("b", 3)])
    store = InMemoryMetadataStore(
        {}, {"a": {"label": "Start #1"}}, {transition: {"bg_color": "Red", "color": "Blue"}}
    )
    definition = Definition(["a", "b"], [transition], None, store)

    dump = MermaidDumper(
        MermaidDumper.TRANSITION_TYPE_WORKFLOW, MermaidDumper.DIRECTION_TOP_TO_BOTTOM
    ).dump(definition, Marking({"a": 3, "b": 1}))

    assert dump == (
        "graph TB\n"
        'place0(["Start #35;1 (3)"])\n'
        "style place0 stroke-width:4px\n"
        'place1(("b"))\n'
        "style place1 stroke-width:4px\n"
        'transition0["t1"]\n'
        "style transition0 fill:Red\n"
        "place0-->|2|transition0\n"
        "linkStyle 0 stroke:Blue\n"
        "transition0-->|3|place1\n"
        "linkStyle 1 stroke:Blue"
    )


def test_dump_counts_a_link_drawn_twice_once() -> None:
    transition = Transition("t1", "a", ["b", "c"])
    store = InMemoryMetadataStore({}, {}, {transition: {"color": "Red"}})
    definition = Definition(
        ["a", "b", "c"], [transition, Transition("t2", ["b", "c"], "a")], None, store
    )
    dumper = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW)

    dump = dumper.dump(definition)

    assert dump == (
        "graph LR\n"
        'place0(["a"])\n'
        'place1(("b"))\n'
        'place2(("c"))\n'
        'transition0["t1"]\n'
        "place0-->transition0\n"
        "linkStyle 0 stroke:Red\n"
        "transition0-->place1\n"
        "linkStyle 1 stroke:Red\n"
        "linkStyle 2 stroke:Red\n"
        "transition0-->place2\n"
        "linkStyle 3 stroke:Red\n"
        'transition1["t2"]\n'
        "place1-->transition1\n"
        "transition1-->place0\n"
        "place2-->transition1"
    )
    assert dumper.dump(definition) == dump


def test_dump_as_state_machine_draws_one_link_per_pair_of_places() -> None:
    dump = MermaidDumper(
        MermaidDumper.TRANSITION_TYPE_STATEMACHINE, MermaidDumper.DIRECTION_RIGHT_TO_LEFT
    ).dump(create_workflow_with_same_name_back_transition())

    assert dump == (
        "graph RL\n"
        'place0(["a"])\n'
        'place1(("b"))\n'
        'place2(("c"))\n'
        'place0-->|"a_to_bc"|place1\n'
        'place0-->|"a_to_bc"|place2\n'
        'place1-->|"back1"|place0\n'
        'place2-->|"back1"|place1\n'
        'place2-->|"back2"|place1\n'
        'place1-->|"back2"|place0\n'
        'place2-->|"c_to_cb"|place1\n'
        'place2-->|"c_to_cb"|place2'
    )


def test_dump_draws_one_node_per_transition_sharing_a_name() -> None:
    dump = MermaidDumper(MermaidDumper.TRANSITION_TYPE_WORKFLOW).dump(
        create_workflow_with_same_name_back_transition()
    )

    assert dump == (
        "graph LR\n"
        'place0(["a"])\n'
        'place1(("b"))\n'
        'place2(("c"))\n'
        'transition0["a_to_bc"]\n'
        "place0-->transition0\n"
        "transition0-->place1\n"
        "transition0-->place2\n"
        'transition1["back1"]\n'
        "place1-->transition1\n"
        "transition1-->place0\n"
        'transition2["back1"]\n'
        "place2-->transition2\n"
        "transition2-->place1\n"
        'transition3["back2"]\n'
        "place2-->transition3\n"
        "transition3-->place1\n"
        'transition4["back2"]\n'
        "place1-->transition4\n"
        "transition4-->place0\n"
        'transition5["c_to_cb"]\n'
        "place2-->transition5\n"
        "transition5-->place1\n"
        "transition5-->place2"
    )
