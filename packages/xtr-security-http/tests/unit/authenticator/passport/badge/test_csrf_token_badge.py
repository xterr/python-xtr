"""The CSRF badge carries a presented token until the listener checks it."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.csrf_token_badge import CsrfTokenBadge


def test_it_carries_the_identifier_and_the_presented_token() -> None:
    badge = CsrfTokenBadge("authenticate", "a-token")

    assert badge.get_csrf_token_id() == "authenticate"
    assert badge.get_csrf_token() == "a-token"


def test_it_accepts_a_request_without_a_token() -> None:
    badge = CsrfTokenBadge("authenticate", None)

    assert badge.get_csrf_token() is None


def test_it_is_unresolved_until_marked() -> None:
    badge = CsrfTokenBadge("authenticate", "a-token")

    assert badge.is_resolved() is False

    badge.mark_resolved()

    assert badge.is_resolved() is True
