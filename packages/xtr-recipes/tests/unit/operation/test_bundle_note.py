from __future__ import annotations

import pytest

from xtr_recipes.operation.bundle_note import BundleNote


@pytest.mark.parametrize(
    "note",
    [
        "listed",
        "already listed",
        "required by another bundle",
        "removed",
        "skipped: install xtr-messenger[di]",
    ],
)
def test_it_renders_the_class_and_the_note(note: str) -> None:
    assert BundleNote("MessengerBundle", note).render() == (f"  bundle MessengerBundle {note}",)


def test_it_changes_nothing() -> None:
    assert BundleNote.changes is False


def test_applying_it_leaves_the_project_alone() -> None:
    assert BundleNote("ClockBundle", "removed").apply() is None
