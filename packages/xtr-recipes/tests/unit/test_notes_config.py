from __future__ import annotations

from xtr_recipes.notes_config import NotesConfig


def test_it_defaults_every_list_to_empty() -> None:
    notes = NotesConfig()

    assert notes.steps == ()
    assert notes.check == ()
    assert notes.run == ()


def test_it_keeps_the_lines_it_is_given() -> None:
    notes = NotesConfig(steps=("edit kernel",), check=("debug:bundles",), run=("consume",))

    assert notes.steps == ("edit kernel",)
    assert notes.check == ("debug:bundles",)
    assert notes.run == ("consume",)
