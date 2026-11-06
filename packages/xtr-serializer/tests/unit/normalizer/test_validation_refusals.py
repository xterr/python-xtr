"""pydantic's errors become this package's, located, with extra fields grouped per object."""

from __future__ import annotations

from typing import ClassVar, NamedTuple, final

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import ErrorDetails
from typing_extensions import override

from xtr_serializer.exception import ExtraAttributesError, NotNormalizableValueError
from xtr_serializer.normalizer._validation_refusals import _ABSENT, _KeyIndexes, refusals_of

PLANTED_VALUE = "s3cr3t-t0ken-4f9a"


@final
class Lazy:
    """An object holding ``method`` behind a property, which counts its reads."""

    def __init__(self) -> None:
        self.reads: int = 0

    @property
    def method(self) -> object:
        self.reads += 1
        return {"store": 1}


@final
class Slotted:
    """An object holding ``method`` in a slot."""

    __slots__: ClassVar[tuple[str, ...]] = ("method",)

    method: object

    def __init__(self, *method: object) -> None:
        if method:
            [self.method] = method


class Pair(NamedTuple):
    """A tuple subclass whose items are read by index."""

    first: object
    second: object


class Lines(list[object]):
    """A list subclass whose length raises."""

    @override
    def __len__(self) -> int:
        raise RuntimeError(PLANTED_VALUE)


class Key:
    """A key with the hash of ``"price"``, which counts how often it is compared."""

    def __init__(self) -> None:
        self.comparisons: int = 0

    @override
    def __hash__(self) -> int:
        return hash("price")

    @override
    def __eq__(self, other: object) -> bool:
        self.comparisons += 1
        return False


class Disguised(tuple[object, ...]):
    """A tuple claiming to be a list, as a class may by overriding ``__class__``."""

    __slots__: ClassVar[tuple[str, ...]] = ()

    @property
    @override
    def __class__(self) -> type[object]:  # pyright: ignore[reportIncompatibleMethodOverride] - the disguise is the point
        return list


class Renaming(type):
    """A metaclass computing the name of its classes, as code the data carries may."""

    @property
    @override
    def __name__(cls) -> str:  # pyright: ignore[reportIncompatibleVariableOverride] - the trap is the point
        raise RuntimeError(PLANTED_VALUE)


class Renamed(metaclass=Renaming):
    """A class whose name its metaclass computes."""


