"""Build a header of a given kind from values whose type is only known at run time.

:meth:`Headers.add_header` and :meth:`Headers.set_header_body` take a body as ``object``;
this checks it against what the kind of header holds and builds that header.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Literal, TypeAlias

from xtr_mime.address import Address
from xtr_mime.exception import InvalidArgumentError
from xtr_mime.group import Group

from .date_header import DateHeader
from .identification_header import IdentificationHeader
from .mailbox_header import MailboxHeader
from .mailbox_list_header import MailboxListHeader
from .parameterized_header import ParameterizedHeader
from .path_header import PathHeader
from .unstructured_header import UnstructuredHeader

if TYPE_CHECKING:
    from .header_interface import HeaderInterface

__all__ = ["HeaderKind", "build_header"]

HeaderKind: TypeAlias = Literal[
    "text", "parameterized", "mailbox", "mailbox_list", "date", "id", "path"
]
"""Which kind of header :meth:`Headers.set_header_body` adds when the header is not there."""


def build_header(kind: HeaderKind, name: str, values: list[object]) -> HeaderInterface:
    """Build a ``kind`` header named ``name`` from ``values``.

    An address list or identifiers take every value, the first spread when it is a list or a
    tuple; any other kind takes exactly one.

    Raises:
        InvalidArgumentError: A value is not of the type the header holds.
    """
    match kind:
        case "mailbox_list":
            given = _spread(values)
            entries = [entry for entry in given if isinstance(entry, Address | Group | str)]
            _check(name, len(entries) == len(given), "addresses and groups", values)
            return MailboxListHeader(name, MailboxListHeader.create_address_list(entries))
        case "id":
            given = _spread(values)
            ids = [identifier for identifier in given if isinstance(identifier, str)]
            _check(name, len(ids) == len(given), "identifiers", values)
            return IdentificationHeader(name, ids)
        case _:
            _check(name, len(values) == 1, "one value", values)
            return _build_single(kind, name, values[0])


def _build_single(kind: HeaderKind, name: str, value: object) -> HeaderInterface:
    match kind, value:
        case ("text", str()):
            return UnstructuredHeader(name, value)
        case ("parameterized", str()):
            return ParameterizedHeader(name, value)
        case ("mailbox", Address() | str()):
            return MailboxHeader(name, Address.create(value))
        case ("path", Address() | str()):
            return PathHeader(name, value if isinstance(value, Address) else Address(value))
        case ("date", datetime()):
            return DateHeader(name, value)
        case _:
            raise InvalidArgumentError(f'The "{name}" header takes a {kind} value (got {value!r}).')


def _spread(values: list[object]) -> list[object]:
    """Spread the first value when it is a sequence: ``add_header("To", [a, b], c)``."""
    first, *rest = values
    return [*first, *rest] if isinstance(first, list | tuple) else values


def _check(name: str, valid: bool, expected: str, value: object) -> None:
    if not valid:
        raise InvalidArgumentError(f'The "{name}" header takes {expected} (got {value!r}).')
