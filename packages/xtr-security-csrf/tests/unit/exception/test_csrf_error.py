"""The root of everything this library raises."""

from __future__ import annotations

import pytest

from xtr_security_csrf import CsrfError, InvalidArgumentError, TokenNotFoundError


def test_it_is_an_exception() -> None:
    assert issubclass(CsrfError, Exception)


def test_every_error_this_library_raises_derives_from_it() -> None:
    assert issubclass(InvalidArgumentError, CsrfError)
    assert issubclass(TokenNotFoundError, CsrfError)


def test_one_except_catches_whatever_a_storage_raises() -> None:
    with pytest.raises(CsrfError) as raised:
        raise TokenNotFoundError("foo")

    assert isinstance(raised.value, TokenNotFoundError)
