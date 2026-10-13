"""The OAuth2 user carries the claims of a token introspection response."""

from __future__ import annotations

import pytest

from xtr_security_core.exception import InvalidArgumentError
from xtr_security_core.user import OAuth2User, UserInterface


def test_it_inherits_the_user_interface() -> None:
    assert UserInterface in OAuth2User.__mro__


def test_it_is_identified_by_the_sub_first() -> None:
    assert OAuth2User(sub="alice", username="al").get_user_identifier() == "alice"


def test_without_a_sub_it_is_identified_by_the_username() -> None:
    assert OAuth2User(username="al").get_user_identifier() == "al"


@pytest.mark.parametrize(("sub", "username"), [(None, None), ("", ""), (None, "")])
def test_neither_a_sub_nor_a_username_is_refused(sub: str | None, username: str | None) -> None:
    with pytest.raises(InvalidArgumentError, match='"sub" or "username" must be provided'):
        _ = OAuth2User(sub=sub, username=username)


def test_it_holds_role_user_by_default() -> None:
    assert OAuth2User(sub="alice").get_roles() == ("ROLE_USER",)
    assert OAuth2User(roles=["ROLE_ADMIN"], sub="alice").get_roles() == ("ROLE_ADMIN",)


def test_it_carries_the_standard_claims() -> None:
    user = OAuth2User(
        scope="read write",
        client_id="svc",
        username="al",
        token_type="Bearer",  # noqa: S106 -- a token type name, not a secret
        exp=3,
        iat=1,
        nbf=2,
        sub="alice",
        aud=["api", "web"],
        iss="https://issuer.example.test",
        jti="t-1",
    )

    assert (
        user.scope,
        user.client_id,
        user.username,
        user.token_type,
        user.exp,
        user.iat,
        user.nbf,
        user.sub,
        user.aud,
        user.iss,
        user.jti,
    ) == (
        "read write",
        "svc",
        "al",
        "Bearer",
        3,
        1,
        2,
        "alice",
        ["api", "web"],
        "https://issuer.example.test",
        "t-1",
    )


def test_other_members_become_additional_claims() -> None:
    assert dict(OAuth2User(sub="alice", tenant="acme").additional_claims) == {"tenant": "acme"}


def test_an_additional_claims_keyword_is_taken_as_the_claims_themselves() -> None:
    user = OAuth2User(sub="alice", additional_claims={"tenant": "acme"})

    assert dict(user.additional_claims) == {"tenant": "acme"}
