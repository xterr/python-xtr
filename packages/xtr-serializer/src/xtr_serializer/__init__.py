"""Objects turned into JSON and back, exactly.

A serializer passes a value through a chain of normalizers, which turn objects into plain
data, and encoders, which turn plain data into text — and back again. What is read back
equals what was written: dataclasses, models, class hierarchies and dates keep their exact
types, and a value that cannot make the round trip is refused rather than changed.
"""

from __future__ import annotations

from .exception import (
    CircularReferenceError,
    ExtraAttributesError,
    InvalidArgumentError,
    LogicError,
    MappingError,
    NotEncodableValueError,
    NotNormalizableValueError,
    PartialDenormalizationError,
    SerializerError,
    UnexpectedValueError,
    UnsupportedFormatError,
)

__all__ = [
    "CircularReferenceError",
    "ExtraAttributesError",
    "InvalidArgumentError",
    "LogicError",
    "MappingError",
    "NotEncodableValueError",
    "NotNormalizableValueError",
    "PartialDenormalizationError",
    "SerializerError",
    "UnexpectedValueError",
    "UnsupportedFormatError",
]
