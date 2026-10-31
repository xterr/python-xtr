"""The fields of a class, read from the JSON schema of the adapter the normalizer writes it with."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.fixtures.described import Account, Empty, Shipment
from tests.fixtures.hierarchies import Event, Mailbox, Notice, Reminder
from xtr_serializer.command._schema_fields import FieldRow, field_rows, type_name_of
from xtr_serializer.normalizer._adapter_cache import Adapter, build_adapter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic import TypeAdapter
    from pydantic.json_schema import JsonSchemaMode


def _writer(type_: object) -> TypeAdapter[object]:
    adapter = build_adapter(type_)
    assert isinstance(adapter, Adapter)
    return adapter.writer


@pytest.mark.parametrize("mode", ["validation", "serialization"])
def test_a_dataclass_field_is_written_under_its_own_name(mode: JsonSchemaMode) -> None:
    rows = field_rows(_writer(Shipment), mode)

    assert rows == [
        FieldRow("reference", "reference", "string", "yes", ""),
        FieldRow("weight", "weight", "number", "yes", ""),
        FieldRow("sent_at", "sent_at", "string (date-time) | null", "no", "null"),
        FieldRow("tags", "tags", "array[string]", "no", ""),
        FieldRow("kind", "kind", '"box" | "letter"', "no", '"box"'),
    ]


def test_a_model_reads_each_field_under_its_alias() -> None:
    rows = field_rows(_writer(Account), "validation")

    assert rows == [
        FieldRow("owner_name", "ownerName", "string", "yes", ""),
        FieldRow("balance", "balanceIn", "integer", "no", "0"),
        FieldRow("labels", "labels", "object[integer]", "no", ""),
    ]


def test_a_model_writes_each_field_under_its_alias() -> None:
    rows = field_rows(_writer(Account), "serialization")

    assert [(row.name, row.serialized_name) for row in rows or ()] == [
        ("owner_name", "ownerName"),
        ("balance", "balanceOut"),
        ("labels", "labels"),
    ]


def test_a_class_with_no_field_has_no_row() -> None:
    assert field_rows(_writer(Empty), "validation") == []


def test_what_is_not_written_as_an_object_has_no_fields() -> None:
    assert field_rows(_writer(int), "validation") is None


def test_a_class_of_a_hierarchy_is_read_from_its_own_member_of_the_union() -> None:
    rows = field_rows(_writer(Notice), "validation", member=1)

    assert rows == [
        FieldRow("title", "title", "string", "yes", ""),
        FieldRow("due", "due", "string (date-time)", "yes", ""),
    ]


def test_a_class_of_a_hierarchy_alone_in_it_is_read_as_the_union_itself() -> None:
    rows = field_rows(_writer(Reminder), "validation", member=0)

    assert [row.name for row in rows or ()] == ["title", "due"]


def test_a_field_declaring_a_hierarchy_takes_each_named_class() -> None:
    rows = field_rows(_writer(Mailbox), "serialization")

    assert rows is not None
    assert rows[0] == FieldRow(
        "latest", "latest", "Event | Delivery | Bounce | Complaint | Batch", "yes", ""
    )
    assert rows[1].type_name == "array[Bounce | Complaint]"


def test_the_base_of_a_hierarchy_is_its_first_member() -> None:
    rows = field_rows(_writer(Event), "validation", member=0)

    assert rows == [FieldRow("name", "name", "string", "yes", "")]


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({}, "any"),
        ({"const": "a"}, '"a"'),
        ({"type": ["string", "null"]}, "string | null"),
        ({"type": "array"}, "array"),
        (
            {"type": "array", "prefixItems": [{"type": "string"}, {"type": "integer"}]},
            "array[string, integer]",
        ),
        ({"type": "object"}, "object"),
        ({"type": "object", "additionalProperties": True}, "object"),
        ({"type": "object", "title": "Point"}, "Point"),
        ({"$ref": "#/$defs/Gone"}, "Gone"),
    ],
)
def test_a_type_is_named_from_its_schema(schema: Mapping[str, object], expected: str) -> None:
    assert type_name_of(schema, {}) == expected


def test_a_type_nested_too_deep_is_cut_short() -> None:
    schema: dict[str, object] = {"type": "string"}
    for _ in range(12):
        schema = {"type": "array", "items": schema}

    assert type_name_of(schema, {}).endswith("array[...]]]]]]]]]")
