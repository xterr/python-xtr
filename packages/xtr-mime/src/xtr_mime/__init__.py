"""Email messages built in code and rendered to standard MIME.

A message is put together from addresses, headers, text and HTML bodies, attachments and
inline images; Python's own ``email`` package turns it into the bytes a mail server accepts,
and DKIM or S/MIME signs it when asked.

:class:`MimeTypes` maps MIME types to file extensions and back, and guesses a file's type —
from its content through :class:`MagicMimeTypeGuesser` where libmagic is installed, from its
extension otherwise.

The parts a body is made of — :class:`TextPart`, :class:`DataPart` and the multiparts — are
usable on their own too: :class:`FormDataPart` is the body of an HTTP form upload.

:class:`Email` is the builder; :class:`Message` is headers over any body part, and
:class:`RawMessage` bytes already rendered. :class:`MessageConverter` reads an email back out
of a message whose body an email could have built.

:class:`DefaultHtmlToTextConverter` writes the text alternative of an HTML body.
"""

from __future__ import annotations

from .address import Address
from .body_renderer_interface import BodyRendererInterface
from .crypto import DkimOptions, DkimSigner, SignedBody, SMimeEncrypter, SMimeSigner
from .draft_email import DraftEmail
from .email import Email
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
    FoldedHeader,
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
from .html_to_text_converter import DefaultHtmlToTextConverter, HtmlToTextConverterInterface
from .magic_mime_type_guesser import MagicMimeTypeGuesser
from .message import Message
from .message_converter import MessageConverter
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
    SMimePart,
    TextPart,
)
from .raw_message import RawMessage

__all__ = [
    "AbstractHeader",
    "AbstractMultipartPart",
    "AbstractPart",
    "Address",
    "AlternativePart",
    "BodyRendererInterface",
    "DataPart",
    "DateHeader",
    "DefaultHtmlToTextConverter",
    "DigestPart",
    "DkimOptions",
    "DkimSigner",
    "DraftEmail",
    "Email",
    "File",
    "FoldedHeader",
    "FormDataPart",
    "Group",
    "HeaderInterface",
    "HeaderKind",
    "Headers",
    "HtmlToTextConverterInterface",
    "IdentificationHeader",
    "InvalidArgumentError",
    "LogicError",
    "MagicMimeTypeGuesser",
    "MailboxHeader",
    "MailboxListHeader",
    "Message",
    "MessageConverter",
    "MessagePart",
    "MimeError",
    "MimeRuntimeError",
    "MimeTypeGuesserInterface",
    "MimeTypes",
    "MimeTypesInterface",
    "MixedPart",
    "ParameterizedHeader",
    "PathHeader",
    "RawMessage",
    "RelatedPart",
    "RfcComplianceError",
    "SMimeEncrypter",
    "SMimePart",
    "SMimeSigner",
    "SignedBody",
    "TextPart",
    "UnstructuredHeader",
]
