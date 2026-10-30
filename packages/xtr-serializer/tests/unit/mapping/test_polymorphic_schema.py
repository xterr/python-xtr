"""Values of a class hierarchy written with their class's name, and read back as that class."""

from __future__ import annotations

from dataclasses import InitVar, dataclass
from datetime import UTC, datetime, timedelta, timezone
from enum import IntEnum
from typing import TYPE_CHECKING, Annotated, ClassVar, cast

import pytest
from pydantic import BaseModel, ConfigDict, Field, model_serializer, model_validator

from tests.fixtures.colliding_key import CollidingKey
from tests.fixtures.hierarchies import (
    Alert,
    Batch,
    Board,
    Bounce,
    Complaint,
    Delivery,
    Event,
    Failure,
    Hashless,
    Labels,
    Mailbox,
    Node,
    Stray,
    Timed,
    Unnamed,
    Weighed,
)
from xtr_serializer import (
    COLLECT_DENORMALIZATION_ERRORS,
    FROM_ATTRIBUTES,
    InvalidArgumentError,
    JsonEncoder,
    NotNormalizableValueError,
    PartialDenormalizationError,
    PydanticNormalizer,
    discriminator_map,
    discriminator_name,
)

if TYPE_CHECKING:
    from collections.abc import Callable

AT = datetime(2026, 10, 30, 9, 30, tzinfo=UTC)
NORMALIZER = PydanticNormalizer()
ENCODER = JsonEncoder()


def round_trip(value: object, type_: object | None = None) -> object:
    data = ENCODER.decode(ENCODER.encode(NORMALIZER.normalize(value), "json"), "json")
    return NORMALIZER.denormalize(data, type(value) if type_ is None else type_)


def written(value: object) -> dict[str, object]:
    return cast("dict[str, object]", NORMALIZER.normalize(value))


def refusal(data: object, type_: object) -> NotNormalizableValueError:
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.denormalize(data, type_)
    return caught.value


MAILBOX = Mailbox(
    latest=Batch(
        "batch",
        events=(Delivery("d", "ana@example.com", AT), Event("plain")),
        failures=[Bounce("b", "full", 552)],
    ),
    failures=[Bounce("b", "full", 552), Complaint("c", "spam", "rude")],
    by_id={"one": Delivery("d", "ion@example.com", AT), "two": Complaint("c", "spam")},
    maybe=Bounce("b", "gone", 550),
    pair=(Delivery("d", "x@example.com", AT), Complaint("c", "spam")),
)


def test_a_value_in_every_place_reads_back_as_its_exact_class() -> None:
    read = cast("Mailbox", round_trip(MAILBOX))

    assert read == MAILBOX
    assert type(cast("Batch", read.latest).events[0]) is Delivery
    assert type(read.by_id["two"]) is Complaint


def test_a_value_is_written_with_its_class_name_first() -> None:
    data = written(Mailbox(Event("e"), [], {}, None, MAILBOX.pair))

    assert data == {
        "latest": {"$type": "event", "name": "e"},
        "failures": [],
        "by_id": {},
        "maybe": None,
        "pair": [
            {
                "$type": "delivery",
                "name": "d",
                "recipient": "x@example.com",
                "at": "2026-10-30T09:30:00Z",
            },
            {"$type": "complaint", "name": "c", "reason": "spam", "feedback": None},
        ],
    }
    assert list(cast("dict[str, object]", data["latest"])) == ["$type", "name"]


def test_a_value_alone_is_written_with_its_class_name_and_read_as_its_base() -> None:
    data = written(Bounce("b", "full", 552))

    assert data == {"$type": "bounce", "name": "b", "reason": "full", "code": 552}
    assert NORMALIZER.denormalize(data, Event) == Bounce("b", "full", 552)
    assert type(NORMALIZER.denormalize(data, Failure)) is Bounce


def test_an_optional_value_reads_back_absent_or_as_its_class() -> None:
    for maybe in (None, Delivery("d", "x@example.com", AT)):
        read = cast("Mailbox", round_trip(Mailbox(Event("e"), [], {}, maybe, MAILBOX.pair)))

        assert read.maybe == maybe


def test_an_intermediate_class_takes_only_its_own_subclasses() -> None:
    data = {"$type": "delivery", "name": "d", "recipient": "x", "at": "2026-10-30T09:30:00Z"}

    error = refusal({**written(MAILBOX), "failures": [data]}, Mailbox)

    assert error.path == "failures[0]"
    assert error.error_type == "class_discriminator"
    assert type(NORMALIZER.denormalize(data, Event)) is Delivery


def test_alerts_take_only_alerts() -> None:
    data = {"$type": "reminder", "title": "pay", "due": "2026-10-30T09:30:00Z"}

    assert refusal(data, Alert).error_type == "class_discriminator"


