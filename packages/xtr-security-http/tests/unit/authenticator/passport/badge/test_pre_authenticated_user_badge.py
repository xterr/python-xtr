"""The pre-authenticated badge resolves from the moment it exists."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.pre_authenticated_user_badge import (
    PreAuthenticatedUserBadge,
)


def test_it_is_resolved() -> None:
    assert PreAuthenticatedUserBadge().is_resolved() is True
