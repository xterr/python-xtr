"""The authentication-method badge records the methods an attempt verified."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http.authenticator.passport.badge.authentication_method_badge import (
    AuthenticationMethodBadge,
)


def test_it_keeps_the_methods_in_the_order_given() -> None:
    badge = AuthenticationMethodBadge("password", "oidc")

    assert badge.get_methods() == ("password", "oidc")


def test_it_deduplicates_repeated_methods() -> None:
    badge = AuthenticationMethodBadge("password", "oidc", "password")

    assert badge.get_methods() == ("password", "oidc")


def test_it_refuses_to_name_no_method() -> None:
    with pytest.raises(InvalidArgumentError):
        _ = AuthenticationMethodBadge()


def test_it_is_resolved_from_the_start() -> None:
    badge = AuthenticationMethodBadge("password")

    assert badge.is_resolved() is True
