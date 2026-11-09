"""The post-authentication token carries the raw token and the firewall."""

from __future__ import annotations

import json
from typing import NoReturn, cast

import pytest
from xtr_security_core.authentication.token.abstract_token import AbstractToken
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user.in_memory_user import InMemoryUser
from xtr_security_http.session import SessionTokenSerializer

from xtr_security_jwt.security.authenticator.token.jwt_post_authentication_token import (
    JwtPostAuthenticationToken,
)


def test_it_is_an_abstract_token() -> None:
    assert AbstractToken in JwtPostAuthenticationToken.__mro__


def test_it_carries_the_user_firewall_roles_and_raw_token() -> None:
    user = InMemoryUser("ada", roles=["ROLE_USER"])
    token = JwtPostAuthenticationToken(user, "api", ("ROLE_USER",), "a.b.c")

    assert token.get_user() is user
    assert token.get_firewall_name() == "api"
    assert list(token.get_role_names()) == ["ROLE_USER"]
    assert token.get_credentials() == "a.b.c"


def test_a_session_keeps_the_raw_token_beside_the_firewall() -> None:
    token = JwtPostAuthenticationToken(InMemoryUser("ada"), "api", ("ROLE_USER",), "a.b.c")

    state = SessionTokenSerializer().encode(token)["state"]

    assert state == {
        "roles": ["ROLE_USER"],
        "attributes": {},
        "firewall": "api",
        "raw_token": "a.b.c",
    }


def test_it_is_rebuilt_from_a_session_with_its_raw_token() -> None:
    serializer = SessionTokenSerializer()
    token = JwtPostAuthenticationToken(InMemoryUser("ada"), "api", ("ROLE_USER",), "a.b.c")
    kept = cast("object", json.loads(json.dumps(serializer.encode(token))))

    rebuilt = serializer.decode(kept)

    assert isinstance(rebuilt, JwtPostAuthenticationToken)
    assert rebuilt.get_credentials() == "a.b.c"
    assert rebuilt.get_firewall_name() == "api"
    assert rebuilt.get_user_identifier() == "ada"
    assert list(rebuilt.get_role_names()) == ["ROLE_USER"]


@pytest.mark.parametrize("raw_token", [None, "", 1])
def test_a_session_state_without_a_raw_token_is_refused(raw_token: object) -> None:
    state: dict[str, object] = {
        "roles": ["ROLE_USER"],
        "attributes": {},
        "firewall": "api",
        "raw_token": raw_token,
    }

    with pytest.raises(InvalidArgumentError, match="raw_token"):
        _ = JwtPostAuthenticationToken.from_session(state, InMemoryUser("ada"), _nests_nothing)


def _nests_nothing(value: object) -> NoReturn:
    """Fail the test: a token that nests no other never hands one on."""
    raise AssertionError(f"Asked to keep or rebuild a nested token: {value!r}.")
