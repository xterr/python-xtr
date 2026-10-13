from __future__ import annotations

import pytest

from xtr_http_client_contracts import (
    HttpClientError,
    HttpError,
    InvalidArgumentError,
    TransportError,
)


def test_it_is_a_transport_error() -> None:
    assert issubclass(InvalidArgumentError, TransportError)


def test_it_is_also_a_value_error() -> None:
    assert issubclass(InvalidArgumentError, ValueError)


def test_it_is_never_an_http_error() -> None:
    assert issubclass(InvalidArgumentError, HttpClientError)
    assert not issubclass(InvalidArgumentError, HttpError)


def test_code_already_guarding_its_arguments_catches_it() -> None:
    with pytest.raises(ValueError, match=r'Unsupported option "foo"\.'):
        raise InvalidArgumentError('Unsupported option "foo".')


def test_it_keeps_the_reason_it_was_given() -> None:
    error = InvalidArgumentError('Unsupported option "foo".')

    assert error.reason == 'Unsupported option "foo".'
    assert str(error) == 'Unsupported option "foo".'