@pytest.mark.parametrize(
    "tag",
    [
        pytest.param({"$type": "circle"}, id="another hierarchy's name"),
        pytest.param({"$type": "secret-token-value"}, id="an unknown name"),
        pytest.param({}, id="no name"),
        pytest.param({"$type": 7}, id="a number"),
        pytest.param({"$type": ["event"]}, id="a list"),
        pytest.param({"$type": None}, id="null"),
    ],
)
def test_a_forged_class_name_is_refused_without_being_quoted(tag: dict[str, object]) -> None:
    data = {**written(MAILBOX), "latest": {**tag, "name": "e"}}

    error = refusal(data, Mailbox)

    assert (error.path, error.error_type) == ("latest", "class_discriminator")
    assert "$type" in str(error)
    assert "circle" not in str(error)
    assert "secret" not in str(error)


def test_data_that_is_no_object_is_refused_where_the_class_name_is_read() -> None:
    assert refusal({"pinned": "notice", "alerts": []}, Board).path == "pinned"


def test_every_forged_name_is_reported_when_errors_are_collected() -> None:
    data = [{"$type": "circle", "name": "e"}, {"name": "e"}, {"$type": "event", "name": 1}]

    with pytest.raises(PartialDenormalizationError) as caught:
        _ = NORMALIZER.denormalize(
            data, list[Event], context={COLLECT_DENORMALIZATION_ERRORS: True}
        )

    assert [(error.path, error.error_type) for error in caught.value.errors] == [
        ("[0]", "class_discriminator"),
        ("[1]", "class_discriminator"),
        ("[2].name", "string_type"),
    ]


def test_an_error_inside_a_value_is_located_past_its_class_name() -> None:
    # The name of the class is the name of one of its fields: the path still names the field.
    @discriminator_map()
    @dataclass(frozen=True)
    class Signal:
        pass

    @discriminator_name("code")
    @dataclass(frozen=True)
    class Coded(Signal):
        code: int
        name: str

    assert refusal({"$type": "code", "code": "x", "name": "n"}, Signal).path == "code"
    assert refusal({"$type": "code", "code": 1, "name": 2}, Signal).path == "name"
    assert refusal([{"$type": "code", "code": 1, "name": 2}], list[Signal]).path == "[0].name"


def test_a_value_of_a_subclass_with_no_name_is_refused_naming_its_class() -> None:
    value = Mailbox(Unnamed("u", "x", AT), [], {}, None, MAILBOX.pair)

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(value)

    assert caught.value.current_type == "Unnamed"
    assert caught.value.error_type == "unnamed_class"
    assert "@discriminator_name" in str(caught.value)


def test_a_value_outside_the_declared_class_is_refused() -> None:
    delivery = cast("Failure", cast("object", Delivery("d", "x", AT)))
    value = Mailbox(Event("e"), [delivery], {}, None, MAILBOX.pair)

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(value)

    assert (caught.value.current_type, caught.value.error_type) == ("Delivery", "unexpected_class")


def test_an_alias_written_where_the_class_name_goes_is_refused_when_the_schema_is_built() -> None:
    @discriminator_map()
    @dataclass(frozen=True)
    class Tagged:
        pass

    @discriminator_name("labelled")
    @dataclass(frozen=True)
    class Labelled(Tagged):
        label: Annotated[str, Field(alias="$type")]

    with pytest.raises(InvalidArgumentError, match=r"'\$type'"):
        _ = NORMALIZER.normalize(Labelled("x"))


def test_a_dataclass_of_a_hierarchy_runs_its_own_checks_on_reading() -> None:
    data = {"$type": "complaint", "name": "c", "reason": "spam", "feedback": ""}

    assert refusal(data, Event).error_type == "value_error"


def test_a_dataclass_with_init_only_fields_reads_them_and_not_the_class_name() -> None:
    seeds: list[int] = []

    @discriminator_name("initialised")
    @discriminator_map()
    @dataclass(frozen=True)
    class Initialised:
        count: int
        seed: InitVar[int] = 0

        def __post_init__(self, seed: int) -> None:
            seeds.append(seed)

    read = NORMALIZER.denormalize({"$type": "initialised", "count": 1, "seed": 7}, Initialised)

    assert (read, seeds[-1]) == (Initialised(1), 7)
    assert NORMALIZER.normalize(read) == {"$type": "initialised", "count": 1}


def test_a_hierarchy_with_no_named_class_has_no_schema() -> None:
    @discriminator_map()
    @dataclass(frozen=True)
    class Empty:
        pass

    assert not NORMALIZER.supports_denormalization({}, Empty)
    with pytest.raises(InvalidArgumentError, match="no class"):
        _ = NORMALIZER.denormalize({}, Empty)


def test_a_refusal_inside_a_value_inside_a_value_keeps_its_words() -> None:
    value = Batch("b", events=(Batch("inner", events=(Unnamed("u", "x", AT),)),))

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(value)

    assert (caught.value.current_type, caught.value.error_type) == ("Unnamed", "unnamed_class")


