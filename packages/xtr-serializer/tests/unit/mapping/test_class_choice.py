"""A class read where its hierarchy is declared, from the data with its name taken out."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import ClassVar, cast

import pytest
from pydantic import (
    AliasChoices,
    AliasPath,
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    model_validator,
)
from pydantic_core import SchemaValidator, core_schema

from tests.fixtures.hierarchies import Delivery, Event
from xtr_serializer import (
    FROM_ATTRIBUTES,
    STRICT,
    MappingError,
    NotNormalizableValueError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)
from xtr_serializer.mapping._class_choice import class_choice

NORMALIZER = PydanticNormalizer()
AT = datetime(2026, 10, 30, 9, 30, tzinfo=UTC)


@discriminator_map()
class Base(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")


@discriminator_name("measured")
@discriminator_map()
@dataclass(frozen=True)
class Measured:
    ratio: float


def test_a_strict_class_reads_its_fields_from_json_as_json() -> None:
    data = {"$type": "delivery", "name": "d", "recipient": "r", "at": "2026-10-30T09:30:00Z"}

    assert NORMALIZER.denormalize(data, Event) == Delivery("d", "r", AT)


def test_a_class_reads_python_data_without_the_class_name() -> None:
    data = {"$type": "delivery", "name": "d", "recipient": "r", "at": AT}
    # A strict dataclass takes an instance only from Python, not its fields.
    context = {FROM_ATTRIBUTES: True, STRICT: False}

    read = NORMALIZER.denormalize(data, Event, context=context)

    assert read == Delivery("d", "r", AT)


def test_a_number_json_has_no_form_for_is_refused_by_the_class_reading_it() -> None:
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.denormalize({"$type": "measured", "ratio": float("nan")}, Measured)

    assert (caught.value.path, caught.value.error_type) == ("ratio", "finite_number")


def test_the_json_schema_of_a_class_is_its_own() -> None:
    definitions = cast("dict[str, dict[str, object]]", TypeAdapter(Measured).json_schema()["$defs"])

    assert {"ratio": {"title": "Ratio", "type": "number"}} in [
        definition.get("properties") for definition in definitions.values()
    ]


def test_a_schema_of_no_class_has_no_fields_to_check_and_reads_as_it_does() -> None:
    own = core_schema.int_schema(ref="own")

    choice = class_choice(own, int, "$type", "choice")

    assert SchemaValidator(core_schema.definitions_schema(choice, [own])).validate_python(3) == 3


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

    read = NORMALIZER.denormalize({"$type": "validated", "value": 1}, Root)

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


def test_a_field_of_a_model_checking_its_data_first_is_checked_too() -> None:
    with pytest.raises(MappingError, match=r"field 'kind'"):

        class Aliased(Base):  # pyright: ignore[reportUnusedClass] - defining it is what raises
            kind: str = Field(serialization_alias="$type")

            @model_validator(mode="before")
            @classmethod
            def unchanged(cls, data: object) -> object:
                return data


def test_an_extra_field_written_under_the_key_is_refused() -> None:
    @discriminator_map()
    class Root(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    @discriminator_name("open")
    class Open(Root):
        pass

    with pytest.raises(NotNormalizableValueError, match="extra field"):
        _ = NORMALIZER.normalize(Open.model_construct(None, **{"$type": "forged"}))


def test_an_extra_field_is_kept_and_the_key_is_not() -> None:
    @discriminator_map()
    class Root(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(extra="allow")

    @discriminator_name("extended")
    class Extended(Root):
        pass

    read = NORMALIZER.denormalize({"$type": "extended", "note": "kept"}, Root)

    assert (type(read), read.model_extra) == (Extended, {"note": "kept"})
