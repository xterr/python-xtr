"""Every error this package raises, each deriving from :class:`SerializerError`.

One ``except SerializerError`` catches them all; a narrower one handles a single
cause. The errors that describe a value — :class:`NotNormalizableValueError` and
its subclasses, :class:`PartialDenormalizationError` and :class:`UnsupportedFormatError`
— keep what went wrong as typed attributes and compose their messages from those,
so the message never repeats the value. The others take a plain message from the
code that raises them, and are only as safe as that code. None of them takes the
value itself, but a traceback renders the chained exception too: raise these
errors without ``from`` on an exception that carries the value.
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
