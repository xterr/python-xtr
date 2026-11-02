"""A class of a hierarchy registers the name it is written under, unambiguously."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from types import GenericAlias, new_class
from typing import TYPE_CHECKING, Generic, TypeVar, cast

import pytest
from pydantic import BaseModel, Field

from tests.fixtures.hierarchies import Delivery, Event, Notice
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


def hierarchy() -> type[object]:
    @discriminator_map()
    @dataclass(frozen=True)
    class Base:
        pass

    return Base


def test_the_class_is_returned_as_it_is() -> None:
    base = hierarchy()

    assert discriminator_name("base")(base) is base


def test_a_name_must_be_some_text() -> None:
    with pytest.raises(MappingError, match="name"):
        _ = discriminator_name("")(hierarchy())


def test_a_class_outside_every_hierarchy_is_refused() -> None:
    @dataclass
    class Loose:
        pass

    with pytest.raises(MappingError, match="no hierarchy"):
        _ = discriminator_name("loose")(Loose)


def test_a_class_in_two_hierarchies_is_refused() -> None:
    both = new_class("Both", (hierarchy(), hierarchy()))

    with pytest.raises(MappingError, match="two hierarchies"):
        _ = discriminator_name("both")(both)


_Item = TypeVar("_Item")


@discriminator_map()
@dataclass(frozen=True)
class _Root:
    pass


@dataclass(frozen=True)
class _Box(_Root, Generic[_Item]):
    content: _Item


def test_a_generic_class_is_refused() -> None:
    # pydantic reads ``_Box[int]`` by its fields, never asking the hierarchy for the classes.
    with pytest.raises(MappingError, match="generic"):
        _ = discriminator_name("box")(_Box)


def test_a_class_under_a_generic_dataclass_is_refused() -> None:
    # A field declaring ``_Box[int]`` would read it alone, never asking for the classes under it.
    @dataclass(frozen=True)
    class IntBox(_Box[int]):
        pass

    with pytest.raises(MappingError, match=r"generic '_Box'"):
        _ = discriminator_name("int_box")(IntBox)


@dataclass(frozen=True)
class _Envelope(Generic[_Item]):
    body: _Item


def test_a_hierarchy_based_on_a_generic_dataclass_names_its_classes() -> None:
    # ``_Envelope[str]`` is above the hierarchy: no field declaring a class of it reads it alone.
    @discriminator_name("message")
    @discriminator_map()
    @dataclass(frozen=True)
    class Message(_Envelope[str]):
        pass

    @discriminator_name("reply")
    @dataclass(frozen=True)
    class Reply(Message):
        to: str

    read = PydanticNormalizer().denormalize({"$type": "reply", "body": "b", "to": "t"}, Message)

    assert read == Reply("b", "t")


def test_a_class_under_a_generic_model_is_named() -> None:
    @discriminator_map()
    class Root(BaseModel):
        pass

    class Box(Root, Generic[_Item]):
        content: _Item

    @discriminator_name("int_box")
    class IntBox(Box[int]):
        pass

    assert PydanticNormalizer().denormalize({"$type": "int_box", "content": 1}, Box[int]) == IntBox(
        content=1
    )


def test_a_name_taken_in_the_hierarchy_is_refused() -> None:
    base = hierarchy()
    _ = discriminator_name("one")(base)

    with pytest.raises(MappingError, match="'one'"):
        _ = discriminator_name("one")(type("Sub", (base,), {}))


def test_a_name_another_hierarchy_uses_is_free() -> None:
    _ = discriminator_name("event")(hierarchy())


def test_a_class_is_registered_under_one_name_only() -> None:
    base = hierarchy()
    _ = discriminator_name("one")(base)

    with pytest.raises(MappingError, match="already"):
        _ = discriminator_name("two")(base)
    with pytest.raises(MappingError, match="already"):
        _ = discriminator_name("one")(base)


def test_a_field_named_as_the_key_is_refused() -> None:
    @discriminator_map(type_property="kind")
    @dataclass
    class Base:
        pass

    @dataclass
    class Sub(Base):
        kind: str

    with pytest.raises(MappingError, match="'kind'"):
        _ = discriminator_name("sub")(Sub)


def test_a_model_field_aliased_as_the_key_is_refused_as_the_model_is_built() -> None:
    @discriminator_map()
    class Base(BaseModel):
        pass

    with pytest.raises(MappingError, match=r"'\$type'"):

        class Aliased(Base):  # pyright: ignore[reportUnusedClass] - defining it is what raises
            kind: str = Field(alias="$type")


def test_a_subclass_with_a_schema_hook_of_its_own_is_refused() -> None:
    def schema_of(_cls: type, source: type, handler: GetCoreSchemaHandler) -> CoreSchema:
        return handler(source)

    hooked = type(
        "Hooked", (hierarchy(),), {"__get_pydantic_core_schema__": classmethod(schema_of)}
    )

    with pytest.raises(MappingError, match="__get_pydantic_core_schema__"):
        _ = discriminator_name("hooked")(hooked)


def test_a_class_named_after_its_hierarchy_was_used_is_refused() -> None:
    base = hierarchy()
    one = discriminator_name("one")(type("One", (base,), {}))

    assert type(PydanticNormalizer().denormalize({"$type": "one"}, base)) is one

    with pytest.raises(MappingError, match="before"):
        _ = discriminator_name("late")(type("Late", (base,), {}))


def test_a_class_named_after_a_sibling_was_used_is_accepted() -> None:
    base = hierarchy()
    one = discriminator_name("one")(type("One", (base,), {}))
    _ = PydanticNormalizer().normalize(one())

    two = discriminator_name("two")(type("Two", (base,), {}))

    assert PydanticNormalizer().normalize(two()) == {"$type": "two"}


def test_a_model_holding_its_hierarchy_built_before_its_classes_are_named_is_refused() -> None:
    @discriminator_map()
    class Base(BaseModel):
        pass

    @discriminator_name("one")
    class One(Base):
        pass

    with pytest.raises(MappingError, match="before"):

        @discriminator_name("holder")
        class Holder(Base):
            inner: Base


def test_threads_registering_at_once_all_get_a_name() -> None:
    base = hierarchy()
    subclasses = [type(f"Sub{index}", (base,), {}) for index in range(64)]

    def register(index: int, sub: type[object]) -> type[object]:
        return discriminator_name(f"sub{index}")(sub)

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(register, range(64), subclasses))

    mapping = ClassDiscriminatorMapping.for_class(base)
    assert mapping is not None
    assert dict(mapping.types_mapping) == {
        f"sub{index}": sub for index, sub in enumerate(subclasses)
    }


def test_threads_registering_the_same_name_register_it_once() -> None:
    base = hierarchy()
    subclasses = [type(f"Sub{index}", (base,), {}) for index in range(32)]
    refused: list[MappingError] = []

    def register(sub: type[object]) -> None:
        try:
            _ = discriminator_name("same")(sub)
        except MappingError as error:
            refused.append(error)

    with ThreadPoolExecutor(max_workers=8) as pool:
        _ = list(pool.map(register, subclasses))

    assert len(refused) == 31


def test_the_fixtures_are_registered() -> None:
    mapping = ClassDiscriminatorMapping.for_class(Event)
    assert mapping is not None
    assert mapping.types_mapping["delivery"] is Delivery
    assert ClassDiscriminatorMapping.for_class(Notice) is not None


@pytest.mark.parametrize("value", [3, "Base", None], ids=["number", "text", "none"])
def test_what_is_no_class_is_refused(value: object) -> None:
    with pytest.raises(MappingError, match="no class"):
        _ = discriminator_name("named")(cast("type", value))


def test_a_class_named_after_its_hierarchy_was_refused_for_having_no_name_is_refused() -> None:
    base = hierarchy()
    normalizer = PydanticNormalizer()

    assert not normalizer.supports_denormalization([], GenericAlias(list, (base,)))
    with pytest.raises(MappingError, match="before"):
        _ = discriminator_name("late")(type("Late", (base,), {}))
    assert not normalizer.supports_denormalization([], GenericAlias(list, (base,)))
