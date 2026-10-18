"""The event that decides whether a refreshed user logs its token out."""

from __future__ import annotations

from xtr_security_core.exception import AuthenticationError
from xtr_security_core.user.in_memory_user import InMemoryUser

from xtr_security_http.authenticator.token.post_authentication_token import PostAuthenticationToken
from xtr_security_http.event.check_refreshed_user_event import CheckRefreshedUserEvent


def _event(user_changed: bool = False) -> CheckRefreshedUserEvent:
    user = InMemoryUser("ada")
    token = PostAuthenticationToken(user, "main", roles=())
    return CheckRefreshedUserEvent(token, user, InMemoryUser("ada"), user_changed)


def test_it_carries_the_token_and_both_users() -> None:
    token = PostAuthenticationToken(InMemoryUser("ada"), "main", roles=())
    original = InMemoryUser("ada", password="stored")  # noqa: S106 -- a test fixture password, not a secret
    refreshed = InMemoryUser("ada", password="reloaded")  # noqa: S106 -- a test fixture password, not a secret
    event = CheckRefreshedUserEvent(token, original, refreshed)

    assert event.get_token() is token
    assert event.get_original_user() is original
    assert event.get_refreshed_user() is refreshed


def test_it_is_seeded_with_the_builtin_verdict() -> None:
    assert _event(user_changed=True).is_user_changed() is True
    assert _event().is_user_changed() is False


def test_a_listener_sets_the_verdict_with_its_reason() -> None:
    event = _event()
    reason = AuthenticationError("The account was disabled.")

    event.set_user_changed(True, reason)  # noqa: FBT003 -- the event's own signature takes the verdict positionally

    assert event.is_user_changed() is True
    assert event.get_exception() is reason


def test_a_verdict_kept_without_a_reason_keeps_the_earlier_reason() -> None:
    event = _event()
    reason = AuthenticationError("The account was disabled.")
    event.set_user_changed(True, reason)  # noqa: FBT003 -- the event's own signature takes the verdict positionally

    event.set_user_changed(True)

    assert event.is_user_changed() is True
    assert event.get_exception() is reason


def test_a_cleared_verdict_clears_the_reason_with_it() -> None:
    event = _event(user_changed=True)
    event.set_user_changed(True, AuthenticationError("The account was disabled."))  # noqa: FBT003 -- the event's own signature takes the verdict positionally

    event.set_user_changed(False)

    assert event.is_user_changed() is False
    assert event.get_exception() is None
