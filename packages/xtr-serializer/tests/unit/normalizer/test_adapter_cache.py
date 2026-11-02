"""The adapter of each type, built under the exact configuration, kept for the types used last."""

from __future__ import annotations

import sysconfig
import threading
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Annotated, Literal, cast, final

import pytest
from pydantic import AwareDatetime, Field, NaiveDatetime, ValidationError
from pydantic_core import to_json
from typing_extensions import (  # pydantic reads typing's TypedDict from Python 3.12
    TypedDict,
    override,
)

from tests.fixtures.exact_values import Appointment, Color, Shape, Visit
from tests.fixtures.nameless import NamelessThing, names_refused
from tests.fixtures.refused_types import (
    REFUSED_TYPES,
    TYPE_CODE_RAISED,
    Sealed,
    Unprintable,
    Unshown,
    nested,
    optionals,
)
from xtr_serializer.normalizer import _adapter_cache as adapter_cache
from xtr_serializer.normalizer._adapter_cache import (
    Adapter,
    AdapterCache,
    build_adapter,
)

if TYPE_CHECKING:
    from collections.abc import Callable


class Opaque:
    """A class pydantic has no schema for."""


class Malformed:
    """A class whose schema hook hands pydantic a schema it refuses."""

    @classmethod
    def __get_pydantic_core_schema__(cls, source: object, handler: object) -> dict[str, str]:
        return {"type": "no-such-schema"}


def test_it_gives_the_same_adapter_for_a_type_used_again() -> None:
    cache = AdapterCache()

    assert cache.get(list[int]) is cache.get(list[int])


def test_it_tells_why_a_type_has_no_adapter() -> None:
    assert build_adapter(Opaque) == "pydantic has no schema for 'Opaque'"


def test_it_names_a_type_with_no_adapter_without_running_its_metaclass() -> None:
    with names_refused():
        adapter = build_adapter(NamelessThing)

    assert adapter == "pydantic has no schema for 'NamelessThing'"


def test_it_tells_why_a_type_whose_schema_pydantic_refuses_has_no_adapter() -> None:
    assert build_adapter(Malformed) == "pydantic refuses the schema of 'Malformed'"


def test_it_tells_why_a_type_pydantic_cannot_build_a_schema_for_has_no_adapter() -> None:
    field = cast("object", Field(discriminator="kind"))
    name = f"Annotated[int, {field!r}]"

    assert build_adapter(Annotated[int, field]) == f"pydantic cannot build a schema for {name!r}"


# Built in the test, not as the module is collected: some interpreters, such as Python 3.12.0,
# recurse past the stack building annotated optionals much deeper than these as typing hashes them.
@pytest.mark.parametrize(
    "type_of", [lambda: nested(500), lambda: optionals(250)], ids=["lists", "annotated-optionals"]
)
def test_a_type_nested_too_deep_to_be_kept_has_no_adapter(type_of: Callable[[], object]) -> None:
    adapter = AdapterCache().get(type_of())

    assert isinstance(adapter, str)
    assert adapter.startswith("pydantic cannot build a schema for ")


def test_a_type_equal_to_a_kept_one_too_deep_to_compare_is_built_again() -> None:
    cache = AdapterCache()

    first = cache.get(optionals(202))
    second = cache.get(optionals(202))

    assert isinstance(first, str)
    assert second == first


@final
class Fickle:
    """Metadata answering a number of hashes and comparisons, then refusing every one after.

    Hashed by its identity unless told otherwise, so the typing module, which keeps the types
    it built, never compares a new one with one kept there that now refuses.
    """

    def __init__(self, hashed: int | None = None) -> None:
        self.hashed = id(self) if hashed is None else hashed
        self.answers = 1_000_000

    def _answer(self) -> None:
        if self.answers <= 0:
            raise LookupError(TYPE_CODE_RAISED)
        self.answers -= 1

    @override
    def __hash__(self) -> int:
        self._answer()
        return self.hashed

    @override
    def __eq__(self, other: object) -> bool:
        self._answer()
        return self is other

    @override
    def __repr__(self) -> str:
        return "Fickle()"


