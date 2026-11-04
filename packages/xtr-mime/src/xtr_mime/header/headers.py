"""The headers of a message or a part, in order, with the rules a message holds them to."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar, Final, final

from xtr_mime._error_text import escaped
from xtr_mime.address import Address
from xtr_mime.exception import LogicError

from ._header_builder import HeaderKind, build_header
from .abstract_header import AbstractHeader
from .date_header import DateHeader
from .identification_header import IdentificationHeader
from .mailbox_header import MailboxHeader
from .mailbox_list_header import MailboxListHeader
from .parameterized_header import ParameterizedHeader
from .path_header import PathHeader
from .unstructured_header import UnstructuredHeader

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator, Mapping
    from datetime import datetime
    from typing import Self

    from xtr_mime.group import Group

    from .header_interface import HeaderInterface

__all__ = ["HeaderKind", "Headers"]

# RFC 5322, 3.6: a message carries each of these at most once.
_UNIQUE_HEADERS: Final = frozenset(
    {"date", "from", "sender", "reply-to", "to", "cc", "bcc"}
    | {"message-id", "in-reply-to", "references", "subject"}
)

# The class a header of each name must be, and the kind add_header builds for it. In-Reply-To
# and References take text too, so that a reply can quote an original Message-ID that is not
# a valid identifier.
_HEADER_CLASSES: Final[Mapping[str, tuple[HeaderKind, tuple[type[HeaderInterface], ...]]]] = {
    "date": ("date", (DateHeader,)),
    "from": ("mailbox_list", (MailboxListHeader,)),
    "sender": ("mailbox", (MailboxHeader,)),
    "reply-to": ("mailbox_list", (MailboxListHeader,)),
    "to": ("mailbox_list", (MailboxListHeader,)),
    "cc": ("mailbox_list", (MailboxListHeader,)),
    "bcc": ("mailbox_list", (MailboxListHeader,)),
    "message-id": ("id", (IdentificationHeader,)),
    "in-reply-to": ("text", (UnstructuredHeader, IdentificationHeader)),
    "references": ("text", (UnstructuredHeader, IdentificationHeader)),
    "return-path": ("path", (PathHeader,)),
}


@final
class Headers:
    """Headers in the order they were added, looked up by name whatever its case.

    Adding checks two rules: a header named in the class map must be of its class (a From is
    a list of addresses, never text), and a header a message carries once cannot be added
    twice.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_headers", "_line_length")

    def __init__(self, *headers: HeaderInterface) -> None:
        """Add ``headers``, in order.

        Raises:
            LogicError: A header is not of the class its name needs, or is added twice when
                it must be unique.
        """
        self._headers: dict[str, list[HeaderInterface]] = {}
        self._line_length = 76
        for header in headers:
            _ = self.add(header)

    def __copy__(self) -> Headers:
        """Copy the headers too: changing a header of the copy leaves this one as it is."""
        copied = Headers()
        copied._line_length = self._line_length
        for header in self.all():
            _ = copied.add(copy.deepcopy(header))
        return copied

    def set_max_line_length(self, line_length: int) -> None:
        """Set the line length on every header, and on every header added later."""
        self._line_length = line_length
        for header in self.all():
            header.set_max_line_length(line_length)

    def get_max_line_length(self) -> int:
        """Return the line length, 76 unless set."""
        return self._line_length

    def add_mailbox_list_header(
        self, name: str, addresses: Iterable[Address | Group | str]
    ) -> Self:
        """Add a list of addresses and groups; a string is read as an address."""
        return self.add(MailboxListHeader(name, MailboxListHeader.create_address_list(addresses)))

    def add_mailbox_header(self, name: str, address: Address | str) -> Self:
        """Add one address; a string may be ``Name <address>``."""
        return self.add(MailboxHeader(name, Address.create(address)))

    def add_id_header(self, name: str, ids: str | Iterable[str]) -> Self:
        """Add one identifier or several."""
        return self.add(IdentificationHeader(name, ids))

    def add_path_header(self, name: str, path: Address | str) -> Self:
        """Add a path; a string is the bare address."""
        return self.add(PathHeader(name, path if isinstance(path, Address) else Address(path)))

    def add_date_header(self, name: str, date_time: datetime) -> Self:
        """Add a date."""
        return self.add(DateHeader(name, date_time))

    def add_text_header(self, name: str, value: str) -> Self:
        """Add free text."""
        return self.add(UnstructuredHeader(name, value))

    def add_parameterized_header(
        self, name: str, value: str, parameters: Mapping[str, str | None] | None = None
    ) -> Self:
        """Add a value with parameters."""
        return self.add(ParameterizedHeader(name, value, parameters))

    def add_header(self, name: str, argument: object, *more: object) -> Self:
        """Add a header of the class its name needs, text for a name the map does not know.

        For an address list or identifiers, ``argument`` is one value or a sequence of them,
        and ``more`` adds values after it; any other header takes ``argument`` alone.

        Raises:
            InvalidArgumentError: A value is not of the type the header takes.
        """
        kind = _HEADER_CLASSES.get(name.lower(), ("text", ()))[0]
        return self.add(build_header(kind, name, [argument, *more]))

    def has(self, name: str) -> bool:
        """Tell whether a header of that name is there, whatever its case."""
        return name.lower() in self._headers

    def add(self, header: HeaderInterface) -> Self:
        """Add ``header`` after the others, with this collection's line length.

        Raises:
            LogicError: ``header`` is not of the class its name needs, or it must be unique
                and one of its name is already there.
        """
        self.check_header_class(header)
        header.set_max_line_length(self._line_length)
        name = header.get_name().lower()
        if name in _UNIQUE_HEADERS and self._headers.get(name):
            raise LogicError(
                f'Impossible to set header "{header.get_name()}" as it\'s already defined and '
                "must be unique."
            )
        self._headers.setdefault(name, []).append(header)
        return self

    def get(self, name: str) -> HeaderInterface | None:
        """Return the first header of that name, whatever its case, ``None`` if there is none."""
        headers = self._headers.get(name.lower())
        return headers[0] if headers else None

    def all(self, name: str | None = None) -> Iterator[HeaderInterface]:
        """Yield every header in order, or every header of one name, whatever its case."""
        if name is None:
            for headers in self._headers.values():
                yield from headers
        else:
            yield from self._headers.get(name.lower(), [])

    def get_names(self) -> list[str]:
        """Return the names, lowercased, in the order they were first added."""
        return list(self._headers)

    def remove(self, name: str) -> None:
        """Remove every header of that name, whatever its case."""
        _ = self._headers.pop(name.lower(), None)

    @staticmethod
    def is_unique_header(name: str) -> bool:
        """Tell whether a message carries a header of that name at most once."""
        return name.lower() in _UNIQUE_HEADERS

    @staticmethod
    def check_header_class(header: HeaderInterface) -> None:
        """Check that ``header`` is of the class its name needs, if the class map names one.

        Raises:
            LogicError: It is not.
        """
        classes = _HEADER_CLASSES.get(header.get_name().lower(), ("text", ()))[1]
        if classes and not isinstance(header, classes):
            expected = '" or "'.join(_type_name(cls) for cls in classes)
            raise LogicError(
                f'The "{header.get_name()}" header must be an instance of "{expected}" '
                f'(got "{_type_name(type(header))}").'
            )

    def to_string(self) -> str:
        """Return every header with a body, each field ending in CRLF."""
        return "".join(f"{field}\r\n" for field in self.to_array())

    def to_array(self) -> list[str]:
        """Return every header with a body as its folded field; one without a body is skipped."""
        return [field for header in self.all() if (field := _field(header)) is not None]

    def get_header_body(self, name: str) -> object:
        """Return the body of the first header of that name, ``None`` if there is none."""
        header = self.get(name)
        return None if header is None else header.get_body()

    def set_header_body(self, kind: HeaderKind, name: str, body: object) -> None:
        """Replace the body of the first header of that name, or add one of ``kind``.

        Raises:
            InvalidArgumentError: ``body`` is not of the type the header takes.
        """
        header = self.get(name)
        if header is None:
            _ = self.add(build_header(kind, name, [body]))
        else:
            header.set_body(body)

    def get_header_parameter(self, name: str, parameter: str) -> str | None:
        """Return a parameter of the first header of that name, ``None`` if there is none.

        Raises:
            LogicError: The header is not a :class:`ParameterizedHeader`.
        """
        header = self.get(name)
        if header is None:
            return None
        if not isinstance(header, ParameterizedHeader):
            raise LogicError(_not_parameterized("get", parameter, name))
        return header.get_parameter(parameter)

    def set_header_parameter(self, name: str, parameter: str, value: str | None) -> None:
        """Set a parameter of the first header of that name.

        Raises:
            LogicError: There is no such header, or it is not a :class:`ParameterizedHeader`.
        """
        header = self.get(name)
        if header is None:
            raise LogicError(
                f'Unable to set parameter "{escaped(parameter)}" on header "{escaped(name)}" as '
                "the header is not defined."
            )
        if not isinstance(header, ParameterizedHeader):
            raise LogicError(_not_parameterized("set", parameter, name))
        header.set_parameter(parameter, value)


def _field(header: HeaderInterface) -> str | None:
    if isinstance(header, AbstractHeader):
        return header.to_field()
    return header.to_string() if header.get_body_as_string() else None


def _not_parameterized(action: str, parameter: str, name: str) -> str:
    return (
        f'Unable to {action} parameter "{escaped(parameter)}" on header "{escaped(name)}" as the '
        f'header is not of class "{_type_name(ParameterizedHeader)}".'
    )


def _type_name(cls: type) -> str:
    """Name a class by where it is imported from: header classes by ``xtr_mime.header``."""
    module = "xtr_mime.header" if cls.__module__.startswith("xtr_mime.header.") else cls.__module__
    return f"{module}.{cls.__qualname__}"
