"""Message headers: one class per kind of body, and :class:`Headers` to hold them in order.

Each header keeps its body typed — text, an address, an address list, a date, identifiers,
a value with parameters — and is written by the engine, which encodes and folds it.
"""

from __future__ import annotations

from .abstract_header import AbstractHeader
from .date_header import DateHeader
from .folded_header import FoldedHeader
from .header_interface import HeaderInterface
from .headers import HeaderKind, Headers
from .identification_header import IdentificationHeader
from .mailbox_header import MailboxHeader
from .mailbox_list_header import MailboxListHeader
from .parameterized_header import ParameterizedHeader
from .path_header import PathHeader
from .unstructured_header import UnstructuredHeader

__all__ = [
    "AbstractHeader",
    "DateHeader",
    "FoldedHeader",
    "HeaderInterface",
    "HeaderKind",
    "Headers",
    "IdentificationHeader",
    "MailboxHeader",
    "MailboxListHeader",
    "ParameterizedHeader",
    "PathHeader",
    "UnstructuredHeader",
]
