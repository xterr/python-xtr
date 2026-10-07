"""The challenge helper quotes an auth-param as an RFC 7235 quoted-string."""

from __future__ import annotations

import pytest
from xtr_security_core.exception import InvalidArgumentError

from xtr_security_http._challenge import quote_auth_param


def test_it_wraps_a_plain_value_in_quotes() -> None:
    assert quote_auth_param("api") == '"api"'


def test_it_escapes_a_double_quote() -> None:
    assert quote_auth_param('a"b') == '"a\\"b"'


def test_it_escapes_a_backslash_before_a_quote() -> None:
    assert quote_auth_param("a\\b") == '"a\\\\b"'


@pytest.mark.parametrize("value", ["a\x00b", "a\x1fb", "a\x7fb", "a\rb", "a\nb"])
def test_it_refuses_a_control_character(value: str) -> None:
    with pytest.raises(InvalidArgumentError):
        _ = quote_auth_param(value)


def test_it_keeps_a_space_and_a_tab() -> None:
    assert quote_auth_param("a b\tc") == '"a b\tc"'
