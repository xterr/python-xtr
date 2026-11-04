"""MIME parts: the leaves a message is made of, and the multiparts that hold them.

A part keeps its body and the headers the caller adds; the engine renders it, with the
headers the part prepares — its media type, charset, transfer encoding, disposition — on a
copy, so rendering never changes it. A body held in a :class:`File` is read only then.
"""

from __future__ import annotations

from .abstract_multipart_part import AbstractMultipartPart
from .abstract_part import AbstractPart
from .data_part import DataPart
from .file import File
from .message_part import MessagePart
from .multipart import AlternativePart, DigestPart, FormDataPart, MixedPart, RelatedPart
from .s_mime_part import SMimePart
from .text_part import TextPart

__all__ = [
    "AbstractMultipartPart",
    "AbstractPart",
    "AlternativePart",
    "DataPart",
    "DigestPart",
    "File",
    "FormDataPart",
    "MessagePart",
    "MixedPart",
    "RelatedPart",
    "SMimePart",
    "TextPart",
]
