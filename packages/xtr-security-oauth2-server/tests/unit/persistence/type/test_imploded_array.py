"""A list of value objects stored as one space-joined string, and read back."""

from __future__ import annotations

from typing import TYPE_CHECKING, final

import pytest
from sqlalchemy import Text
from sqlalchemy.dialects import sqlite
from typing_extensions import override

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.imploded_array import ImplodedArray

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()


@final
class Letters(ImplodedArray[str]):
    """A concrete decorator whose value objects are plain strings."""

    impl = Text
    cache_ok = True

    @override
    def convert_database_values(self, values: Sequence[str]) -> tuple[str, ...]:
        """Return the stored words as they came."""
        return tuple(values)


def test_it_stores_text_so_any_number_of_values_fits() -> None:
    assert isinstance(Letters().impl_instance, Text)


def test_a_list_goes_in_as_one_space_joined_string() -> None:
    assert Letters().process_bind_param(("read", "write"), _DIALECT) == "read write"


def test_one_value_goes_in_on_its_own() -> None:
    assert Letters().process_bind_param(("read",), _DIALECT) == "read"


def test_an_empty_list_goes_in_as_nothing_at_all() -> None:
    assert Letters().process_bind_param((), _DIALECT) is None


def test_nothing_goes_in_as_nothing() -> None:
    assert Letters().process_bind_param(None, _DIALECT) is None


def test_a_stored_string_comes_back_split() -> None:
    assert Letters().process_result_value("read write", _DIALECT) == ("read", "write")


def test_nothing_stored_comes_back_as_an_empty_list() -> None:
    assert Letters().process_result_value(None, _DIALECT) == ()


def test_the_values_are_whatever_the_decorator_makes_of_them() -> None:
    assert Letters().convert_database_values(["read"]) == ("read",)


async def test_a_list_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, Letters(), ("read", "write")) == ("read", "write")


async def test_an_empty_list_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, Letters(), ()) == ()


def test_it_may_be_cached_so_a_query_on_it_is_not_recompiled_every_time() -> None:
    assert isinstance(Letters()._static_cache_key, tuple)
