"""A part tree written to the wire, and wire bytes read back into one."""

from __future__ import annotations

from email.generator import BytesGenerator
from email.message import EmailMessage
from email.parser import BytesParser
from typing import TYPE_CHECKING, final

from typing_extensions import override

from xtr_mime.exception import MimeError, MimeRuntimeError

from ._grammar import PACKAGE_FAILURES, check_boundary
from ._policy import POLICY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from email.message import Message

    from ._policy import EnginePart

    # The stubs make the message generic in its headers' types, which the engine's parts are
    # strings of; the class is not.
    _EmailMessage = EmailMessage[str, str]
else:
    _EmailMessage = EmailMessage

__all__ = ["VerbatimPart", "parse", "render", "to_bytes", "to_string"]


@final
class _ChunkSink:
    """Collects what the generator writes, so rendering can hand the message out in pieces."""

    __slots__ = ("chunks",)

    def __init__(self) -> None:
        self.chunks: list[bytes] = []

    def write(self, data: bytes) -> None:
        self.chunks.append(data)


@final
class VerbatimPart(_EmailMessage):
    """A part whose body is bytes the generator writes as they are, after the part's headers.

    The package's own payload is left empty: its getter decodes the bytes a string holds as
    surrogates, and its writer changes the line ends of a text body.
    """

    def __init__(self, body: bytes) -> None:
        super().__init__(policy=POLICY)
        self.set_payload("")
        self.body: bytes = body


# Not final: the generator clones itself, through its class, for every part it writes.
class _WireGenerator(BytesGenerator):
    """The package's generator, but for a verbatim part: its headers, then its bytes."""

    @override
    def flatten(self, msg: Message, unixfrom: bool = False, linesep: str | None = None) -> None:
        if not isinstance(msg, VerbatimPart):
            super().flatten(msg, unixfrom, linesep)
            return
        # The headers are written by the package, as for any part, then the body after them.
        head: EnginePart = EmailMessage(policy=msg.policy)
        for name, value in msg.raw_items():
            head.set_raw(name, value)
        head.set_payload("")
        super().flatten(head, unixfrom, linesep)
        self.write(msg.body.decode("ascii", "surrogateescape"))


def render(part: EnginePart) -> Iterator[bytes]:
    """Render ``part`` as the bytes a mail server accepts, in the pieces the engine writes.

    Every header of every part is checked as it is written, those of a parsed part included:
    a header the engine did not build itself may hold what one it builds may not. Every
    multipart must carry its boundary.

    Raises:
        RfcComplianceError: A header is refused: its name is not one, or what is written of
            it holds a control character, a line separator or a lone surrogate, starts a line
            of its own, has a line longer than 998 octets or reads as other addresses than a
            parsed one held; or a multipart has no boundary RFC 2046 allows.
        MimeRuntimeError: The engine fails to write the part.
    """
    for sub_part in part.walk():
        # A multipart the parser read as text is written as such, without boundaries.
        if sub_part.get_content_maintype() == "multipart" and not isinstance(
            sub_part.get_payload(), str
        ):
            check_boundary(sub_part.get_boundary() or "")
    sink = _ChunkSink()
    try:
        _WireGenerator(sink, mangle_from_=False, policy=POLICY).flatten(part)
    except MimeError:
        raise
    except PACKAGE_FAILURES as error:
        raise MimeRuntimeError(f"The message cannot be written: {error}.") from error
    yield from sink.chunks


def to_bytes(part: EnginePart) -> bytes:
    """Render ``part`` in one piece.

    Raises:
        RfcComplianceError: As :func:`render` does.
        MimeRuntimeError: As :func:`render` does.
    """
    return b"".join(render(part))


def to_string(part: EnginePart) -> str:
    """Render ``part`` as text; bytes that are not UTF-8 (an 8bit body) survive as surrogates.

    ``to_string(part).encode("utf-8", "surrogateescape") == to_bytes(part)``, always.

    Raises:
        RfcComplianceError: As :func:`render` does.
        MimeRuntimeError: As :func:`render` does.
    """
    return to_bytes(part).decode("utf-8", "surrogateescape")


def parse(data: bytes) -> EnginePart:
    """Read a rendered message (S/MIME output, a test's expectation) back into a part tree.

    Raises:
        MimeRuntimeError: The parts are nested deeper than the engine's reader can follow, or
            the reader fails on the bytes.
    """
    try:
        return BytesParser(policy=POLICY).parsebytes(data)
    except RecursionError as error:
        raise MimeRuntimeError("The message is nested too deeply to be read.") from error
    except PACKAGE_FAILURES as error:
        raise MimeRuntimeError(f"The message cannot be read: {error}.") from error
