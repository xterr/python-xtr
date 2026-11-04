from __future__ import annotations

from xtr_mime.exception import MimeError


def test_it_is_an_exception() -> None:
    assert issubclass(MimeError, Exception)
