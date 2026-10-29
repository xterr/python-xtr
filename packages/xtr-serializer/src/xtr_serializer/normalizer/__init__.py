"""Normalizers turn values into plain data, and denormalizers turn plain data back.

The half of a serializer that knows the types. Also here: the pydantic normalizer, which handles
every type pydantic has a schema for, the context keys it reads, and the one asking a
denormalizer for every error at once.
"""

from __future__ import annotations

from .denormalizer_aware_interface import DenormalizerAwareInterface
from .denormalizer_interface import COLLECT_DENORMALIZATION_ERRORS, DenormalizerInterface
from .normalizer_aware_interface import NormalizerAwareInterface
from .normalizer_interface import NormalizerInterface
from .pydantic_normalizer import PydanticNormalizer
from .pydantic_normalizer_keys import (
    ALLOW_EXTRA_ATTRIBUTES,
    ATTRIBUTES,
    BY_ALIAS,
    FROM_ATTRIBUTES,
    IGNORED_ATTRIBUTES,
    POPULATE_BY_NAME,
    SKIP_DEFAULT_VALUES,
    SKIP_NULL_VALUES,
    SKIP_UNSET_VALUES,
    STRICT,
)

__all__ = [
    "ALLOW_EXTRA_ATTRIBUTES",
    "ATTRIBUTES",
    "BY_ALIAS",
    "COLLECT_DENORMALIZATION_ERRORS",
    "FROM_ATTRIBUTES",
    "IGNORED_ATTRIBUTES",
    "POPULATE_BY_NAME",
    "SKIP_DEFAULT_VALUES",
    "SKIP_NULL_VALUES",
    "SKIP_UNSET_VALUES",
    "STRICT",
    "DenormalizerAwareInterface",
    "DenormalizerInterface",
    "NormalizerAwareInterface",
    "NormalizerInterface",
    "PydanticNormalizer",
]
