"""An instant stored in UTC, and read back knowing it is in UTC."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import DateTime
from sqlalchemy.dialects import sqlite
from xtr_security_oauth2_server_core.exception.invalid_argument_error import InvalidArgumentError

from tests.support.orm import round_trip
from xtr_security_oauth2_server.persistence.type.utc_datetime import UtcDateTime

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = pytest.mark.anyio

_DIALECT = sqlite.dialect()
_AT_NOON = datetime(2026, 3, 4, 12, 0, 0, tzinfo=UTC)


def test_it_stores_a_plain_timestamp_so_every_database_reads_the_same() -> None:
    stored = UtcDateTime().impl_instance

    assert isinstance(stored, DateTime)
    assert stored.timezone is False


def test_an_instant_goes_in_without_its_zone_because_it_is_already_utc() -> None:
    assert UtcDateTime().process_bind_param(_AT_NOON, _DIALECT) == datetime(2026, 3, 4, 12, 0, 0)  # noqa: DTZ001 -- the stored value is deliberately naive


def test_an_instant_in_another_zone_is_moved_to_utc_before_it_is_stored() -> None:
    elsewhere = datetime(2026, 3, 4, 14, 0, 0, tzinfo=timezone(timedelta(hours=2)))

    assert UtcDateTime().process_bind_param(elsewhere, _DIALECT) == datetime(2026, 3, 4, 12, 0, 0)  # noqa: DTZ001 -- the stored value is deliberately naive


def test_nothing_goes_in_as_nothing() -> None:
    assert UtcDateTime().process_bind_param(None, _DIALECT) is None


def test_a_stored_timestamp_comes_back_knowing_it_is_utc() -> None:
    read = UtcDateTime().process_result_value(datetime(2026, 3, 4, 12, 0, 0), _DIALECT)  # noqa: DTZ001 -- what a database without zones hands back

    assert read == _AT_NOON
    assert read is not None
    assert read.tzinfo is UTC


def test_nothing_stored_comes_back_as_nothing() -> None:
    assert UtcDateTime().process_result_value(None, _DIALECT) is None


def test_a_naive_instant_is_refused_rather_than_guessed_at() -> None:
    with pytest.raises(InvalidArgumentError, match="time zone"):
        _ = UtcDateTime().process_bind_param(datetime(2026, 3, 4, 12, 0, 0), _DIALECT)  # noqa: DTZ001 -- the point of the test is an instant with no zone


async def test_an_instant_survives_a_trip_through_a_database(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, UtcDateTime(), _AT_NOON) == _AT_NOON


async def test_nothing_survives_a_trip_through_a_database_as_nothing(tmp_path: Path) -> None:
    assert await round_trip(tmp_path, UtcDateTime(), None) is None


def test_it_may_be_cached_so_a_query_on_it_is_not_recompiled_every_time() -> None:
    assert isinstance(UtcDateTime()._static_cache_key, tuple)
