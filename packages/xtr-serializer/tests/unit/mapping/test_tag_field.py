"""A class's schema reads the key its name is written under, and keeps nothing of it."""

from __future__ import annotations

from typing import ClassVar

import pytest
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, model_validator
from pydantic_core import core_schema

from xtr_serializer import (
    MappingError,
    NotNormalizableValueError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)
from xtr_serializer.mapping._tag_field import with_tag_field


@discriminator_map()
class Base(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")


def test_a_schema_that_is_no_class_cannot_carry_the_key() -> None:
    with pytest.raises(MappingError, match="'int' one"):
        _ = with_tag_field(core_schema.int_schema(), "$type")


def test_a_schema_made_already_is_left_as_it_is() -> None:
    @discriminator_name("checked")
    class Checked(Base):
        value: int

    schema = Checked.__pydantic_core_schema__

    assert with_tag_field(schema, "$type") is schema


def test_a_model_checking_itself_reads_the_key_inside_its_checks() -> None:
    seen: list[list[str]] = []

    @discriminator_map()
    class Root(BaseModel):
        pass

    @discriminator_name("validated")
    class Validated(Root):
        value: int

        @model_validator(mode="after")
        def remember(self) -> Validated:
            seen.append(sorted(vars(self)))
            return self

    read = PydanticNormalizer().denormalize({"$type": "validated", "value": 1}, Root)

    assert (read, seen[-1]) == (Validated(value=1), ["value"])


@pytest.mark.parametrize(
    "alias",
    [
        pytest.param(AliasPath("$type", 0), id="a path"),
        pytest.param(AliasChoices("kind", AliasPath("$type")), id="one of several"),
    ],
)
def test_a_field_read_from_the_key_is_refused(alias: AliasPath | AliasChoices) -> None:
    with pytest.raises(MappingError, match=r"field 'kind'"):

        class Aliased(Base):  # pyright: ignore[reportUnusedClass] - defining it is what raises
            kind: str = Field(validation_alias=alias)


def test_a_field_written_under_the_key_is_refused() -> None:
    with pytest.raises(MappingError, match=r"field 'kind'"):

        class Aliased(Base):  # pyright: ignore[reportUnusedClass] - defining it is what raises
            kind: str = Field(serialization_alias="$type")


def test_an_extra_field_written_under_the_key_is_refused() -> None:
    @discriminator_map()
    class Root(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    @discriminator_name("open")
    class Open(Root):
        pass

    with pytest.raises(NotNormalizableValueError, match="extra field"):
        _ = PydanticNormalizer().normalize(Open.model_construct(None, **{"$type": "forged"}))


def test_an_extra_field_is_kept_and_the_key_is_not() -> None:
    @discriminator_map()
    class Root(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    @discriminator_name("extended")
    class Extended(Root):
        pass

    read = PydanticNormalizer().denormalize({"$type": "extended", "note": "kept"}, Root)

    assert (type(read), read.model_extra) == (Extended, {"note": "kept"})