def reads_an_int(adapter: Adapter | str) -> bool:
    """Tell whether ``adapter`` is the one of an ``int``, whatever annotates it."""
    return isinstance(adapter, Adapter) and cast("object", adapter.reader.validate_json("1")) == 1


@pytest.mark.parametrize("answers", range(6))
def test_a_type_whose_hash_starts_raising_while_it_is_kept_is_still_answered(answers: int) -> None:
    fickle = Fickle()
    type_ = Annotated[int, fickle]
    cache = AdapterCache()
    fickle.answers = answers

    first = cache.get(type_)
    again = cache.get(type_)

    assert reads_an_int(first)
    assert reads_an_int(again)


def test_types_evicting_a_kept_one_whose_hash_now_raises_are_answered_and_kept() -> None:
    fickle = Fickle()
    type_ = Annotated[int, fickle]
    cache = AdapterCache()
    _ = cache.get(type_)
    fickle.answers = 0
    others = [Annotated[int, number] for number in range(256)]

    adapters = [cache.get(other) for other in others]

    assert all(map(reads_an_int, adapters))
    assert cache.get(others[-1]) is adapters[-1]
    assert reads_an_int(cache.get(type_))


def test_a_kept_type_whose_comparison_now_raises_leaves_one_hashed_alike_kept() -> None:
    kept = Fickle()
    other = Fickle(hashed=kept.hashed)
    kept_type, other_type = Annotated[int, kept], Annotated[int, other]
    cache = AdapterCache()
    _ = cache.get(kept_type)
    kept.answers = 0

    adapter = cache.get(other_type)

    assert reads_an_int(adapter)
    assert cache.get(other_type) is adapter


# Hashes under which a lookup of a type hashed as KEPT compares it with a kept one again and
# again, a type hashed as NESTED kept beside it. Should each comparison change the table, moving
# NESTED to the end say, the table is rebuilt before the lookup gives up, and the lookup starts
# over: for ever, on Python 3.13 and later, whose tables they are chosen for. The free-threaded
# build lays its table out another way.
FREE_THREADED = bool(cast("object", sysconfig.get_config_var("Py_GIL_DISABLED")))
KEPT, NESTED = (
    (3822639324648131612, 372269656135498629)
    if FREE_THREADED
    else (2920007979038758759, 4016821748236031427)
)


@final
class Nested:
    """A type hashed as ``NESTED``."""

    @override
    def __hash__(self) -> int:
        return NESTED

    @override
    def __repr__(self) -> str:
        return "Nested()"


@final
class Recalling:
    """A type hashed as ``KEPT``, whose comparison with another looks ``recalled`` up in a cache.

    Compared with anything else, as pydantic compares it while building it, it uses no cache, so
    what a cache keeps is the same whatever pydantic's version.
    """

    def __init__(self, cache: AdapterCache, recalled: object) -> None:
        self.cache = cache
        self.recalled = recalled

    @override
    def __hash__(self) -> int:
        return KEPT

    @override
    def __eq__(self, other: object) -> bool:
        if isinstance(other, Recalling):
            _ = self.cache.get(self.recalled)
        return self is other

    @override
    def __repr__(self) -> str:
        return "Recalling()"


def looked_up_in_a_thread(cache: AdapterCache, type_: object) -> list[Adapter | str]:
    """Look ``type_`` up in a thread of its own, so a lookup that never ends fails, not hangs."""
    answers: list[Adapter | str] = []
    lookup = threading.Thread(target=lambda: answers.append(cache.get(type_)), daemon=True)
    lookup.start()
    lookup.join(timeout=10)
    return answers


