"""A call into this package it cannot answer for, which answers nobody."""

from __future__ import annotations

import pytest
from xtr_security_oauth2_server_core.exception import OAuthServerError

from xtr_security_openid_connect_server.exception import OpenIdConnectServerError
from xtr_security_openid_connect_server.exception.invalid_argument_error import (
    InvalidArgumentError,
)


def test_one_except_for_this_package_catches_it() -> None:
    with pytest.raises(OpenIdConnectServerError, match=r"a claim set names no scope"):
        raise InvalidArgumentError("a claim set names no scope")


def test_a_malformed_call_is_a_bad_argument() -> None:
    with pytest.raises(ValueError, match=r"a claim set names no scope"):
        raise InvalidArgumentError("a claim set names no scope")


def test_it_is_not_a_refusal_a_client_is_waiting_for() -> None:
    # Nothing a client sent caused it, so no endpoint may answer it as a
    # protocol error.
    assert not issubclass(InvalidArgumentError, OAuthServerError)
