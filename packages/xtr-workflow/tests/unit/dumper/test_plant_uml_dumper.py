"""A PlantUML dump draws a workflow or a state machine, byte for byte."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.support.definitions import (
    create_complex_state_machine_definition,
    create_complex_workflow_definition,
    create_simple_workflow_definition,
    create_workflow_with_same_name_back_transition,
)
from xtr_workflow import Definition, Marking, Transition
from xtr_workflow.dumper import PlantUmlDumper
from xtr_workflow.exception import InvalidArgumentError
from xtr_workflow.metadata import InMemoryMetadataStore

_FIXTURES = Path(__file__).parents[2] / "fixtures" / "puml"


def _fixture(transition_type: str, name: str) -> bytes:
    return (_FIXTURES / transition_type / f"{name}.puml").read_bytes()


@pytest.mark.parametrize(
    ("definition", "marking", "expected_file_name", "title"),
    [
        pytest.param(
            create_simple_workflow_definition(),
            None,
            "simple-workflow-nomarking",
            "SimpleDiagram",
            id="simple",
        ),
        pytest.param(
            create_complex_workflow_definition(),
            None,
            "complex-workflow-nomarking",
            "ComplexDiagram",
            id="complex",
        ),
        pytest.param(
            create_simple_workflow_definition(),
            Marking({"b": 1}),
            "simple-workflow-marking",
            "SimpleDiagram",
            id="simple-marked",
        ),
        pytest.param(
            create_complex_workflow_definition(),
            Marking({"c": 1, "e": 1}),
            "complex-workflow-marking",
            "ComplexDiagram",
            id="complex-marked",
        ),
    ],
)
def test_dump_workflow_without_marking(
    definition: Definition, marking: Marking | None, expected_file_name: str, title: str
) -> None:
    dumper = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION)

    dump = dumper.dump(definition, marking, {"title": title})

    # A fixture ends with a newline, a dump does not.
    assert (dump + "\n").encode() == _fixture(
        PlantUmlDumper.WORKFLOW_TRANSITION, expected_file_name
    )


@pytest.mark.parametrize(
    ("definition", "marking", "expected_file_name", "title"),
    [
        pytest.param(
            create_complex_state_machine_definition(),
            None,
            "complex-state-machine-nomarking",
            "SimpleDiagram",
            id="complex",
        ),
        pytest.param(
            create_complex_state_machine_definition(),
            Marking({"c": 1, "e": 1}),
            "complex-state-machine-marking",
            "SimpleDiagram",
            id="complex-marked",
        ),
    ],
)
def test_dump_state_machine_without_marking(
    definition: Definition, marking: Marking | None, expected_file_name: str, title: str
) -> None:
    dumper = PlantUmlDumper(PlantUmlDumper.STATEMACHINE_TRANSITION)

    dump = dumper.dump(definition, marking, {"title": title})

    assert (dump + "\n").encode() == _fixture(
        PlantUmlDumper.STATEMACHINE_TRANSITION, expected_file_name
    )


def test_dump_workflow_with_spaces_in_the_state_names_and_description() -> None:
    # +---------+  t 1   +----------+  |
    # | place a | -----> | place b  |  |
    # +---------+        +----------+  |
    store = InMemoryMetadataStore({}, {"place a": {"description": "My custom\nplace description"}})
    definition = Definition(
        ["place a", "place b"], [Transition("t 1", "place a", "place b")], None, store
    )

    dump = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION).dump(
        definition, None, {"title": "SimpleDiagram"}
    )

    assert (dump + "\n").encode() == _fixture(
        PlantUmlDumper.WORKFLOW_TRANSITION, "simple-workflow-with-spaces"
    )


def test_an_unknown_transition_type_is_refused() -> None:
    with pytest.raises(InvalidArgumentError) as raised:
        _ = PlantUmlDumper("foo")

    assert str(raised.value) == "Transition type 'foo' does not exist."


def test_it_lists_both_transition_types() -> None:
    assert PlantUmlDumper.TRANSITION_TYPES == ("arrow", "square")


SQUARE_STYLED_DUMP = r"""@startuml
allow_mixing
title T
title N
skinparam titleBorderRoundCorner 15
skinparam titleBorderThickness 2
skinparam state {
    BackgroundColor<<initial>> #87b741
    BackgroundColor<<marked>> #3887C6
    BorderColor #3887C6
    BorderColor<<marked>> Black
    FontColor<<marked>> White
    FontSize 12
    BackgroundColor<<ABCDEF>> #ABCDEF
    BackgroundColor<<Yellow>> Yellow
}
skinparam agent {
    BackgroundColor #ffffff
    BorderColor #3887C6
}
skinparam handwritten true
state "a" <<initial>> <<ABCDEF>>
"a" : x
"a" : y
state "b" <<marked>> <<Yellow>>
state "cd e"
agent "t1"
agent "t2"
"a" -[#Red]-> "t1": "<font color=Blue>Go</font>\n<font color=Blue>now</font>"
"t1" -[#Red]-> "b": "<font color=Blue>Go</font>\n<font color=Blue>now</font>"
"b" -[#00ff00]-> "t2"
"t2" -[#00ff00]-> "cd
e"
@enduml"""

ARROW_STYLED_DUMP = r"""@startuml
allow_mixing
title T
title N
skinparam titleBorderRoundCorner 15
skinparam titleBorderThickness 2
skinparam state {
    BackgroundColor<<initial>> #87b741
    BackgroundColor<<marked>> #3887C6
    BorderColor #3887C6
    BorderColor<<marked>> Black
    FontColor<<marked>> White
    FontSize 12
    BackgroundColor<<ABCDEF>> #ABCDEF
    BackgroundColor<<Yellow>> Yellow
}
skinparam handwritten true
state "a" <<initial>> <<ABCDEF>>
"a" : x
"a" : y
state "b" <<marked>> <<Yellow>>
state "cd e"
"a" -[#Red]-> "b": "<font color=Blue>Go</font>\n<font color=Blue>now</font>"
"b" -[#00ff00]-> "cd
e": "t2"
@enduml"""


def _styled_definition() -> Definition:
    # Quotes cannot be escaped in a name, so they are dropped; colours with
    # and without "#", a description with empty and "0" lines, a coloured
    # label over two lines.
    first = Transition('t"1', "a", "b")
    second = Transition("t2", "b", 'c"d\ne')
    store = InMemoryMetadataStore(
        {},
        {"a": {"bg_color": "#ABCDEF", "description": "x\n\n0\ny"}, "b": {"bg_color": "Yellow"}},
        {
            first: {"arrow_color": "Red", "color": "Blue", "label": "Go\nnow"},
            second: {"arrow_color": "#00ff00"},
        },
    )
    return Definition(["a", "b", 'c"d\ne'], [first, second], None, store)


@pytest.mark.parametrize(
    ("transition_type", "expected"),
    [
        pytest.param(PlantUmlDumper.WORKFLOW_TRANSITION, SQUARE_STYLED_DUMP, id="square"),
        pytest.param(PlantUmlDumper.STATEMACHINE_TRANSITION, ARROW_STYLED_DUMP, id="arrow"),
    ],
)
def test_dump_styles_places_and_transitions_from_their_metadata(
    transition_type: str, expected: str
) -> None:
    options = {
        "title": "T",
        "name": "N",
        "skinparams": {"handwritten": "true", "state": {"FontSize": 12}},
    }

    dump = PlantUmlDumper(transition_type).dump(_styled_definition(), Marking({"b": 1}), options)

    assert dump == expected


SAME_NAME_BACK_TRANSITION_DUMP = """@startuml
allow_mixing
skinparam titleBorderRoundCorner 15
skinparam titleBorderThickness 2
skinparam state {
    BackgroundColor<<initial>> #87b741
    BackgroundColor<<marked>> #3887C6
    BorderColor #3887C6
    BorderColor<<marked>> Black
    FontColor<<marked>> White
}
skinparam agent {
    BackgroundColor #ffffff
    BorderColor #3887C6
}
state "a" <<initial>>
state "b"
state "c"
agent "a_to_bc"
agent "back1"
agent "back1"
agent "back2"
agent "back2"
agent "c_to_cb"
"a" --> "a_to_bc"
"a_to_bc" --> "b"
"a_to_bc" --> "c"
"b" --> "back1"
"back1" --> "a"
"c" --> "back1"
"back1" --> "b"
"c" --> "back2"
"back2" --> "b"
"b" --> "back2"
"back2" --> "a"
"c" --> "c_to_cb"
"c_to_cb" --> "b"
"c_to_cb" --> "c"
@enduml"""


def test_dump_draws_each_workflow_line_once() -> None:
    dump = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION).dump(
        create_workflow_with_same_name_back_transition()
    )

    assert dump == SAME_NAME_BACK_TRANSITION_DUMP


def test_dump_skips_skin_parameters_that_are_not_a_mapping() -> None:
    dump = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION).dump(
        Definition(["a"], []), None, {"skinparams": "none"}
    )

    assert dump == '@startuml\nallow_mixing\nstate "a" <<initial>>\n@enduml'


def test_dump_leaves_the_default_skin_parameters_unchanged() -> None:
    dumper = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION)
    _ = dumper.dump(_styled_definition())

    assert "<<ABCDEF>>" not in dumper.dump(Definition(["a"], []))


@pytest.mark.parametrize(
    ("skinparams", "expected_lines"),
    [
        pytest.param("none", [], id="skin-parameters-not-a-mapping"),
        pytest.param(
            {"state": "flat"},
            [
                "skinparam titleBorderRoundCorner 15",
                "skinparam titleBorderThickness 2",
                "skinparam state flat",
                "skinparam agent {",
                "    BackgroundColor #ffffff",
                "    BorderColor #3887C6",
                "}",
            ],
            id="state-not-a-mapping",
        ),
    ],
)
def test_dump_draws_no_fill_style_where_the_skin_parameters_hold_none(
    skinparams: object, expected_lines: list[str]
) -> None:
    definition = Definition(["a"], [], None, InMemoryMetadataStore({}, {"a": {"bg_color": "Red"}}))

    dump = PlantUmlDumper(PlantUmlDumper.WORKFLOW_TRANSITION).dump(
        definition, None, {"skinparams": skinparams}
    )

    assert dump.split("\n") == [
        "@startuml",
        "allow_mixing",
        *expected_lines,
        'state "a" <<initial>> <<Red>>',
        "@enduml",
    ]
