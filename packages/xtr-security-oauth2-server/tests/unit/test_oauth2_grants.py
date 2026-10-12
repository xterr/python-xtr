"""The grant types this server names, and the question of whether it knows one."""

from __future__ import annotations

import pytest

from xtr_security_oauth2_server.oauth2_grants import OAuth2Grants


@pytest.mark.parametrize(
    ("named", "expected"),
    [
        (OAuth2Grants.AUTHORIZATION_CODE, "authorization_code"),
        (OAuth2Grants.CLIENT_CREDENTIALS, "client_credentials"),
        (OAuth2Grants.IMPLICIT, "implicit"),
        (OAuth2Grants.PASSWORD, "password"),
        (OAuth2Grants.REFRESH_TOKEN, "refresh_token"),
        (OAuth2Grants.DEVICE_CODE, "urn:ietf:params:oauth:grant-type:device_code"),
    ],
)
def test_it_names_each_grant_as_the_protocol_does(named: str, expected: str) -> None:
    assert named == expected


@pytest.mark.parametrize(
    "grant",
    [
        "authorization_code",
        "client_credentials",
        "implicit",
        "password",
        "refresh_token",
        "urn:ietf:params:oauth:grant-type:device_code",
    ],
)
def test_it_knows_every_grant_it_names(grant: str) -> None:
    assert OAuth2Grants.has(grant) is True


def test_it_does_not_know_a_grant_it_never_named() -> None:
    assert OAuth2Grants.has("urn:ietf:params:oauth:grant-type:token-exchange") is False
