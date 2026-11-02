"""The keys a class's fields are known by before pydantic builds a schema for it."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import AliasPath, BaseModel, Field

from xtr_serializer.mapping._field_names import field_names_of


@dataclass
class Plain:
    first: int
    second: str


class Model(BaseModel):
    plain: int
    aliased: int = Field(alias="read_as")
    written: int = Field(serialization_alias="written_as")
    pathed: int = Field(validation_alias=AliasPath("deep", 0))


def test_a_dataclass_is_known_by_its_field_names() -> None:
    assert field_names_of(Plain) == {"first", "second"}


def test_a_model_is_known_by_its_field_names_and_the_aliases_that_are_names() -> None:
    assert field_names_of(Model) == {
        "plain",
        "aliased",
        "read_as",
        "written",
        "written_as",
        "pathed",
    }


def test_another_class_has_no_fields() -> None:
    assert field_names_of(int) == frozenset()
