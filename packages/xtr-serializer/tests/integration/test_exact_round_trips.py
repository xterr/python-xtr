"""Generated types and values written to JSON and read back equal, with the exact type of each part.

A fixed seed draws nested dataclasses and models whose fields mix the values JSON has no form for
and the classes of hierarchies, declared by their base or a class in between; each value goes
through the normalizer and the JSON encoder and back. The same seed draws the same cases on every
run, so a failure is reproduced by running the test again.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Iterator
from dataclasses import dataclass, make_dataclass
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from enum import Enum, IntEnum
from itertools import count
from random import Random
from types import GenericAlias, NoneType
from typing import Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, create_model

from tests.fixtures.hierarchies import (
    Alert,
    Batch,
    Bounce,
    Circle,
    Complaint,
    Delivery,
    Event,
    Failure,
    Notice,
    Outage,
    Reminder,
    Shape,
    Square,
)
from xtr_serializer import JsonEncoder, PydanticNormalizer, ZonedDateTime
from xtr_serializer.normalizer import _adapter_cache

SEED: Final = 20261030
TYPES: Final = 250
VALUES_PER_TYPE: Final = 4
MAX_DEPTH: Final = 3

ZONES: Final = tuple(
    ZoneInfo(key)
    for key in ("Europe/Bucharest", "America/New_York", "Australia/Lord_Howe", "Asia/Kolkata")
)
# Hours a zone repeats as its clocks go back, from their first instant in UTC.
REPEATED_HOURS: Final = (
    (ZoneInfo("Europe/Bucharest"), datetime(2026, 10, 25, tzinfo=UTC)),
    (ZoneInfo("America/New_York"), datetime(2026, 11, 1, 5, tzinfo=UTC)),
)
EPOCH: Final = datetime(1900, 1, 1, tzinfo=UTC)
TWO_CENTURIES: Final = 200 * 365 * 86_400
LONGEST_INT: Final = 9_223_372_036_854_775_807
DIGITS: Final = 100_000_000_000_000_000_000

# pydantic builds a model from field types known at run time only.
_model: Final = cast("Callable[..., type[BaseModel]]", create_model)
_names: Final = count()


class Colour(IntEnum):
    RED = 1
    GREEN = 2


class Mood(Enum):
    CALM = "calm"
    BUSY = "busy"


@dataclass(frozen=True)
class Kind:
    """A type, and how to draw a value of it."""

    annotation: object
    draw: Callable[[Random], object]


def text(rng: Random) -> str:
    # Any character but the surrogates, which have no UTF-8 form.
    return "".join(
        chr(rng.choice((rng.randint(0, 0xD7FF), rng.randint(0xE000, 0x10FFFF))))
        for _ in range(rng.randint(0, 8))
    )


def finite_float(rng: Random) -> float:
    # Not uniform(-1e308, 1e308): the width of that range is infinite.
    return rng.choice((rng.uniform(-1, 1) * 1e308, rng.uniform(-1, 1), float(rng.randint(-9, 9))))


def instant(rng: Random) -> datetime:
    return EPOCH + timedelta(
        seconds=rng.randint(0, TWO_CENTURIES), microseconds=rng.randint(0, 999_999)
    )


def fixed_offset_datetime(rng: Random) -> datetime:
    return instant(rng).astimezone(timezone(timedelta(minutes=rng.randint(-1080, 1080))))


def zoned_datetime(rng: Random) -> datetime:
    if rng.random() < 0.3:  # inside an hour the clocks repeat, either time of it
        zone, start = rng.choice(REPEATED_HOURS)
        return (start + timedelta(seconds=rng.randint(0, 7199))).astimezone(zone)
    return instant(rng).astimezone(rng.choice(ZONES))


def clock_time(rng: Random) -> time:
    return time(rng.randint(0, 23), rng.randint(0, 59), rng.randint(0, 59), rng.randint(0, 999_999))


def duration(rng: Random) -> timedelta:
    return timedelta(
        days=rng.randint(-99_999, 99_999),
        seconds=rng.randint(0, 86_399),
        microseconds=rng.randint(0, 999_999),
    )


HASHABLE: Final = (
    Kind(int, lambda rng: rng.randint(-LONGEST_INT - 1, LONGEST_INT)),
    Kind(float, finite_float),
    Kind(str, text),
    Kind(bool, lambda rng: rng.random() < 0.5),
    Kind(datetime, fixed_offset_datetime),
    Kind(date, lambda rng: date.fromordinal(rng.randint(1, date.max.toordinal()))),
    Kind(time, clock_time),
    Kind(timedelta, duration),
    Kind(Decimal, lambda rng: Decimal(rng.randint(-DIGITS, DIGITS)).scaleb(rng.randint(-12, 6))),
    Kind(UUID, lambda rng: UUID(int=rng.getrandbits(128))),
    Kind(bytes, lambda rng: rng.randbytes(rng.randint(0, 16))),
    Kind(Colour, lambda rng: rng.choice(list(Colour))),
    Kind(Mood, lambda rng: rng.choice(list(Mood))),
    Kind(Literal["a", "b", 3], lambda rng: rng.choice(("a", "b", 3))),
)
SCALARS: Final = (*HASHABLE, Kind(NoneType, lambda _: None), Kind(ZonedDateTime, zoned_datetime))


def failure(rng: Random) -> Failure:
    if rng.random() < 0.5:
        return Bounce(text(rng), text(rng), rng.randint(400, 599))
    return Complaint(text(rng), text(rng), text(rng) or None)


def event(rng: Random) -> Event:
    draws: tuple[Callable[[Random], Event], ...] = (
        lambda r: Event(text(r)),
        lambda r: Delivery(text(r), text(r), fixed_offset_datetime(r)),
        failure,
        lambda r: Batch(text(r), tuple(failure(r) for _ in range(r.randint(0, 2))), [failure(r)]),
    )
    return rng.choice(draws)(rng)


def outage(rng: Random) -> Outage:
    return Outage(title=text(rng), level=rng.randint(0, 9), region=text(rng))


def notice(rng: Random) -> Notice:
    draws: tuple[Callable[[Random], Notice], ...] = (
        lambda r: Notice(title=text(r)),
        lambda r: Reminder(title=text(r), due=fixed_offset_datetime(r)),
        outage,
    )
    return rng.choice(draws)(rng)


def shape(rng: Random) -> Shape:
    if rng.random() < 0.5:
        return Circle(text(rng), finite_float(rng))
    return Square(text(rng), finite_float(rng))


# A value of any named class under the one declared: the base, or a class in between.
HIERARCHIES: Final = (
    Kind(Event, event),
    Kind(Failure, failure),
    Kind(Notice, notice),
    Kind(Alert, outage),
    Kind(Shape, shape),
)
LEAVES: Final = (*SCALARS, *HIERARCHIES)


def several(rng: Random, kind: Kind) -> list[object]:
    return [kind.draw(rng) for _ in range(rng.randint(0, 3))]


def list_of(inner: Kind, _rng: Random) -> Kind:
    return Kind(GenericAlias(list, (inner.annotation,)), lambda r: several(r, inner))


def tuple_of(inner: Kind, _rng: Random) -> Kind:
    return Kind(GenericAlias(tuple, (inner.annotation, ...)), lambda r: tuple(several(r, inner)))


def pair_of(inner: Kind, rng: Random) -> Kind:
    other = rng.choice(SCALARS)
    return Kind(
        GenericAlias(tuple, (inner.annotation, other.annotation)),
        lambda r: (inner.draw(r), other.draw(r)),
    )


def frozenset_of(_inner: Kind, rng: Random) -> Kind:
    element = rng.choice(HASHABLE)
    return Kind(
        GenericAlias(frozenset, (element.annotation,)), lambda r: frozenset(several(r, element))
    )


def dict_of(inner: Kind, _rng: Random) -> Kind:
    return Kind(
        GenericAlias(dict, (str, inner.annotation)),
        lambda r: {text(r): value for value in several(r, inner)},
    )


def optional(inner: Kind, _rng: Random) -> Kind:
    return Kind(
        cast("type", inner.annotation) | None,
        lambda r: None if r.random() < 0.3 else inner.draw(r),
    )


CONTAINERS: Final = (list_of, tuple_of, pair_of, frozenset_of, dict_of, optional)


def nested_kind(rng: Random, depth: int) -> Kind:
    if depth >= MAX_DEPTH or rng.random() < 0.4:
        return rng.choice(LEAVES)
    if rng.random() < 0.25:
        return composite_kind(rng, depth + 1)
    return rng.choice(CONTAINERS)(nested_kind(rng, depth + 1), rng)


def composite_kind(rng: Random, depth: int) -> Kind:
    """Draw a dataclass or a model whose fields are drawn in turn."""
    fields = {f"f{index}": nested_kind(rng, depth) for index in range(rng.randint(1, 4))}
    name = f"Generated{next(_names)}"
    built: type = (
        make_dataclass(name, [(field, kind.annotation) for field, kind in fields.items()])
        if rng.random() < 0.5
        else _model(
            name,
            __config__=_adapter_cache._EXACT,
            **{field: (kind.annotation, ...) for field, kind in fields.items()},
        )
    )
    build = cast("Callable[..., object]", built)
    return Kind(built, lambda r: build(**{field: kind.draw(r) for field, kind in fields.items()}))


def parts(read: object, value: object) -> Iterator[tuple[object, object]]:
    """Pair each part of ``value`` with the part of ``read`` in its place."""
    if isinstance(value, list | tuple):
        yield from zip(cast("list[object]", read), cast("list[object]", value), strict=True)
    elif isinstance(value, dict):
        mapping = cast("dict[str, object]", value)
        yield from ((cast("dict[str, object]", read)[key], mapping[key]) for key in mapping)
    elif isinstance(value, BaseModel) or dataclasses.is_dataclass(value):
        for name in cast("dict[str, object]", vars(value)):
            yield cast("object", getattr(read, name)), cast("object", getattr(value, name))


def assert_same(read: object, value: object) -> None:
    """Assert ``read`` has the exact type of ``value`` all the way down, and the same zone."""
    assert type(read) is type(value)
    if isinstance(value, datetime) and isinstance(value.tzinfo, ZoneInfo):
        assert (cast("datetime", read).tzinfo, cast("datetime", read).fold) == (
            value.tzinfo,
            value.fold,
        )
    elif isinstance(value, datetime):
        assert cast("datetime", read).utcoffset() == value.utcoffset()
    elif isinstance(value, frozenset):
        assert {type(part) for part in cast("frozenset[object]", read)} == {
            type(part) for part in value
        }
    for read_part, part in parts(read, value):
        assert_same(read_part, part)


def test_generated_values_read_back_equal_with_their_exact_types() -> None:
    rng = Random(SEED)  # noqa: S311 - drawn for reproducible cases, not for secrecy
    normalizer, encoder = PydanticNormalizer(), JsonEncoder()
    cases = with_class_names = 0

    for _ in range(TYPES):
        kind = composite_kind(rng, 0)
        for _ in range(VALUES_PER_TYPE):
            value = kind.draw(rng)
            text_written = encoder.encode(normalizer.normalize(value), "json")
            data = encoder.decode(text_written, "json")

            read = normalizer.denormalize(data, kind.annotation)

            assert read == value
            assert_same(read, value)
            cases += 1
            with_class_names += '"$type"' in text_written

    assert cases >= 1000
    assert with_class_names >= 200
