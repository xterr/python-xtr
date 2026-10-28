"""The logout configuration validates its fields."""

from __future__ import annotations

import pytest
from xtr_security_http import ClearedCookie

from xtr_security.bundle import LogoutConfig
from xtr_security.exception import InvalidConfigurationError


def test_a_logout_defaults_to_the_documented_choices() -> None:
    logout = LogoutConfig()

    assert logout.path == "/logout"
    assert logout.target_path == "/"
    assert logout.enable_csrf is False
    assert logout.csrf_parameter == "_csrf_token"
    assert logout.csrf_token_id == "logout"
    assert logout.clear_site_data is None
    assert dict(logout.cookie_clearing) == {}
    assert logout.invalidate_session is True
    assert logout.clear_csrf_tokens is False


def test_a_logout_needs_its_path() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = LogoutConfig(path="")


def test_a_logout_needs_its_target_path() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = LogoutConfig(target_path="")


def test_a_logout_refuses_empty_site_data_directives() -> None:
    with pytest.raises(InvalidConfigurationError):
        _ = LogoutConfig(clear_site_data=())


def test_a_logout_keeps_its_fields() -> None:
    cookies = {"session": ClearedCookie(path="/account")}
    logout = LogoutConfig(
        path="/sign-out",
        target_path="/bye",
        csrf_parameter="token",
        csrf_token_id="sign-out",
        clear_site_data=("cache", "storage"),
        cookie_clearing=cookies,
        invalidate_session=False,
    )

    assert logout.path == "/sign-out"
    assert logout.target_path == "/bye"
    assert logout.csrf_parameter == "token"
    assert logout.csrf_token_id == "sign-out"
    assert tuple(logout.clear_site_data or ()) == ("cache", "storage")
    assert logout.cookie_clearing is cookies
    assert logout.invalidate_session is False
