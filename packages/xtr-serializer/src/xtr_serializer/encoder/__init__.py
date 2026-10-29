"""Encoders write plain data as text, and decoders read text back into plain data.

The half of a serializer that knows the formats. Also here: the JSON encoder and the context
key it reads.
"""

from __future__ import annotations

from .decoder_interface import DecoderInterface
from .encoder_interface import EncoderInterface
from .json_encoder import JsonEncoder
from .json_encoder_keys import JSON_INDENT

__all__ = [
    "JSON_INDENT",
    "DecoderInterface",
    "EncoderInterface",
    "JsonEncoder",
]
