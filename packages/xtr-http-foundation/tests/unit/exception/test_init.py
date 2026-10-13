from __future__ import annotations

from xtr_http_foundation import exception
from xtr_http_foundation.exception import HttpFoundationError

_EXPORTED: tuple[type[HttpFoundationError], ...] = (
    exception.HttpFoundationError,
    exception.InvalidArgumentError,
)


def test_every_exported_name_resolves() -> None:
    assert [name for name in exception.__all__ if not hasattr(exception, name)] == []


def test_it_exports_every_error_this_library_raises() -> None:
    assert sorted(exception.__all__) == sorted(error.__name__ for error in _EXPORTED)


def test_every_error_it_exports_derives_from_the_base() -> None:
    assert [error for error in _EXPORTED if not issubclass(error, HttpFoundationError)] == []
