"""The shape of the cookie a session's ID travels in."""

from __future__ import annotations

import dataclasses

import pytest

from xtr_http_foundation import SessionCookieConfig
from xtr_http_foundation.exception import InvalidArgumentError


def _assign(target: object, name: str, value: object) -> None:
    # Taking an `object` keeps the type checkers out of the way. They refuse the
    # assignment on sight, and what is being tested here is that so does the runtime.
    setattr(target, name, value)


def test_it_builds_with_nothing_said() -> None:
    cookie = SessionCookieConfig()

    assert cookie.name == "xtr_session"
    assert cookie.path == "/"
    assert cookie.domain is None
    assert cookie.secure is False
    assert cookie.httponly is True
    assert cookie.samesite == "lax"
    assert cookie.lifetime is None


def test_it_is_frozen_once_built() -> None:
    cookie = SessionCookieConfig()

    with pytest.raises(dataclasses.FrozenInstanceError):
        _assign(cookie, "name", "other_session")


def test_it_refuses_a_name_no_cookie_could_carry() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SessionCookieConfig(name="")


@pytest.mark.parametrize("samesite", ["sometimes", "lax "])
def test_it_refuses_a_samesite_that_is_none_of_the_three(samesite: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SessionCookieConfig(samesite=samesite)


def test_it_reads_a_samesite_without_regard_to_case() -> None:
    assert SessionCookieConfig(samesite="Strict").samesite == "Strict"


def test_it_refuses_a_negative_lifetime() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = SessionCookieConfig(lifetime=-1)
