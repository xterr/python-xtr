"""Definitions the dumper and workflow tests share.

Each one exercises a shape the dumpers draw differently: tokens split and
joined, metadata styling a place or a transition, several transitions sharing
a name. Places, transitions, metadata and their order are fixed, since the
expected dumps are byte-exact.
"""

from __future__ import annotations

from xtr_workflow import Definition, Transition
from xtr_workflow.metadata import InMemoryMetadataStore

__all__ = [
    "create_complex_state_machine_definition",
    "create_complex_workflow_definition",
    "create_simple_workflow_definition",
    "create_workflow_with_metadata_edge_cases",
    "create_workflow_with_same_name_back_transition",
    "create_workflow_with_same_name_transition",
]


def create_complex_workflow_definition() -> Definition:
    """Return a workflow that splits a token in two, joins them, then forks.

    ::

        +---+     +----+     +---+     +----+     +----+     +----+     +----+     +----+     +---+
        | a | --> | t1 | --> | c | --> | t2 | --> | d  | --> | t4 | --> | f  | --> | t6 | --> | g |
        +---+     +----+     +---+     +----+     +----+     +----+     +----+     +----+     +---+
                    |                    ^          |                                           ^
                    |                    |          |                                           |
                    v                    |          v                                           |
                  +----+                 |        +----+     +----+     +----+                  |
                  | b  | ----------------+        | t3 | --> | e  | --> | t5 | -----------------+
                  +----+                          +----+     +----+     +----+
    """
    transition_with_metadata_dump_style = Transition("t3", "d", "e")
    transitions = [
        Transition("t1", "a", ["b", "c"]),
        Transition("t2", ["b", "c"], "d"),
        transition_with_metadata_dump_style,
        Transition("t4", "d", "f"),
        Transition("t5", "e", "g"),
        Transition("t6", "f", "g"),
    ]
    metadata_store = InMemoryMetadataStore(
        {},
        {},
        {
            transition_with_metadata_dump_style: {
                "label": "My custom transition label 1",
                "color": "Red",
                "arrow_color": "Green",
            },
        },
    )

    return Definition(list("abcdefg"), transitions, None, metadata_store)


def create_simple_workflow_definition() -> Definition:
    """Return a straight workflow whose transitions and last place carry styling metadata.

    ::

        +---+     +----+     +---+     +----+     +---+
        | a | --> | t1 | --> | b | --> | t2 | --> | c |
        +---+     +----+     +---+     +----+     +---+
    """
    transition_with_metadata_dump_style = Transition("t1", "a", "b")
    transition_with_metadata_arrow_color_pink = Transition("t2", "b", "c")
    metadata_store = InMemoryMetadataStore(
        {},
        {
            "c": {
                "bg_color": "DeepSkyBlue",
                "description": "My custom place description",
            },
        },
        {
            transition_with_metadata_dump_style: {
                "label": "My custom transition label 2",
                "color": "Grey",
                "arrow_color": "Purple",
            },
            transition_with_metadata_arrow_color_pink: {
                "arrow_color": "Pink",
            },
        },
    )

    return Definition(
        list("abc"),
        [transition_with_metadata_dump_style, transition_with_metadata_arrow_color_pink],
        None,
        metadata_store,
    )


def create_workflow_with_metadata_edge_cases() -> Definition:
    """Return a straight workflow whose places and last transition carry partial metadata.

    A colour without a description, a description without a colour, both with
    a description spanning two lines, and characters a markup label must escape.
    """
    transition_with_description = Transition("t3", "c", "d")
    transitions = [
        Transition("t1", "a", "b"),
        Transition("t2", "b", "c"),
        transition_with_description,
    ]
    metadata_store = InMemoryMetadataStore(
        {},
        {
            # A colour only, no description.
            "b": {
                "bg_color": "Orange",
            },
            # A description only, no colour.
            "c": {
                "description": 'A <bold> description with "special" chars & entities',
            },
            # A description over two lines, with a colour.
            "d": {
                "bg_color": "Lime",
                "description": "First line\nSecond line",
            },
        },
        {
            transition_with_description: {
                "bg_color": "LightCoral",
                "description": "Transition description",
            },
        },
    )

    return Definition(list("abcd"), transitions, None, metadata_store)


