from __future__ import annotations

from xtr_mime.exception import InvalidArgumentError, MimeError


def test_it_derives_from_the_package_base_and_is_a_value_error() -> None:
    assert issubclass(InvalidArgumentError, MimeError)
    assert issubclass(InvalidArgumentError, ValueError)