class Line(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid", strict=True)

    price: int


class Basket(BaseModel):
    lines: list[Line]


def details_of(data: object) -> ValidationError:
    with pytest.raises(ValidationError) as raised:
        _ = Basket.model_validate(data)
    return raised.value


def test_a_value_that_does_not_fit_keeps_its_path_type_and_message() -> None:
    data = {"lines": [{"price": "1"}]}
    error = details_of(data)

    [refusal] = refusals_of(error.errors(), data, plain=True)

    assert type(refusal) is NotNormalizableValueError
    assert (refusal.path, refusal.error_type, refusal.current_type) == (
        "lines[0].price",
        "int_type",
        "str",
    )
    assert refusal.message == "Input should be a valid integer"


def test_the_type_of_a_refused_value_is_named_without_running_its_code() -> None:
    renamed = Renamed()
    detail = ErrorDetails(
        type="string_type", loc=("x",), msg="Input should be a valid string", input=renamed
    )

    [refusal] = refusals_of([detail], {"x": renamed}, plain=False)

    assert refusal.current_type == "Renamed"


def test_the_extra_fields_of_one_object_are_one_error() -> None:
    data = {"lines": [{"price": 1, "a": 0, "b": 0}, {"price": 1, "c": 0}]}
    error = details_of(data)

    refusals = refusals_of(error.errors(), data, plain=True)

    assert [
        (refusal.path, refusal.extra_attributes)
        for refusal in refusals
        if isinstance(refusal, ExtraAttributesError)
    ] == [("lines[0]", ("a", "b")), ("lines[1]", ("c",))]
    assert len(refusals) == 2


@pytest.mark.parametrize(
    "error_type",
    [
        "union_tag_invalid",
        "bytes_invalid_encoding",
        "get_attribute_error",
        "iteration_error",
        "mapping_type",
        "datetime_object_invalid",
        "timezone_offset",
        "zoneinfo_str",
        "byte_size_unit",
        "import_error",
    ],
)
def test_a_message_pydantic_builds_from_the_data_is_replaced(error_type: str) -> None:
    detail = ErrorDetails(
        type=error_type, loc=("x",), msg=f"refused {PLANTED_VALUE}", input=PLANTED_VALUE
    )

    [refusal] = refusals_of([detail], {"x": PLANTED_VALUE}, plain=True)

    assert PLANTED_VALUE not in refusal.message
    assert (refusal.path, refusal.error_type) == ("x", error_type)


@pytest.mark.parametrize(
    ("error_type", "message"),
    [
        ("value_error", "Value error, end must follow start"),
        ("assertion_error", "Assertion failed, end must follow start"),
        ("slot_order", "end must follow start"),
    ],
    ids=["value-error", "assertion", "custom-error"],
)
def test_the_words_of_a_validator_are_passed_on(error_type: str, message: str) -> None:
    detail = ErrorDetails(type=error_type, loc=("end",), msg=message, input=1)

    [refusal] = refusals_of([detail], {"end": 1}, plain=True)

    assert (refusal.path, refusal.error_type, refusal.message) == ("end", error_type, message)


def string_error_at(*loc: str | int) -> ErrorDetails:
    return ErrorDetails(type="string_type", loc=loc, msg="Input should be a valid string", input=1)


def test_an_attribute_behind_a_property_is_located_but_not_read() -> None:
    data = Lazy()

    [refusal] = refusals_of([string_error_at("method", "Pickup", "store")], data, plain=False)

    assert refusal.path == "method"
    assert data.reads == 0


def test_an_attribute_in_a_slot_is_walked_through() -> None:
    data = Slotted({"store": 1})

    [refusal] = refusals_of([string_error_at("method", "Pickup", "store")], data, plain=False)

    assert refusal.path == "method.store"


def test_a_slot_never_set_holds_no_step() -> None:
    [refusal] = refusals_of([string_error_at("method")], Slotted(), plain=False)

    assert refusal.path is None


@pytest.mark.parametrize(
    "data",
    [Pair("a", {"store": 1}), Lines(["a", {"store": 1}]), Disguised(("a", {"store": 1}))],
    ids=["tuple-subclass", "list-subclass", "tuple-claiming-to-be-a-list"],
)
def test_a_sequence_subclass_is_indexed_as_the_built_in(data: object) -> None:
    [refusal] = refusals_of([string_error_at(1, "store")], data, plain=False)

    assert refusal.path == "[1].store"


def test_a_field_missing_behind_a_property_ends_the_path_at_the_property() -> None:
    detail = ErrorDetails(type="missing", loc=("method", "store"), msg="Field required", input={})

    [refusal] = refusals_of([detail], Lazy(), plain=False)

    assert refusal.path == "method"


def test_a_value_with_no_fields_holds_no_step() -> None:
    [refusal] = refusals_of([string_error_at("upper")], "text", plain=False)

    assert refusal.path is None


def test_an_index_into_a_value_that_is_no_sequence_holds_no_step() -> None:
    [refusal] = refusals_of([string_error_at(0)], Lazy(), plain=False)

    assert refusal.path is None


def test_a_key_is_found_without_comparing_the_keys_of_the_data() -> None:
    key = Key()
    data = {"items": {key: 1, "price": {"store": 1}}}
    key.comparisons = 0  # building the dict compared the colliding keys once

    [refusal] = refusals_of([string_error_at("items", "price", "store")], data, plain=False)

    assert refusal.path == "items.price.store"
    assert key.comparisons == 0


MANY = 20_000
KEYS: list[str | int] = [f"k{index}" for index in range(MANY)]


@pytest.mark.parametrize(
    ("data", "steps", "plain", "last_path"),
    [
        (dict.fromkeys(KEYS, 0), KEYS, True, "k19999"),
        (dict.fromkeys(KEYS, 0), KEYS, False, "k19999"),
        (Lines([0] * MANY), list(range(MANY)), False, "[19999]"),
    ],
    ids=["plain-mapping", "mapping", "list-subclass"],
)
def test_the_errors_of_a_large_container_are_located(
    data: object, steps: list[str | int], plain: bool, last_path: str
) -> None:
    details = [string_error_at(step) for step in steps]

    refusals = refusals_of(details, data, plain=plain)

    assert (len(refusals), refusals[-1].path) == (MANY, last_path)


def test_the_keys_of_a_mapping_are_indexed_on_the_first_lookup_only() -> None:
    """Later lookups read the index, not the mapping: locating every error reads it once."""
    mapping: dict[object, object] = {"a": 1}
    indexes = _KeyIndexes()
    assert indexes.item_at(mapping, "a") == 1
    mapping["b"] = 2

    assert indexes.item_at(mapping, "b") is _ABSENT
    assert indexes.item_at(mapping, "a") == 1
