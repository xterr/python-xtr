"""Unit tests for :class:`xtr_maker.entity.NeededImport`."""

from __future__ import annotations

import libcst as cst

from xtr_maker.entity import NeededImport

_STATEMENTS = cst.parse_module(
    "import os\n"
    "from typing import Final, final\n"
    "from sqlalchemy.orm import Mapped  # the annotation\n"
    "from app.x import Thing as Other\n"
    "from . import sibling\n"
    "x = 1\n"
).body


def test_read_splits_runtime_imports_from_annotation_ones() -> None:
    rendered = (
        "from typing import TYPE_CHECKING\n\nif TYPE_CHECKING:\n    from app.a import A as B\n"
    )

    runtime, annotations = NeededImport.read(rendered)

    assert runtime == [NeededImport("typing", "TYPE_CHECKING")]
    assert annotations == [NeededImport("app.a", "A", "B")]


def test_module_of_names_the_module_of_any_import() -> None:
    assert [NeededImport.module_of(statement) for statement in _STATEMENTS] == [
        "os",
        "typing",
        "sqlalchemy.orm",
        "app.x",
        ".",
        None,
    ]


def test_is_in_matches_the_name_and_its_binding() -> None:
    assert NeededImport("typing", "final").is_in(_STATEMENTS)
    assert NeededImport("app.x", "Thing", "Other").is_in(_STATEMENTS)
    assert not NeededImport("app.x", "Thing").is_in(_STATEMENTS)


def test_joinable_returns_the_statement_and_its_names() -> None:
    assert NeededImport("typing", "cast").joinable(_STATEMENTS) == (
        1,
        [("Final", None), ("final", None)],
    )


def test_a_statement_with_a_comment_or_an_aliased_name_is_not_joinable() -> None:
    assert NeededImport("sqlalchemy.orm", "relationship").joinable(_STATEMENTS) is None
    assert NeededImport("typing", "cast", "c").joinable(_STATEMENTS) is None
