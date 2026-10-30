"""The adapter of each type, built under the exact configuration, kept for the types used last."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import cast

import pytest
from pydantic import AwareDatetime, NaiveDatetime, ValidationError

from tests.fixtures.exact_values import Appointment, Color, Shape, Visit
from xtr_serializer.normalizer._adapter_cache import Adapter, AdapterCache, build_adapter


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


def test_it_tells_why_a_type_whose_schema_pydantic_refuses_has_no_adapter() -> None:
    assert build_adapter(Malformed) == "pydantic refuses the schema of 'Malformed'"


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
