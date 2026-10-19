"""The marker every refused link's error wears, catchable as itself."""

from __future__ import annotations

import pytest

from xtr_security_http.exception import (
    ExpiredLoginLinkError,
    InvalidLoginLinkError,
    InvalidLoginLinkErrorInterface,
)


def test_the_marker_is_an_error_base_a_catch_can_name() -> None:
    assert issubclass(InvalidLoginLinkErrorInterface, Exception)


def test_the_marker_catches_the_refusals_that_wear_it() -> None:
    with pytest.raises(InvalidLoginLinkErrorInterface):
        raise InvalidLoginLinkError('Missing "user" parameter.')


def test_the_marker_catches_an_expired_link_too() -> None:
    with pytest.raises(InvalidLoginLinkErrorInterface):
        raise ExpiredLoginLinkError("Login link has expired.")
