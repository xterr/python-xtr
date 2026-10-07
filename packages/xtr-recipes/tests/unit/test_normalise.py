from __future__ import annotations

from xtr_recipes.normalise import normalise


def test_it_lowercases_and_unifies_separators() -> None:
    assert normalise("Xtr_Messenger") == "xtr-messenger"


def test_it_collapses_a_run_of_separators() -> None:
    assert normalise("xtr__messenger..core") == "xtr-messenger-core"


def test_it_strips_surrounding_whitespace() -> None:
    assert normalise("  xtr-clock  ") == "xtr-clock"
