"""The remember-me badge marks an authentication a cookie may outlive."""

from __future__ import annotations

from xtr_security_http.authenticator.passport.badge.remember_me_badge import RememberMeBadge


def test_it_starts_disabled() -> None:
    badge = RememberMeBadge()

    assert badge.is_enabled() is False


def test_enabling_and_disabling_answer_self() -> None:
    badge = RememberMeBadge()

    assert badge.enable() is badge
    assert badge.is_enabled() is True

    assert badge.disable() is badge
    assert badge.is_enabled() is False


def test_it_carries_the_parameters_it_was_given() -> None:
    badge = RememberMeBadge({"remember_me_parameter": "remember-me"})

    assert badge.get_parameters() == {"remember_me_parameter": "remember-me"}


def test_it_is_resolved_from_the_start() -> None:
    badge = RememberMeBadge()

    assert badge.is_resolved() is True
