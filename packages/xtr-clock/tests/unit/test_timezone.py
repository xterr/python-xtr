from __future__ import annotations

from datetime import UTC, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from xtr_clock import InvalidTimezoneError, local_timezone, resolve_timezone


def test_an_already_resolved_timezone_is_returned_unchanged() -> None:
    zone = ZoneInfo("Europe/Paris")

    assert resolve_timezone(zone) is zone


def test_utc_resolves_by_name() -> None:
    assert resolve_timezone("UTC").utcoffset(None) == timedelta(0)


@pytest.mark.parametrize("name", ["UTC", "utc", "Z", "z"])
def test_every_spelling_of_utc_resolves_to_the_same_object(name: str) -> None:
    assert resolve_timezone(name) is UTC


def test_utc_needs_no_timezone_database_behind_it() -> None:
    assert not isinstance(resolve_timezone("UTC"), ZoneInfo)


@pytest.mark.parametrize("name", ["Z", "z"])
def test_the_zulu_designator_resolves_to_utc(name: str) -> None:
    assert resolve_timezone(name) is UTC


def test_an_iana_name_resolves_to_that_zone() -> None:
    assert resolve_timezone("Europe/Paris") == ZoneInfo("Europe/Paris")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("+02:00", timedelta(hours=2)),
        ("+0200", timedelta(hours=2)),
        ("-05:30", -timedelta(hours=5, minutes=30)),
        ("-0530", -timedelta(hours=5, minutes=30)),
        ("+00:00", timedelta(0)),
    ],
)
def test_a_fixed_offset_resolves_to_that_offset(name: str, expected: timedelta) -> None:
    assert resolve_timezone(name) == timezone(expected)


@pytest.mark.parametrize("name", ["Nope/Nope", "", "Europe/Paris/Extra", "not a zone"])
def test_a_name_this_system_does_not_know_is_refused(name: str) -> None:
    with pytest.raises(InvalidTimezoneError) as caught:
        _ = resolve_timezone(name)

    assert caught.value.timezone == name


@pytest.mark.parametrize("name", ["+25:00", "+02:60", "-99:99", "+24:00", "-24:00"])
def test_an_offset_outside_the_possible_range_is_refused(name: str) -> None:
    with pytest.raises(InvalidTimezoneError):
        _ = resolve_timezone(name)


def test_the_error_is_also_a_value_error() -> None:
    with pytest.raises(ValueError, match="Nope/Nope"):
        _ = resolve_timezone("Nope/Nope")


def test_the_local_timezone_comes_from_tz_when_it_names_a_known_zone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "Asia/Tokyo")

    assert local_timezone() == ZoneInfo("Asia/Tokyo")


def test_a_tz_this_system_cannot_read_falls_back_instead_of_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TZ", "EST5EDT,M3.2.0,M11.1.0")

    assert local_timezone().utcoffset(None) is not None


def test_the_local_timezone_is_resolvable_with_no_tz_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("TZ", raising=False)

    assert local_timezone() is not None
