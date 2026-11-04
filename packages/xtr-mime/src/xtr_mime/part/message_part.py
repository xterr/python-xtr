"""A whole message attached to another, as ``message/rfc822``."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, ClassVar, Final, Protocol, final, runtime_checkable

from typing_extensions import override

from xtr_mime._engine import build_verbatim, set_fields

from .data_part import DataPart

if TYPE_CHECKING:
    from collections.abc import Iterable

    from xtr_mime._engine import EnginePart
    from xtr_mime.header import Headers

__all__ = ["MessagePart"]

# Any line end: CRLF, a bare LF or a bare CR.
_LINE_END: Final = re.compile(rb"\r\n|\r|\n")


class _RenderableMessage(Protocol):
    """What a message attached to another must do: render itself."""

    def to_string(self) -> str:
        """Return the whole message as text."""
        ...

    def to_iterable(self) -> Iterable[bytes]:
        """Return the whole message in the bytes a mail server receives."""
        ...


@runtime_checkable
class _MessageWithHeaders(Protocol):
    """A message whose headers can be read, which names the attachment after its subject."""

    def get_headers(self) -> Headers:
        """Return the message's headers."""
        ...


@final
class MessagePart(DataPart):
    """A message carried as an attachment, named after its subject (``email.eml`` for none).

    The message is rendered when the part is, and written in ``8bit``: RFC 2046 allows a
    ``message/rfc822`` body only ``7bit``, ``8bit`` or ``binary``, so a reader opens it as the
    message it is. Its bytes are written as they are, 8-bit ones included, but for its line
    ends, every one written as CRLF — the only line end SMTP carries; the message itself is
    left as it is.
    """

    __slots__: ClassVar[tuple[str, ...]] = ("_message",)

    def __init__(self, message: _RenderableMessage) -> None:
        """Keep ``message``; it is rendered only when the part is."""
        if isinstance(message, _MessageWithHeaders):
            name = f"{message.get_headers().get_header_body('Subject') or ''}.eml"
        else:
            name = "email.eml"
        super().__init__("", name, "message/rfc822", "8bit")
        self._message: _RenderableMessage = message

    def get_message(self) -> _RenderableMessage:
        """Return the message carried, as it was given."""
        return self._message

    @override
    def get_body(self) -> str:
        """Return the message, rendered."""
        return self._message.to_string()

    @override
    def _to_engine(self) -> EnginePart:
        part = build_verbatim(_LINE_END.sub(b"\r\n", b"".join(self._message.to_iterable())))
        set_fields(part, self.get_prepared_headers().to_array())
        return part
