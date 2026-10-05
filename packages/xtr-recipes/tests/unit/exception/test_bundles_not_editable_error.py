from __future__ import annotations

from pathlib import Path

from xtr_recipes.exception import BundlesNotEditableError, RecipesError


def test_it_derives_from_the_base() -> None:
    assert issubclass(BundlesNotEditableError, RecipesError)


def test_it_keeps_the_path_reason_and_entries() -> None:
    error = BundlesNotEditableError(Path("/x/bundles.py"), "built oddly", ("m.b:B",))

    assert error.path == Path("/x/bundles.py")
    assert error.reason == "built oddly"
    assert error.entries == ("m.b:B",)


def test_its_message_lists_the_entries_to_add() -> None:
    message = str(BundlesNotEditableError(Path("/x/bundles.py"), "oddly", ("m.b:B", "n.c:C")))

    assert "m.b:B" in message
    assert "n.c:C" in message


def test_it_omits_the_hint_when_there_are_no_entries() -> None:
    message = str(BundlesNotEditableError(Path("/x/bundles.py"), "oddly", ()))

    assert "add to BUNDLES" not in message
