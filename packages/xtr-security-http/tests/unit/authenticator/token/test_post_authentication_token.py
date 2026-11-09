"""The post-authentication token remembers the firewall that made it."""

from __future__ import annotations

from typing import NoReturn

import pytest
from xtr_security_core.authentication.token.token_interface import TokenInterface
from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import InMemoryUser

from xtr_security_http.authenticator.token import PostAuthenticationToken


def _nests_nothing(value: object) -> NoReturn:
    """Fail the test: a token that nests no other never hands one on."""
    raise AssertionError(f"Asked to keep or rebuild a nested token: {value!r}.")


def test_it_inherits_the_token_interface() -> None:
    assert TokenInterface in PostAuthenticationToken.__mro__


def test_an_empty_firewall_name_is_refused() -> None:
    with pytest.raises(InvalidArgumentError, match="firewall_name"):
        _ = PostAuthenticationToken(InMemoryUser("alice"), "", ["ROLE_USER"])


def test_it_keeps_the_firewall_user_and_roles() -> None:
    user = InMemoryUser("alice")
    token = PostAuthenticationToken(user, "api", ["ROLE_USER"])

    assert token.get_firewall_name() == "api"
    assert token.get_role_names() == ("ROLE_USER",)
    assert token.get_user() is user


def test_a_session_keeps_its_firewall_beside_its_roles_and_attributes() -> None:
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    token.set_attribute("oidc_id_token", "header.payload.signature")

    assert token.to_session(_nests_nothing) == {
        "roles": ["ROLE_USER"],
        "attributes": {"oidc_id_token": "header.payload.signature"},
        "firewall": "api",
    }


def test_it_is_rebuilt_from_a_session_as_the_token_it_was() -> None:
    token = PostAuthenticationToken(InMemoryUser("alice"), "api", ["ROLE_USER"])
    token.set_attribute("oidc_access_token_expires_at", 1_700_000_000)
    user = InMemoryUser("alice")

    rebuilt = PostAuthenticationToken.from_session(
        token.to_session(_nests_nothing),
        user,
        _nests_nothing,
    )

    assert type(rebuilt) is PostAuthenticationToken
    assert rebuilt.get_user() is user
    assert rebuilt.get_firewall_name() == "api"
    assert rebuilt.get_role_names() == ("ROLE_USER",)
    assert dict(rebuilt.get_attributes()) == {"oidc_access_token_expires_at": 1_700_000_000}


@pytest.mark.parametrize("firewall", [None, "", ["api"]])
def test_a_session_state_without_a_firewall_is_refused(firewall: object) -> None:
    state: dict[str, object] = {"roles": [], "attributes": {}, "firewall": firewall}

    with pytest.raises(InvalidArgumentError, match="firewall"):
        _ = PostAuthenticationToken.from_session(state, InMemoryUser("alice"), _nests_nothing)
