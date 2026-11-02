"""A message as a transport sent it: the original, the bytes rendered from it, the envelope."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, ClassVar

from xtr_mime import IdentificationHeader, Message, RawMessage

if TYPE_CHECKING:
    from collections.abc import Generator

    from .envelope import Envelope

__all__ = ["SentMessage"]


class SentMessage:
    """What a transport sent, and what it learned sending it.

    A :class:`~xtr_mime.Message` is rendered once, here, from a copy given a ``Message-ID``
    when it has none: the bytes a transport writes, a signature covers and a listener reads
    afterwards are the same bytes, and the caller's message is left as it was. Raw bytes are
    sent as they are.

    The message id is the transport's: the ``Message-ID`` of a message, until the transport
    sets the id its server gave (an SMTP ``250 Ok queued as ...``, a provider's API id). A raw
    message has none until then.
    """

    __slots__: ClassVar[tuple[str, ...]] = (
        "_debug",
        "_envelope",
        "_message_id",
        "_original",
        "_raw",
    )

    def __init__(self, message: RawMessage, envelope: Envelope) -> None:
        """Check ``message`` can be sent and render it.

        Raises:
            xtr_mime.LogicError: The message cannot be sent as it is: no recipient, no author,
                no body, or a draft.
            xtr_mime.MimeError: The message cannot be rendered — a header or a body the
                engine refuses.
        """
        message.ensure_validity()
        self._original: RawMessage = message
        self._envelope: Envelope = envelope
        self._message_id: str = ""
        self._debug: str = ""
        if isinstance(message, Message):
            prepared = copy.copy(message)
            headers = prepared.get_headers()
            if not headers.has("Message-ID"):
                _ = headers.add_id_header("Message-ID", prepared.generate_message_id())
            identification = headers.get("Message-ID")
            if isinstance(identification, IdentificationHeader):
                self._message_id = identification.get_id() or ""
            self._raw: RawMessage = RawMessage(b"".join(prepared.to_iterable()))
        else:
            self._raw = message

    def get_message(self) -> RawMessage:
        """Return what is sent: the message rendered, or the raw message itself."""
        return self._raw

    def get_original_message(self) -> RawMessage:
        """Return the message as the caller handed it over."""
        return self._original

    def get_envelope(self) -> Envelope:
        """Return the envelope the message was sent with."""
        return self._envelope

    def set_message_id(self, message_id: str) -> None:
        """Replace the message id with the one the transport's server gave."""
        self._message_id = message_id

    def get_message_id(self) -> str:
        """Return the transport's message id, empty for a raw message until one is set.

        For a message it starts as the ``Message-ID`` header of what was rendered, until the
        transport sets the one its server gave.
        """
        return self._message_id

    def get_debug(self) -> str:
        """Return what the transport logged while sending, empty unless it logged anything."""
        return self._debug

    def append_debug(self, debug: str) -> None:
        """Append to what the transport logged."""
        self._debug += debug

    def to_string(self) -> str:
        """Return what is sent, as text."""
        return self._raw.to_string()

    def to_iterable(self) -> Generator[bytes, None, None]:
        """Yield what is sent, as a mail server receives it."""
        return self._raw.to_iterable()
