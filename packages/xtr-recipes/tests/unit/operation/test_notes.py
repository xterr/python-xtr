from __future__ import annotations

from xtr_recipes.operation.notes import Notes


def test_it_renders_every_group_in_order() -> None:
    notes = Notes(steps=("call setup(app, kernel)",), check=("app debug:bundles",), run=("app go",))

    assert notes.render() == (
        "  steps:",
        "    - call setup(app, kernel)",
        "  check:",
        "    - app debug:bundles",
        "  run:",
        "    - app go",
    )


def test_it_leaves_out_an_empty_group() -> None:
    assert Notes(check=("app debug:config messenger",)).render() == (
        "  check:",
        "    - app debug:config messenger",
    )


def test_it_renders_every_entry_of_a_group() -> None:
    assert Notes(run=("first", "second")).render() == ("  run:", "    - first", "    - second")


def test_notes_with_nothing_in_them_render_nothing() -> None:
    assert Notes().render() == ()


def test_it_changes_nothing() -> None:
    assert Notes.changes is False


def test_applying_it_leaves_the_project_alone() -> None:
    assert Notes(run=("app go",)).apply() is None
