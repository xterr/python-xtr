"""Unit tests for :class:`xtr_maker.entity.EntitySourceEditor`."""

from __future__ import annotations

import difflib
import subprocess
import sys
from typing import TYPE_CHECKING

import pytest

from xtr_maker import ClassName, InvalidArgumentError
from xtr_maker.entity import (
    EntityField,
    EntitySourceEditor,
    FieldType,
    MappedAttribute,
)

if TYPE_CHECKING:
    from pathlib import Path

_ORDER = '''"""An order."""

from __future__ import annotations

from decimal import Decimal
from typing import final

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

__all__ = ["Order"]


@final
class Order(UUIDAuditBase):
    """One order."""

    __tablename__ = "orders"  # kept as written

    number: Mapped[str] = mapped_column(String(32), unique=True)
    total: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    """What it costs."""

    def describe(self) -> str:
        return self.number
'''

_BARE = '''"""A tag."""

from __future__ import annotations

from advanced_alchemy.base import BigIntBase


class Tag(BigIntBase):
    """One tag."""

    __tablename__ = "tags"
'''


def _editor(source: str = _ORDER, name: str = "Order") -> EntitySourceEditor:
    return EntitySourceEditor(source, ClassName.create(name, root_package="app", kind="entity"))


def _add(editor: EntitySourceEditor, field: EntityField) -> None:
    imports = editor.imports()
    editor.add_attribute(field.attribute(imports), imports)


def _changed(before: str, after: str) -> list[str]:
    return [
        line
        for line in difflib.unified_diff(before.splitlines(), after.splitlines(), lineterm="", n=0)
        if line[:1] in "+-" and not line.startswith(("+++", "---"))
    ]


def test_an_untouched_source_round_trips_byte_for_byte() -> None:
    assert _editor().source == _ORDER


def test_it_reads_the_bases_the_table_and_the_names() -> None:
    editor = _editor()

    assert editor.bases == ("UUIDAuditBase",)
    assert editor.table_name == "orders"
    assert editor.has_attribute("total")
    assert editor.has_attribute("describe")
    assert not editor.has_attribute("title")


def test_a_field_goes_after_the_last_mapped_attribute_and_its_docstring() -> None:
    editor = _editor()

    _add(editor, EntityField("note", FieldType.TEXT))

    assert _changed(_ORDER, editor.source) == [
        "-from sqlalchemy import Numeric, String",
        "+from sqlalchemy import Numeric, String, Text",
        "+    note: Mapped[str] = mapped_column(Text)",
    ]
    assert '    """What it costs."""\n    note: Mapped[str]' in editor.source


def test_a_class_with_no_mapped_attribute_gets_one_after_its_table_name() -> None:
    editor = _editor(_BARE, "Tag")

    _add(editor, EntityField("label", FieldType.STRING, length=40))

    assert editor.source.endswith(
        '    __tablename__ = "tags"\n\n    label: Mapped[str] = mapped_column(String(40))\n'
    )
    assert "from sqlalchemy import String\nfrom sqlalchemy.orm import Mapped, mapped_column\n" in (
        editor.source
    )


def test_a_relationship_imports_its_target_for_annotations() -> None:
    editor = _editor()
    imports = editor.imports()
    target = imports.add("app.entity.customer", "Customer", type_checking=True)
    call = imports.add("sqlalchemy.orm", "relationship")

    editor.add_attribute(MappedAttribute("customer", target, call), imports)

    assert "from typing import TYPE_CHECKING, final\n" in editor.source
    assert "if TYPE_CHECKING:\n    from app.entity.customer import Customer\n\n__all__" in (
        editor.source
    )
    assert "from sqlalchemy.orm import Mapped, mapped_column, relationship\n" in editor.source


def test_a_name_the_class_has_is_refused_and_nothing_changes() -> None:
    editor = _editor()

    with pytest.raises(InvalidArgumentError, match="Order already has a property 'describe'"):
        _add(editor, EntityField("describe", FieldType.TEXT))

    assert editor.source == _ORDER


def test_a_name_added_once_is_refused_the_second_time() -> None:
    editor = _editor()
    _add(editor, EntityField("note", FieldType.TEXT))

    with pytest.raises(InvalidArgumentError, match="already has a property 'note'"):
        _add(editor, EntityField("note", FieldType.TEXT))


def test_a_module_without_the_class_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="defines no class Book"):
        _ = _editor(_ORDER, "Book")


def test_a_module_that_does_not_parse_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="does not parse"):
        _ = _editor("class Order(:\n")


def test_a_class_on_one_line_is_refused() -> None:
    editor = _editor("class Order(UUIDAuditBase): pass\n")

    with pytest.raises(InvalidArgumentError, match="defined on one line"):
        _add(editor, EntityField("note", FieldType.TEXT))


def test_the_edited_module_passes_the_import_sorting_and_the_formatter(tmp_path: Path) -> None:
    editor = _editor()
    for typed in ("published_at:datetime?", "reference:uuid", "status:enum:http.HTTPStatus"):
        _add(editor, EntityField.parse(typed))
    target = tmp_path / "order.py"
    _ = target.write_text(editor.source, encoding="utf-8")

    checked = _ruff("check", "--select", "I,E501", str(target))
    formatted = _ruff("format", "--check", "--diff", str(target))

    assert checked.returncode == 0, checked.stdout
    assert formatted.returncode == 0, formatted.stdout


def test_an_entity_imported_for_annotations_lets_the_import_cycle_through_once() -> None:
    editor = _editor()
    for name, entity in (("customer", "Customer"), ("courier", "Courier")):
        imports = editor.imports()
        target = imports.add(f"app.entity.{name}", entity, type_checking=True)
        editor.add_attribute(
            MappedAttribute(name, target, imports.add("sqlalchemy.orm", "relationship")), imports
        )

    assert editor.source.count("# pyright: reportImportCycles=false\nif TYPE_CHECKING:\n") == 1


def test_a_field_leaves_the_import_cycle_comment_out() -> None:
    editor = _editor()

    _add(editor, EntityField("note", FieldType.TEXT))

    assert "reportImportCycles" not in editor.source


def _ruff(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 — fixed arguments, the interpreter running the tests.
        [sys.executable, "-m", "ruff", *arguments, "--isolated"],
        capture_output=True,
        text=True,
        check=False,
    )
