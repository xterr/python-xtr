from __future__ import annotations

from xtr_http_foundation.exception import HttpFoundationError, InvalidArgumentError


def test_it_derives_from_the_package_base() -> None:
    assert issubclass(InvalidArgumentError, HttpFoundationError)


def test_it_is_also_a_value_error() -> None:
    assert isinstance(InvalidArgumentError('"nope" is not a valid IP address.'), ValueError)


def test_it_carries_the_message_it_is_given() -> None:
    assert str(InvalidArgumentError('"nope" is not a valid IP address.')) == (
        '"nope" is not a valid IP address.'
    )
