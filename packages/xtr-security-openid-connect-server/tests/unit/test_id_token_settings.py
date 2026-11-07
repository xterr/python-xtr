"""What an ID token is signed with, and how long it lasts."""

from __future__ import annotations

import dataclasses
from datetime import timedelta

import pytest

from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)
from xtr_security_openid_connect_server.id_token_settings import IdTokenSettings


def test_it_keeps_the_algorithm_and_the_lifetime() -> None:
    settings = IdTokenSettings(algorithm="ES256", ttl=timedelta(minutes=5))

    assert settings.algorithm == "ES256"
    assert settings.ttl == timedelta(minutes=5)


def test_with_no_lifetime_the_access_token_decides() -> None:
    assert IdTokenSettings(algorithm="RS256").ttl is None


def test_an_empty_algorithm_is_refused_by_name() -> None:
    with pytest.raises(InvalidArgumentError, match="algorithm"):
        _ = IdTokenSettings(algorithm="")


@pytest.mark.parametrize("ttl", [timedelta(0), timedelta(seconds=-1)])
def test_a_lifetime_that_is_not_positive_is_refused_by_name(ttl: timedelta) -> None:
    with pytest.raises(InvalidArgumentError, match="ttl"):
        _ = IdTokenSettings(algorithm="RS256", ttl=ttl)


def test_it_cannot_be_changed_once_built() -> None:
    settings = IdTokenSettings(algorithm="RS256")
    field = "algorithm"

    with pytest.raises(dataclasses.FrozenInstanceError):
        # Through setattr: the type checkers refuse the assignment on sight, and
        # what is tested here is that the runtime refuses it too.
        setattr(settings, field, "ES256")
