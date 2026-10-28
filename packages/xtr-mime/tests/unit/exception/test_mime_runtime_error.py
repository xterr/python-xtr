from __future__ import annotations

from xtr_mime.exception import MimeError, MimeRuntimeError


def test_it_derives_from_the_package_base_and_is_a_runtime_error() -> None:
    assert issubclass(MimeRuntimeError, MimeError)
    assert issubclass(MimeRuntimeError, RuntimeError)
