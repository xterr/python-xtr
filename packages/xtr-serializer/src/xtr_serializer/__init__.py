"""Objects turned into JSON and back, exactly.

A serializer passes a value through a chain of normalizers, which turn objects into plain
data, and encoders, which turn plain data into text — and back again. What is read back
equals what was written: dataclasses, models, class hierarchies and dates keep their exact
types, and a value that cannot make the round trip is refused rather than changed.
"""

from __future__ import annotations

from .context import (
    Context,
    ContextBuilderInterface,
    JsonEncoderContextBuilder,
    PydanticNormalizerContextBuilder,
    SerializerContextBuilder,
)
from .decorator import discriminator_map, discriminator_name
from .encoder import (
    JSON_INDENT,
    DecoderInterface,
    EncoderInterface,
    JsonEncoder,
)
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
from .mapping import ClassDiscriminatorMapping
from .normalized_value import NormalizedValue
from .normalizer import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    COLLECT_DENORMALIZATION_ERRORS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
    DenormalizerAwareInterface,
    DenormalizerInterface,
    NormalizerAwareInterface,
    NormalizerInterface,
    PydanticNormalizer,
)
from .serializer import Serializer
from .serializer_aware_interface import SerializerAwareInterface
from .serializer_interface import SerializerInterface
from .supported_types import SupportedTypes
from .zoned_datetime import ZonedDateTime

__all__ = [
    "ALLOW_EXTRA_ATTRIBUTES",
    "ATTRIBUTES",
    "BY_ALIAS",
    "COLLECT_DENORMALIZATION_ERRORS",
    "FROM_ATTRIBUTES",
    "IGNORED_ATTRIBUTES",
    "JSON_INDENT",
    "POPULATE_BY_NAME",
    "SKIP_DEFAULT_VALUES",
    "SKIP_NULL_VALUES",
    "SKIP_UNSET_VALUES",
    "STRICT",
    "CircularReferenceError",
    "ClassDiscriminatorMapping",
    "Context",
    "ContextBuilderInterface",
    "DecoderInterface",
    "DenormalizerAwareInterface",
    "DenormalizerInterface",
    "EncoderInterface",
    "ExtraAttributesError",
    "InvalidArgumentError",
    "JsonEncoder",
    "JsonEncoderContextBuilder",
    "LogicError",
    "MappingError",
    "NormalizedValue",
    "NormalizerAwareInterface",
    "NormalizerInterface",
    "NotEncodableValueError",
    "NotNormalizableValueError",
    "PartialDenormalizationError",
    "PydanticNormalizer",
    "PydanticNormalizerContextBuilder",
    "Serializer",
    "SerializerAwareInterface",
    "SerializerContextBuilder",
    "SerializerError",
    "SerializerInterface",
    "SupportedTypes",
    "UnexpectedValueError",
    "UnsupportedFormatError",
    "ZonedDateTime",
    "discriminator_map",
    "discriminator_name",
]
