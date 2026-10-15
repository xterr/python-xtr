"""The header value that sets a cookie, and the one that clears it."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime

import pytest

from xtr_http_foundation import cleared_cookie_header_value, cookie_header_value
from xtr_http_foundation.exception import InvalidArgumentError


def test_it_sets_a_cookie_with_the_attributes_a_browser_honours() -> None:
    assert cookie_header_value("session", "abc") == "session=abc; path=/; httponly; samesite=lax"


def test_it_encodes_a_value_that_cannot_sit_in_a_header_as_it_arrived() -> None:
    value = cookie_header_value("session", "a b/c")

    assert value == "session=a%20b%2Fc; path=/; httponly; samesite=lax"


def test_it_encodes_the_reserved_characters_of_a_name() -> None:
    value = cookie_header_value("a b", "abc")

    assert value == "a%20b=abc; path=/; httponly; samesite=lax"


def test_it_dates_a_cookie_from_the_moment_it_expires() -> None:
    expires = datetime(2035, 1, 1, tzinfo=UTC)

    value = cookie_header_value("session", "abc", expires=expires)

    assert value.startswith("session=abc; expires=Mon, 01 Jan 2035 00:00:00 GMT; Max-Age=")
    max_age = int(value.split("Max-Age=", 1)[1].split(";", 1)[0])
    expected = int(expires.timestamp() - datetime.now(UTC).timestamp())
    assert abs(max_age - expected) <= 2


def test_it_reads_a_naive_moment_as_utc() -> None:
    value = cookie_header_value("session", "abc", expires=datetime(2035, 1, 1))  # noqa: DTZ001 — the naive moment is the point: the builder reads it as UTC.

    assert "expires=Mon, 01 Jan 2035 00:00:00 GMT" in value


def test_it_carries_every_attribute_in_the_order_a_browser_reads_them() -> None:
    value = cookie_header_value(
        "session",
        "abc",
        expires=datetime(2035, 1, 1, tzinfo=UTC),
        path="/login",
        domain="example.com",
        secure=True,
        httponly=False,
        samesite="Strict",
    )

    parts = value.split("; ")
    assert parts[0] == "session=abc"
    assert parts[1] == "expires=Mon, 01 Jan 2035 00:00:00 GMT"
    assert parts[2].startswith("Max-Age=")
    assert parts[3:] == ["path=/login", "domain=example.com", "secure", "samesite=strict"]


def test_it_reads_samesite_without_regard_to_case() -> None:
    value = cookie_header_value("session", "abc", samesite="Strict")

    assert value.endswith("samesite=strict")


@pytest.mark.parametrize("samesite", [None, ""])
def test_it_writes_no_samesite_attribute_for_none_or_empty(samesite: str | None) -> None:
    value = cookie_header_value("session", "abc", samesite=samesite)

    assert "samesite" not in value


@pytest.mark.parametrize("path", [None, "", "/"])
def test_it_reads_every_silent_path_as_the_whole_site(path: str | None) -> None:
    value = cookie_header_value("session", "abc", path=path)

    assert value.startswith("session=abc; path=/;")


def test_it_clears_a_cookie_whose_value_is_empty() -> None:
    value = cookie_header_value("session", "")

    assert value.startswith("session=deleted; expires=")
    assert value.endswith("; Max-Age=0; path=/; httponly; samesite=lax")

    moment = parsedate_to_datetime(value.split("expires=", 1)[1].split(";", 1)[0])
    ago = datetime.now(UTC) - moment
    assert timedelta(days=365) < ago < timedelta(days=367)


def test_it_clears_a_cookie_by_name_with_the_attributes_it_was_set_with() -> None:
    value = cleared_cookie_header_value(
        "session",
        path="/login",
        domain="example.com",
        secure=True,
        httponly=False,
        samesite=None,
    )

    assert value.startswith("session=deleted; expires=")
    assert value.endswith("; Max-Age=0; path=/login; domain=example.com; secure")


def test_clearing_by_name_is_setting_with_the_value_emptied() -> None:
    assert cleared_cookie_header_value("session") == cookie_header_value("session", "")


def test_it_refuses_a_name_that_is_empty() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("", "abc")


@pytest.mark.parametrize("samesite", ["sometimes", "lax "])
def test_it_refuses_a_samesite_that_is_none_of_the_three(samesite: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("session", "abc", samesite=samesite)


def test_it_refuses_a_path_that_cannot_sit_in_an_attribute() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("session", "abc", path="/login;secure")


def test_it_refuses_a_domain_that_cannot_sit_in_an_attribute() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("session", "abc", domain="example.com,other")


@pytest.mark.parametrize("name", ["__Secure-session", "__Host-session"])
def test_it_refuses_a_reserved_prefix_without_the_secure_flag(name: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value(name, "abc")


def test_it_refuses_a_host_prefix_with_a_domain() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("__Host-session", "abc", secure=True, domain="example.com")


def test_it_refuses_a_host_prefix_with_a_path_besides_the_root() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = cookie_header_value("__Host-session", "abc", secure=True, path="/login")


def test_it_builds_a_host_prefixed_cookie_that_asked_for_everything() -> None:
    value = cookie_header_value("__Host-session", "abc", secure=True)

    assert value == "__Host-session=abc; path=/; secure; httponly; samesite=lax"
