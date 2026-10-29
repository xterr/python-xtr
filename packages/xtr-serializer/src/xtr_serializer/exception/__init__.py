"""Every error this package raises, each deriving from :class:`SerializerError`.

One ``except SerializerError`` catches them all; a narrower one handles a single
cause. Each error carries what went wrong as typed attributes and puts its
message together from them — where in the value the problem is and which types
were involved — so none of them repeats the value itself, which may be a secret.
"""

from __future__ import annotations

from .circular_reference_error import CircularReferenceError
from .extra_attributes_error import ExtraAttributesError
from .invalid_argument_error import InvalidArgumentError
from .logic_error import LogicError
from .mapping_error import MappingError
from .not_encodable_value_error import NotEncodableValueError
from .not_normalizable_value_error import NotNormalizableValueError
from .partial_denormalization_error import PartialDenormalizationError
from .serializer_error import SerializerError
from .unexpected_value_error import UnexpectedValueError
from .unsupported_format_error import UnsupportedFormatError

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