def create_workflow_with_same_name_transition() -> Definition:
    """Return a workflow where two transitions named ``to_a`` lead back from different places.

    ::

          +------------------------------------------------------------+
          |                                                            |
          |                                                            |
          |         +----------------------------------------+         |
          v         |                                        v         |
        +---+     +---------+     +---+     +--------+     +---+     +------+
        | a | --> | a_to_bc | --> | b | --> | b_to_c | --> | c | --> | to_a | -+
        +---+     +---------+     +---+     +--------+     +---+     +------+  |
          ^                         |                                  ^       |
          |                         +----------------------------------+       |
          |                                                                    |
          |                                                                    |
          +--------------------------------------------------------------------+
    """
    transitions = [
        Transition("a_to_bc", "a", ["b", "c"]),
        Transition("b_to_c", "b", "c"),
        Transition("to_a", "b", "a"),
        Transition("to_a", "c", "a"),
    ]

    return Definition(list("abc"), transitions)


def create_complex_state_machine_definition() -> Definition:
    """Return a state machine where two transitions named ``t1`` enter ``b``.

    The second ``t1`` carries a label spanning two lines.

    ::

                            t1
                      +------------------+
                      v                  |
        +---+  t1   +-----+  t2   +---+  |
        | a | ----> |  b  | ----> | c |  |
        +---+       +-----+       +---+  |
                      |                  |
                      | t3               |
                      v                  |
                    +-----+              |
                    |  d  | -------------+
                    +-----+
    """
    transition_with_metadata_dump_style = Transition("t1", "d", "b")
    transition_with_metadata_arrow_color_blue = Transition("t2", "b", "c")
    transitions = [
        Transition("t1", "a", "b"),
        transition_with_metadata_dump_style,
        transition_with_metadata_arrow_color_blue,
        Transition("t3", "b", "d"),
    ]
    metadata_store = InMemoryMetadataStore(
        {},
        {},
        {
            transition_with_metadata_dump_style: {
                "label": "My custom transition\nlabel 3",
                "color": "Grey",
                "arrow_color": "Red",
            },
            transition_with_metadata_arrow_color_blue: {
                "arrow_color": "Blue",
            },
        },
    )

    return Definition(["a", "b", "c", "d"], transitions, None, metadata_store)


def create_workflow_with_same_name_back_transition() -> Definition:
    """Return a workflow where pairs of transitions named ``back1`` and ``back2`` lead back.

    ::

          +-----------------------------------------------------------------+
          |                                                                 |
          |                                                                 |
          |         +---------------------------------------------+         |
          v         |                                             v         |
        +---+     +---------+     +-------+     +---------+     +---+     +-------+
        | a | --> | a_to_bc | --> |       | --> |  back2  | --> |   | --> | back2 |
        +---+     +---------+     |       |     +---------+     |   |     +-------+
          ^                       |       |                     |   |
          |                       |   c   | <-----+             | b |
          |                       |       |       |             |   |
          |                       |       |     +---------+     |   |     +-------+
          |                       |       | --> | c_to_cb | --> |   | --> | back1 |
          |                       +-------+     +---------+     +---+     +-------+
          |                         |                             ^         |
          |                         |                             |         |
          |                         v                             |         |
          |                       +-------+                       |         |
          |                       | back1 | ----------------------+         |
          |                       +-------+                                 |
          |                                                                 |
          +-----------------------------------------------------------------+
    """
    transitions = [
        Transition("a_to_bc", "a", ["b", "c"]),
        Transition("back1", "b", "a"),
        Transition("back1", "c", "b"),
        Transition("back2", "c", "b"),
        Transition("back2", "b", "a"),
        Transition("c_to_cb", "c", ["b", "c"]),
    ]

    return Definition(list("abc"), transitions)
