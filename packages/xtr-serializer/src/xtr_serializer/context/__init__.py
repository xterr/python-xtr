"""The options a call hands the serializer, and the builders that put them together.

A context is a plain mapping every step of a call reads from; a builder sets its options
through typed methods, one builder for each step that has options of its own.
"""

from __future__ import annotations

from .context import Context
from .context_builder_interface import ContextBuilderInterface
from .encoder import JsonEncoderContextBuilder
from .normalizer import PydanticNormalizerContextBuilder
from .serializer_context_builder import SerializerContextBuilder

__all__ = [
    "Context",
    "ContextBuilderInterface",
    "JsonEncoderContextBuilder",
    "PydanticNormalizerContextBuilder",
    "SerializerContextBuilder",
]
