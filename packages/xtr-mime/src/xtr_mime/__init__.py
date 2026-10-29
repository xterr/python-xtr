"""Email messages built in code and rendered to standard MIME.

A message is put together from addresses, headers, text and HTML bodies, attachments and
inline images; Python's own ``email`` package turns it into the bytes a mail server accepts,
and DKIM or S/MIME signs it when asked.

:class:`MimeTypes` maps MIME types to file extensions and back, and guesses a file's type —
from its content through :class:`MagicMimeTypeGuesser` where libmagic is installed, from its
extension otherwise.

The parts a body is made of — :class:`TextPart`, :class:`DataPart` and the multiparts — are
usable on their own too: :class:`FormDataPart` is the body of an HTTP form upload.
"""

from __future__ import annotations

from .address import Address
from .exception import (
    InvalidArgumentError,
    LogicError,
    MimeError,
    MimeRuntimeError,
    RfcComplianceError,
)
from .group import Group
from .header import (
    AbstractHeader,
    DateHeader,
    HeaderInterface,
    HeaderKind,
    Headers,
    IdentificationHeader,
    MailboxHeader,
    MailboxListHeader,
    ParameterizedHeader,
    PathHeader,
    UnstructuredHeader,
)
from .magic_mime_type_guesser import MagicMimeTypeGuesser
from .mime_type_guesser_interface import MimeTypeGuesserInterface
from .mime_types import MimeTypes
from .mime_types_interface import MimeTypesInterface
from .part import (
    AbstractMultipartPart,
    AbstractPart,
    AlternativePart,
    DataPart,
    DigestPart,
    File,
    FormDataPart,
    MessagePart,
    MixedPart,
    RelatedPart,
    TextPart,
)

__all__ = [
    "AbstractHeader",
    "AbstractMultipartPart",
    "AbstractPart",
    "Address",
    "AlternativePart",
    "DataPart",
    "DateHeader",
    "DigestPart",
    "File",
    "FormDataPart",
    "Group",
    "HeaderInterface",
    "HeaderKind",
    "Headers",
    "IdentificationHeader",
    "InvalidArgumentError",
    "LogicError",
    "MagicMimeTypeGuesser",
    "MailboxHeader",
    "MailboxListHeader",
    "MessagePart",
    "MimeError",
    "MimeRuntimeError",
    "MimeTypeGuesserInterface",
    "MimeTypes",
    "MimeTypesInterface",
    "MixedPart",
    "ParameterizedHeader",
    "PathHeader",
    "RelatedPart",
    "RfcComplianceError",
    "TextPart",
    "UnstructuredHeader",
]