def test_a_type_whose_comparison_uses_the_cache_again_is_answered() -> None:
    cache = AdapterCache()
    _ = cache.get(Recalling(cache, Nested()))
    other = Recalling(cache, Nested())

    answers = looked_up_in_a_thread(cache, other)

    assert answers == [build_adapter(other)]


def test_a_type_whose_comparison_uses_a_kept_type_again_is_answered() -> None:
    cache, nested = AdapterCache(), Nested()
    _ = cache.get(Recalling(cache, nested))
    _ = cache.get(nested)
    other = Recalling(cache, nested)

    answers = looked_up_in_a_thread(cache, other)

    assert answers == [build_adapter(other)]


@final
class Colliding:
    """A type hashed alike with all others, whose next comparison may look a type up in a cache."""

    def __init__(self, cache: AdapterCache) -> None:
        self.cache = cache
        self.recalled: object = None

    @override
    def __hash__(self) -> int:
        return 0

    @override
    def __eq__(self, other: object) -> bool:
        recalled, self.recalled = self.recalled, None
        if recalled is not None:
            _ = self.cache.get(recalled)
        return self is other

    @override
    def __repr__(self) -> str:
        return "Colliding()"


def test_a_comparison_using_the_cache_again_as_it_evicts_leaves_it_bounded() -> None:
    cache = AdapterCache()
    first, second, third = Colliding(cache), Colliding(cache), Colliding(cache)
    others = [Annotated[int, number] for number in range(255)]
    for type_ in [first, second, third, *others[:-1]]:
        _ = cache.get(type_)
    # The last of those evicts `first`; `third`, used again, takes the slot it left (but on the
    # free-threaded build, whose table does not reuse it), which a lookup of `second` probes first.
    _ = cache.get(third)
    third.recalled = Annotated[int, "recalled"]

    # Evicting `second` compares `third` with it, which looks up a type the cache does not keep.
    _ = cache.get(others[-1])

    assert len(cache._adapters) <= 256


def test_a_type_being_built_holds_up_no_lookup_in_another_thread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cache = AdapterCache()
    _ = cache.get(int)
    build = adapter_cache.build_adapter
    answered: list[bool] = []

    def build_while_another_thread_looks_up(type_: object) -> Adapter | str:
        lookup = threading.Thread(target=cache.get, args=(int,), daemon=True)
        lookup.start()
        lookup.join(timeout=10)
        answered.append(not lookup.is_alive())
        return build(type_)

    monkeypatch.setattr(adapter_cache, "build_adapter", build_while_another_thread_looks_up)

    _ = cache.get(str)

    assert answered == [True]


@pytest.mark.parametrize(
    ("type_", "name"),
    [(Unshown, "Unshown"), (Unprintable(), "a type that cannot be named"), (Sealed, "Sealed")],
    ids=["unshown-class", "unprintable", "sealed-class"],
)
def test_it_tells_why_a_type_whose_building_raises_has_no_adapter(type_: object, name: str) -> None:
    assert build_adapter(type_) == (
        f"pydantic cannot build a schema for {name!r}: building it raised LookupError"
    )


@pytest.mark.parametrize("type_", REFUSED_TYPES.values(), ids=REFUSED_TYPES.keys())
def test_it_tells_why_any_type_pydantic_refuses_to_build_has_no_adapter(type_: object) -> None:
    adapter = build_adapter(type_)

    assert isinstance(adapter, str)
    assert adapter.startswith("pydantic cannot build a schema for ")


@pytest.mark.parametrize("type_", [Color, Shape], ids=["tuple-members", "dict-members"])
def test_an_application_value_of_a_container_subclass_stays_in_the_schema(type_: object) -> None:
    assert isinstance(build_adapter(type_), Adapter)


def test_an_adapter_reads_strictly_and_refuses_what_is_not_finite() -> None:
    adapter = build_adapter(tuple[int, Decimal])
    assert isinstance(adapter, Adapter)

    with pytest.raises(ValidationError) as raised:
        _ = cast("object", adapter.reader.validate_json('["1", "NaN"]'))

    assert [error["type"] for error in raised.value.errors()] == ["int_type", "finite_number"]