def test_a_zoned_datetime_refused_inside_a_value_keeps_its_words() -> None:
    value = Node(Timed(at=datetime(2026, 10, 30, tzinfo=timezone(timedelta(hours=2)))))

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(value)

    assert caught.value.error_type == "zoned_datetime"


def chain(depth: int, last: Node) -> Node:
    value = last
    for _ in range(depth):
        value = Node(value)
    return value


@pytest.mark.parametrize(
    "value_of",
    [
        lambda: chain(250, Node()),
        lambda: chain(40, Stray()),
        lambda: chain(40, Weighed(weight=cast("int", cast("object", "heavy")))),
    ],
    ids=["deeper-than-reading-goes", "refused-deep-inside", "mistyped-deep-inside"],
)
def test_a_value_refused_deep_inside_a_chain_of_values_is_refused_at_once(
    value_of: Callable[[], Node],
) -> None:
    # pydantic 2.12 tries a refused member of a union again, once per union holding it.
    with pytest.raises(NotNormalizableValueError):
        _ = NORMALIZER.normalize(value_of())


def test_a_class_refusing_to_be_hashed_is_refused_without_running_its_code() -> None:
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(Node(Hashless()))

    assert (caught.value.current_type, caught.value.error_type) == ("Hashless", "unnamed_class")


def test_a_mapping_holding_the_key_is_located_by_its_own_keys() -> None:
    error = refusal({"tags": {"$type": "k", "k": 5}}, Labels)

    assert error.path == "tags.k"


def test_a_dataclass_with_a_validator_before_its_fields_reads_them_without_the_class_name() -> None:
    seen: list[object] = []

    @discriminator_map()
    @dataclass(frozen=True)
    class Checked:
        count: int = 0

    @discriminator_name("checked_more")
    @dataclass(frozen=True)
    class CheckedMore(Checked):
        @model_validator(mode="before")
        @classmethod
        def remember(cls, data: object) -> object:
            seen.append(data)
            return data

    read = NORMALIZER.denormalize({"$type": "checked_more", "count": 1}, Checked)

    assert seen == [{"count": 1}]
    assert read == CheckedMore(1)


def test_a_class_written_as_no_object_is_refused() -> None:
    @discriminator_map()
    class Text(BaseModel):
        model_config: ClassVar[ConfigDict] = ConfigDict(defer_build=True)

    @discriminator_name("line")
    class Line(Text):
        @model_serializer
        def as_text(self) -> str:
            return "a line naming $type"

    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(Line())

    assert caught.value.error_type == "class_discriminator_object"


def test_the_class_name_is_read_and_taken_out_without_running_code_the_data_carries() -> None:
    @discriminator_map()
    class Signal(BaseModel):
        count: int = 0

    @discriminator_name("ping")
    class Ping(Signal):
        pass

    key = CollidingKey("$type", "the key's own words")
    data = {key: 1, "$type": "ping", "count": 1}
    key.armed = True

    read = NORMALIZER.denormalize(data, Signal, context={FROM_ATTRIBUTES: True})

    assert read == Ping(count=1)


@dataclass(frozen=True)
class Either:
    item: Event | int


@dataclass(frozen=True)
class Only:
    item: Event


def test_a_value_of_a_subclass_with_no_name_in_a_union_is_refused_as_where_it_is_alone() -> None:
    errors: list[NotNormalizableValueError] = []
    for value in (Either(Unnamed("u", "x", AT)), Only(Unnamed("u", "x", AT))):
        with pytest.raises(NotNormalizableValueError) as caught:
            _ = NORMALIZER.normalize(value)
        errors.append(caught.value)

    assert str(errors[0]) == str(errors[1])
    assert (errors[0].error_type, errors[0].current_type) == ("unnamed_class", "Unnamed")


def test_a_union_of_a_hierarchy_still_writes_what_is_not_of_it() -> None:
    assert NORMALIZER.normalize(Either(7)) == {"item": 7}
    assert round_trip(Either(Bounce("b", "full", 552))) == Either(Bounce("b", "full", 552))


class Level(IntEnum):
    ONE = 1


@discriminator_map()
@dataclass(frozen=True)
class Counted:
    count: int


@discriminator_name("counted")
@dataclass(frozen=True)
class CountedMore(Counted):
    pass


@dataclass(frozen=True)
class Counts:
    items: list[Counted]


@pytest.mark.parametrize("count", [True, Level.ONE], ids=["bool", "int-enum"])
def test_a_subclass_of_int_inside_a_value_is_refused_where_it_sits(count: int) -> None:
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(Counts([CountedMore(count)]))

    assert (caught.value.path, caught.value.error_type) == ("items[0].count", "not_exact")


def test_a_subclass_of_int_deep_inside_a_chain_of_values_is_refused_where_it_sits() -> None:
    with pytest.raises(NotNormalizableValueError) as caught:
        _ = NORMALIZER.normalize(chain(40, Weighed(weight=True)))

    assert (caught.value.path, caught.value.error_type) == ("nxt." * 40 + "weight", "not_exact")
