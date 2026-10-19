"""The staged remember-me cookie, and the header value it renders."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from xtr_security_http.remember_me import RememberMeCookie

pytestmark = pytest.mark.anyio


def test_a_set_cookie_renders_the_value_with_its_expiry_and_attributes() -> None:
    expires = datetime.now(UTC) + timedelta(days=365)

    value = RememberMeCookie("REMEMBERME", "the-value", expires=expires).header_value()

    assert value.startswith("REMEMBERME=the-value;")
    assert "path=/" in value
    assert "httponly" in value
    assert "expires=" in value
    assert "Max-Age=" in value


def test_a_set_cookie_repeats_the_attributes_it_was_given() -> None:
    expires = datetime.now(UTC) + timedelta(days=365)

    value = RememberMeCookie(
        "REMEMBERME",
        "the-value",
        expires=expires,
        path="/login",
        domain="example.com",
        secure=True,
        samesite="strict",
    ).header_value()

    assert "path=/login" in value
    assert "domain=example.com" in value
    assert "secure" in value
    assert "samesite=strict" in value


def test_a_cleared_cookie_renders_the_form_a_browser_drops() -> None:
    value = RememberMeCookie("REMEMBERME", None).header_value()

    assert value.startswith("REMEMBERME=deleted;")
    assert "Max-Age=0" in value
    assert "path=/" in value


def test_a_cleared_cookie_repeats_the_attributes_the_set_one_carried() -> None:
    value = RememberMeCookie(
        "REMEMBERME",
        None,
        path="/login",
        domain="example.com",
        secure=True,
        samesite="strict",
    ).header_value()

    assert "path=/login" in value
    assert "domain=example.com" in value
    assert "secure" in value
    assert "samesite=strict" in value
