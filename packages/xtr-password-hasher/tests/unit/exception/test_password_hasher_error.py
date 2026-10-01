from __future__ import annotations

import pytest

from xtr_password_hasher import (
    InvalidArgumentError,
    InvalidPasswordError,
    PasswordHasherError,
    UnknownPasswordHasherError,
)


def test_it_is_an_exception() -> None:
    assert issubclass(PasswordHasherError, Exception)


def test_every_error_derives_from_it() -> None:
    assert issubclass(InvalidArgumentError, PasswordHasherError)
    assert issubclass(InvalidPasswordError, PasswordHasherError)
    assert issubclass(UnknownPasswordHasherError, PasswordHasherError)


def test_catching_the_base_catches_a_subclass() -> None:
    with pytest.raises(PasswordHasherError) as caught:
        raise InvalidArgumentError("nope")

    assert isinstance(caught.value, InvalidArgumentError)
