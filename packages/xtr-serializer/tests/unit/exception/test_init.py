"""The errors module exports every error the package raises, and the package exports them too."""

from __future__ import annotations

import xtr_serializer
from xtr_serializer import exception
from xtr_serializer.exception import SerializerError

_EXPORTED: tuple[type[SerializerError], ...] = (
    exception.CircularReferenceError,
    exception.ExtraAttributesError,
    exception.InvalidArgumentError,
    exception.LogicError,
    exception.MappingError,
    exception.NotEncodableValueError,
    exception.NotNormalizableValueError,
    exception.PartialDenormalizationError,
    exception.SerializerError,
    exception.UnexpectedValueError,
    exception.UnsupportedFormatError,
)


def test_every_exported_name_resolves() -> None:
    assert [name for name in exception.__all__ if not hasattr(exception, name)] == []


def test_it_exports_every_error_this_library_raises() -> None:
    assert sorted(exception.__all__) == sorted(error.__name__ for error in _EXPORTED)


def test_every_error_it_exports_derives_from_the_base() -> None:
    assert [error for error in _EXPORTED if not issubclass(error, SerializerError)] == []


def test_the_package_exports_every_error_too() -> None:
    assert [name for name in exception.__all__ if name not in xtr_serializer.__all__] == []
