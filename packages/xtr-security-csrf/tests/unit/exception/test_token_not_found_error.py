"""The error an empty id raises."""

from __future__ import annotations

from xtr_security_csrf import CsrfError, TokenNotFoundError


def test_it_derives_from_the_package_root() -> None:
    assert issubclass(TokenNotFoundError, CsrfError)


def test_it_carries_the_id_no_token_is_stored_under() -> None:
    error = TokenNotFoundError("foo")

    assert error.get_token_id() == "foo"


def test_its_message_names_the_id() -> None:
    error = TokenNotFoundError("foo")

    assert "foo" in str(error)
    assert "does not exist" in str(error)