def test_its_reader_refuses_a_naive_datetime_where_the_type_declares_no_zone_rule() -> None:
    adapter = build_adapter(dict[str, datetime])
    assert isinstance(adapter, Adapter)

    with pytest.raises(ValidationError) as raised:
        _ = cast("object", adapter.reader.validate_json('{"at": "2026-01-01T00:00:00"}'))

    assert raised.value.errors()[0]["type"] == "timezone_aware"


@pytest.mark.parametrize(
    ("type_", "text"),
    [(NaiveDatetime, '"2026-01-01T00:00:00"'), (AwareDatetime, '"2026-01-01T00:00:00Z"')],
    ids=["naive", "aware"],
)
def test_a_datetime_declaring_its_zone_rule_keeps_it(type_: object, text: str) -> None:
    adapter = build_adapter(type_)
    assert isinstance(adapter, Adapter)

    assert isinstance(cast("object", adapter.reader.validate_json(text)), datetime)


@pytest.mark.parametrize(
    ("type_", "expected"),
    [
        (Appointment, Appointment(at=datetime(2026, 1, 1))),  # noqa: DTZ001 - its own rule
        (Visit, Visit(at=datetime(2026, 1, 1))),  # noqa: DTZ001 - its own rule
    ],
    ids=["model", "pydantic-dataclass"],
)
def test_its_reader_leaves_a_model_its_own_zone_rule(type_: object, expected: object) -> None:
    adapter = build_adapter(type_)
    assert isinstance(adapter, Adapter)

    assert cast("object", adapter.reader.validate_json('{"at": "2026-01-01T00:00:00"}')) == expected


@dataclass
class Shaped:
    """A default value that looks like a schema of a datetime."""

    shapes: tuple[dict[str, str], ...] = ({"type": "datetime"},)


def test_a_default_value_shaped_like_a_schema_is_read_as_it_is() -> None:
    adapter = build_adapter(Shaped)
    assert isinstance(adapter, Adapter)

    assert cast("object", adapter.reader.validate_json("{}")) == Shaped()


class Named(TypedDict):
    """Fields named as the parts of a schema that hold the application's values."""

    members: datetime
    default: datetime
    metadata: datetime
    expected: datetime
    custom_error_context: datetime


@pytest.mark.parametrize("field", list(Named.__annotations__))
def test_its_reader_refuses_a_naive_datetime_in_a_field_named_as_a_part_of_a_schema(
    field: str,
) -> None:
    adapter = build_adapter(Named)
    assert isinstance(adapter, Adapter)
    data = dict.fromkeys(Named.__annotations__, "2026-01-01T00:00:00Z")
    data[field] = "2026-01-01T00:00:00"

    with pytest.raises(ValidationError) as raised:
        _ = cast("object", adapter.reader.validate_json(to_json(data)))

    assert [(error["type"], error["loc"]) for error in raised.value.errors()] == [
        ("timezone_aware", (field,))
    ]


class ByDefault(TypedDict):
    """A union member tagged as the part of a schema that holds a default."""

    kind: Literal["default"]
    at: datetime


class ByMembers(TypedDict):
    """A union member tagged as the part of a schema that holds an enum's members."""

    kind: Literal["members"]
    at: datetime


@pytest.mark.parametrize("tag", ["default", "members"])
def test_its_reader_refuses_a_naive_datetime_in_a_union_member_tagged_as_a_part_of_a_schema(
    tag: str,
) -> None:
    adapter = build_adapter(Annotated[ByDefault | ByMembers, Field(discriminator="kind")])
    assert isinstance(adapter, Adapter)
    text = to_json({"kind": tag, "at": "2026-01-01T00:00:00"})

    with pytest.raises(ValidationError) as raised:
        _ = cast("object", adapter.reader.validate_json(text))

    assert raised.value.errors()[0]["type"] == "timezone_aware"
