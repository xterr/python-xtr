"""A base class declares the key its hierarchy writes class names under."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Generic, TypeVar, cast

import pytest
from pydantic import BaseModel, RootModel, ValidationError

from tests.fixtures.hierarchies import Event, Notice
from xtr_serializer import (
    ClassDiscriminatorMapping,
    MappingError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)

if TYPE_CHECKING:
    from pydantic import GetCoreSchemaHandler
    from pydantic_core import CoreSchema


def test_the_class_is_returned_as_it_is() -> None:
    @dataclass
    class Base:
        pass

    assert discriminator_map()(Base) is Base


def test_the_key_defaults_to_one_no_field_can_be_named() -> None:
    @discriminator_map()
    @dataclass
    class Base:
        pass

    assert ClassDiscriminatorMapping.for_class(Base) == ClassDiscriminatorMapping("$type", {})


def test_the_key_can_be_chosen() -> None:
    @discriminator_name("named")
    @discriminator_map(type_property="kind")
    @dataclass(frozen=True)
    class Base:
        value: int

    assert PydanticNormalizer().normalize(Base(1)) == {"kind": "named", "value": 1}


def test_an_empty_key_is_refused() -> None:
    @dataclass
    class Base:
        pass

    with pytest.raises(MappingError, match="type_property"):
        _ = discriminator_map(type_property="")(Base)


def test_a_key_a_field_of_the_base_uses_is_refused() -> None:
    @dataclass
    class Base:
        kind: str

    with pytest.raises(MappingError, match="'kind'"):
        _ = discriminator_map(type_property="kind")(Base)


@pytest.mark.parametrize("base", [Event, Notice], ids=["root", "model root"])
def test_a_class_already_in_a_hierarchy_cannot_start_another(base: type) -> None:
    sub = type("Sub", (base,), {})

    with pytest.raises(MappingError, match="already in the hierarchy"):
        _ = discriminator_map()(sub)
    with pytest.raises(MappingError, match="already in the hierarchy"):
        _ = discriminator_map()(base)


def test_a_class_with_a_schema_hook_of_its_own_is_refused() -> None:
    @dataclass
    class Hooked:
        @classmethod
        def __get_pydantic_core_schema__(
            cls, source: type, handler: GetCoreSchemaHandler
        ) -> CoreSchema:
            return handler(source)

    with pytest.raises(MappingError, match="__get_pydantic_core_schema__"):
        _ = discriminator_map()(Hooked)


def test_a_root_model_is_refused() -> None:
    class Root(RootModel[int]):
        pass

    with pytest.raises(MappingError, match="root model"):
        _ = discriminator_map()(Root)


def test_a_class_pydantic_has_no_schema_for_is_refused() -> None:
    class Plain:
        pass

    with pytest.raises(MappingError, match="no dataclass or model"):
        _ = discriminator_map()(Plain)


_Item = TypeVar("_Item")


@dataclass
class _GenericBase(Generic[_Item]):
    value: _Item


class _GenericModel(BaseModel, Generic[_Item]):
    value: _Item


@pytest.mark.parametrize("base", [_GenericBase, _GenericModel], ids=["dataclass", "model"])
def test_a_generic_class_is_refused(base: type) -> None:
    # pydantic reads ``Base[int]`` by its fields, never asking the hierarchy for the classes.
    with pytest.raises(MappingError, match="generic"):
        _ = discriminator_map()(base)


def test_a_model_base_built_before_it_is_declared_writes_its_name() -> None:
    @discriminator_name("base")
    @discriminator_map()
    class Base(BaseModel):
        value: int

    assert PydanticNormalizer().normalize(Base(value=1)) == {"$type": "base", "value": 1}


def test_a_model_validated_by_itself_is_read_by_pydantic_alone() -> None:
    @discriminator_name("base")
    @discriminator_map()
    class Base(BaseModel):
        value: int

    assert Base.model_validate({"value": 1}, extra="forbid") == Base(value=1)
    with pytest.raises(ValidationError):
        _ = Base.model_validate({"$type": "base", "value": 1}, extra="forbid")


@pytest.mark.parametrize("value", [3, "Base", None], ids=["number", "text", "none"])
def test_what_is_no_class_is_refused(value: object) -> None:
    with pytest.raises(MappingError, match="no class"):
        _ = discriminator_map()(cast("type", value))
