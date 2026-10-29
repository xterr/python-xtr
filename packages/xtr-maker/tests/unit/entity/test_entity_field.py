"""Unit tests for :class:`xtr_maker.entity.EntityField`."""

from __future__ import annotations

from http import HTTPStatus

import pytest

from xtr_maker import ImportCollector, InvalidArgumentError
from xtr_maker.entity import EntityField, FieldType


def _line(field: EntityField) -> tuple[str, str]:
    imports = ImportCollector("app")
    line = field.attribute(imports).render()
    return line, imports.render()


def test_a_string_takes_its_length() -> None:
    assert EntityField.parse("title:string:120") == EntityField(
        "title", FieldType.STRING, length=120
    )


def test_a_decimal_takes_its_precision_and_scale() -> None:
    field = EntityField.parse("price:decimal:12:3")

    assert (field.precision, field.scale) == (12, 3)


def test_a_question_mark_makes_it_nullable() -> None:
    assert EntityField.parse("published_at:datetime?").nullable


def test_a_name_alone_gets_the_type_it_suggests() -> None:
    assert EntityField.parse("is_active").type is FieldType.BOOLEAN


def test_an_enum_takes_its_class() -> None:
    field = EntityField.parse("status:enum:http.HTTPStatus")

    assert field.enum_class == "http.HTTPStatus"
    assert EntityField.enum_type("http.HTTPStatus") is HTTPStatus


@pytest.mark.parametrize(
    ("typed", "reason"),
    [
        ("title:text:12", "does not read as a field"),
        ("status:enum", "does not read as a field"),
        ("title:words", "There is no field type 'words'"),
        ("title:string:long", "is not a whole number"),
        ("title:string:0", "must be at least 1"),
        ("price:decimal:2:5", "scale between 0 and its precision"),
        ("status:enum:http.Nothing", "names no enum"),
        ("status:enum:collections.OrderedDict", "names no enum"),
        ("class:string", "keyword"),
    ],
)
def test_a_field_that_cannot_be_written_is_refused(typed: str, reason: str) -> None:
    with pytest.raises(InvalidArgumentError, match=reason):
        _ = EntityField.parse(typed)


def test_a_string_renders_its_column_and_imports() -> None:
    line, imports = _line(EntityField("title", FieldType.STRING, length=120))

    assert line == "title: Mapped[str] = mapped_column(String(120))\n"
    assert (
        imports == "from sqlalchemy import String\nfrom sqlalchemy.orm import Mapped, mapped_column"
    )


def test_a_nullable_field_is_optional_and_says_so_to_the_column() -> None:
    line, _ = _line(EntityField("price", FieldType.DECIMAL, nullable=True))

    assert line == "price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)\n"


@pytest.mark.parametrize(
    ("kind", "annotation", "column"),
    [
        (FieldType.TEXT, "str", "Text"),
        (FieldType.BIG_INTEGER, "int", "BigInteger"),
        (FieldType.DATETIME, "datetime", "DateTimeUTC(timezone=True)"),
        (FieldType.JSON, "dict[str, object]", "JSON"),
        (FieldType.UUID, "UUID", "GUID"),
        (FieldType.BINARY, "bytes", "LargeBinary"),
    ],
)
def test_each_type_maps_to_its_python_and_column_types(
    kind: FieldType, annotation: str, column: str
) -> None:
    line, _ = _line(EntityField("value", kind))

    assert line == f"value: Mapped[{annotation}] = mapped_column({column})\n"


def test_an_enum_is_stored_by_its_class() -> None:
    line, imports = _line(EntityField("status", FieldType.ENUM, enum_class="http.HTTPStatus"))

    assert line == "status: Mapped[HTTPStatus] = mapped_column(Enum(HTTPStatus))\n"
    assert "from http import HTTPStatus" in imports
