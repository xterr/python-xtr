"""The xtr-dependency-injection bundle for xtr-serializer."""

from __future__ import annotations

from .named_serializer_config import NamedSerializerConfig
from .serializer_bundle import SerializerBundle
from .serializer_config import ALL_SERIALIZERS, DEFAULT_SERIALIZER, SerializerConfig
from .serializer_pass import ENCODER_TAG, NORMALIZER_TAG, SerializerPass

__all__ = [
    "ALL_SERIALIZERS",
    "DEFAULT_SERIALIZER",
    "ENCODER_TAG",
    "NORMALIZER_TAG",
    "NamedSerializerConfig",
    "SerializerBundle",
    "SerializerConfig",
    "SerializerPass",
]
