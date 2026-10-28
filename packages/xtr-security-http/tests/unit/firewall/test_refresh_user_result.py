"""The outcome of a user-refresh attempt."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.firewall.refresh_user_result import RefreshUserResult


def test_a_held_refresh_carries_the_token() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", roles=())
    result = RefreshUserResult(token)

    assert result.token is token
    assert result.deauthentication_reason is None
    assert result.provider_classes == ()
    assert result.exception is None


def test_a_deauthentication_carries_its_reason_and_its_providers() -> None:
    reason = AuthenticationError("The account was disabled.")

    result = RefreshUserResult(None, "the user has changed", (dict,), reason)

    assert result.token is None
    assert result.deauthentication_reason == "the user has changed"
    assert result.provider_classes == (dict,)
    assert result.exception is reason
