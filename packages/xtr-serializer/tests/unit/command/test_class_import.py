"""A class is found from its module and its name, or the reason it cannot be is given."""

from __future__ import annotations

import sys
from typing import TYPE_CHECKING

import pytest

from tests.fixtures.described import Shipment
from tests.fixtures.hierarchies import Event
from xtr_serializer.command._class_import import import_class

if TYPE_CHECKING:
    from pathlib import Path


@pytest.mark.parametrize(
    "path", ["tests.fixtures.described:Shipment", "tests.fixtures.described.Shipment"]
)
def test_a_class_is_found_by_its_module_and_name(path: str) -> None:
    assert import_class(path) is Shipment


def test_a_class_inside_a_package_is_found_by_its_dotted_path() -> None:
    assert import_class("tests.fixtures.hierarchies.Event") is Event


def test_a_module_that_does_not_exist_is_named() -> None:
    assert import_class("tests.fixtures.nowhere:Shipment") == (
        "no module 'tests.fixtures.nowhere' can be imported"
    )


def test_a_dotted_path_naming_no_module_is_refused() -> None:
    assert import_class("nowhere_at_all.Shipment") == (
        "no module of 'nowhere_at_all.Shipment' can be imported"
    )


@pytest.mark.parametrize(
    "path", ["tests.fixtures.described:Missing", "tests.fixtures.described.Missing"]
)
def test_a_name_the_module_does_not_have_is_refused(path: str) -> None:
    assert import_class(path) == "'tests.fixtures.described' has no 'Missing'"


def test_what_is_not_a_class_is_refused() -> None:
    assert import_class("tests.fixtures.described:not_a_class") == (
        "'tests.fixtures.described:not_a_class' is a function, not a class"
    )


@pytest.mark.parametrize("path", ["", "Shipment", ":Shipment", "tests.fixtures.described:", ".x.Y"])
def test_a_path_naming_no_module_and_class_is_refused(path: str) -> None:
    assert import_class(path) == (
        f"{path!r} names no class: write it module:Class, or module.Class"
    )


def test_a_module_failing_to_import_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / "xtr_serializer_broken_module.py").write_text(
        "import xtr_serializer_missing_dependency\n"
    )
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])

    refusal = import_class("xtr_serializer_broken_module:Anything")

    assert refusal == (
        "'xtr_serializer_broken_module' cannot be imported: "
        "No module named 'xtr_serializer_missing_dependency'"
    )


def test_a_module_importing_a_name_its_module_lacks_says_why(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _ = (tmp_path / "xtr_serializer_lacking_module.py").write_text("from os import lacking\n")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])

    refusal = import_class("xtr_serializer_lacking_module.Anything")

    assert isinstance(refusal, str)
    assert refusal.startswith(
        "'xtr_serializer_lacking_module' cannot be imported: cannot import name 'lacking'"
    )
